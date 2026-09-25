# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""What one failing step of a management pass takes down with it.

The pass runs four steps: the liveness check, the aggregator, the stale sweep
and then _start_new_trials. The aggregator and the sweep each handle their own
exceptions. The liveness check did not, so anything it raised reached the loop,
which logs and waits five seconds. A database blip on the first trial it
touched cost the three steps after it as well, and a run with free capacity
claimed nothing while it went on.
"""

import datetime
from unittest import mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services import worker
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
import psutil
import pytest
import sqlalchemy
from sqlalchemy import orm

# pylint: disable=protected-access

# The PID the fake spawn reports for the trial the pass starts.
_PID = 4242

# The PID on the in-flight trial. Nothing is there, so the liveness check
# retries it, and the retry is the commit that fails.
_DEAD_PID = 4243

# The start time recorded beside a PID when its worker was spawned.
_PID_STARTED_AT = 1758000000.25


@pytest.fixture(name="gda_client")
def _gda_client():
  """Answers the two calls create_run makes on the way past."""
  client = mock.MagicMock()
  client.get_agent_context.return_value = {"sys": "test"}
  return client


@pytest.fixture(name="manager")
def _manager(session_factory: orm.sessionmaker):
  """The manager, reset either side because it is a singleton."""
  WorkerProcessManager._instance = None
  mgr = WorkerProcessManager(session_factory=session_factory)
  yield mgr
  mgr.stop()
  WorkerProcessManager._instance = None


def _agent(db_session: orm.Session):
  return AgentRepository(db_session).create(
      name="Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=BigQueryConfig(tables=["t"]),
      ),
  )


def _suite(db_session: orm.Session, *questions: str):
  suite = SuiteRepository(db_session).create(name="Suite")
  example_repo = ExampleRepository(db_session)
  for question in questions:
    example_repo.create(suite.id, question)
  db_session.commit()
  return suite


def _run_with_a_dead_worker_and_a_waiting_trial(db_session, gda_client):
  """A RUNNING run holding one in-flight trial and one still PENDING.

  Concurrency of two, so the run has a slot free for the waiting trial. The
  in-flight one carries a PID nothing is at, which is what sends the liveness
  check into the retry whose commit fails.
  """
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  exec_service = ExecutionService(db_session, snap_service, gda_client)

  agent = _agent(db_session)
  suite = _suite(db_session, "Q1", "Q2")
  run = exec_service.create_run(agent.id, suite.id, concurrency=2)
  run.status = execution.RunStatus.RUNNING

  in_flight, waiting = run.trials
  in_flight.status = execution.RunStatus.RUNNING
  in_flight.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(seconds=60)
  in_flight.trial_pid = _DEAD_PID
  in_flight.trial_pid_started_at = _PID_STARTED_AT
  db_session.commit()
  return in_flight, waiting


def _process_lookup(pid: int):
  """psutil.Process, with nothing at the in-flight trial's PID."""
  if pid == _DEAD_PID:
    raise psutil.NoSuchProcess(pid)
  proc = mock.MagicMock()
  proc.is_running.return_value = True
  proc.status.return_value = psutil.STATUS_RUNNING
  proc.create_time.return_value = _PID_STARTED_AT
  return proc


def _spawn_context():
  """A context whose Process reports that it started."""
  ctx = mock.MagicMock()
  ctx.Process.return_value.pid = _PID
  ctx.Process.return_value.is_alive.return_value = False
  return ctx


def _factory_whose_first_session_cannot_commit(
    session_factory: orm.sessionmaker,
):
  """A factory whose first session refuses to commit, like a database blip.

  Only the first one. The steps after the liveness check open sessions of their
  own, and whether they still get to run is what is under test.
  """
  opened = []

  def refuse():
    raise sqlalchemy.exc.OperationalError(
        "COMMIT", {}, Exception("server closed the connection")
    )

  def open_session():
    session = session_factory()
    opened.append(session)
    if len(opened) == 1:
      session.commit = refuse
    return session

  return open_session


def _one_pass(manager):
  """Runs the management loop for a single pass, on the calling thread.

  The loop waits on the stop event at the end of a pass and again in its
  exception handler, so setting the event from the wait returns after one turn
  whichever way the pass went.
  """

  def wait(timeout):
    del timeout
    manager.stop_event.set()
    return True

  return mock.patch.object(manager.stop_event, "wait", side_effect=wait)


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def test_a_failed_liveness_check_does_not_cost_the_rest_of_the_pass(
    db_session, gda_client, manager, session_factory
):
  """The liveness check was the only step of the pass with no handler.

  A commit that failed on the first trial reached the management loop, which
  logs and waits five seconds. The aggregator, the stale sweep and
  _start_new_trials were all skipped, so a run with a free slot and a trial
  waiting for it claimed nothing.
  """
  in_flight, waiting = _run_with_a_dead_worker_and_a_waiting_trial(
      db_session, gda_client
  )
  manager.session_factory = _factory_whose_first_session_cannot_commit(
      session_factory
  )

  with (
      _one_pass(manager),
      mock.patch.object(
          worker.multiprocessing, "get_context", return_value=_spawn_context()
      ),
      mock.patch.object(worker.psutil, "Process", side_effect=_process_lookup),
  ):
    manager._management_loop()

  started = _reread(db_session, waiting)
  assert started.status == execution.RunStatus.RUNNING, (
      "The pass stopped at the liveness check, so the run sat on a free slot"
      " with a trial waiting for it."
  )
  assert started.trial_pid == _PID

  # The trial whose retry could not commit is still where it was. Losing that
  # one write is the part of the pass the blip is allowed to cost.
  unchanged = _reread(db_session, in_flight)
  assert unchanged.status == execution.RunStatus.RUNNING
  assert unchanged.retry_count == 0
