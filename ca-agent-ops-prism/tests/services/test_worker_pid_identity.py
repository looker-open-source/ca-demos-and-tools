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

"""Telling a trial's own worker apart from whatever holds its PID now.

A PID is not process identity. Cloud Run restarts the container and the PID
namespace starts again, so the first workers the new process spawns land on the
same low numbers the trials claimed before the restart recorded. Those trials
then read as alive: they held their run's capacity until the 30 minute timeout
and the run sat there, and the kill that eventually came went to a healthy
unrelated trial, because its parent was us and the ppid check was happy.

So the manager records the process start time next to the PID and compares it.
These pin both answers: a recycled PID is dead and must not be killed, and a
worker that really is the trial's is alive and must not be touched.
"""

import datetime
import os
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
from sqlalchemy import orm

# pylint: disable=protected-access

# The PID on the trials below. Nothing is ever spawned, psutil is faked.
_PID = 4242

# The start time recorded beside that PID when the worker was spawned.
_PID_STARTED_AT = 1758000000.25

# A process that took the PID over later. The gap is what gives it away.
_RECYCLED_STARTED_AT = _PID_STARTED_AT + 900.0


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


def _running_run(db_session: orm.Session, gda_client):
  """A RUNNING run with one PENDING trial, at a concurrency of one."""
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  exec_service = ExecutionService(db_session, snap_service, gda_client)

  agent = _agent(db_session)
  suite = _suite(db_session, "Q1")
  run = exec_service.create_run(agent.id, suite.id, concurrency=1)
  run.status = execution.RunStatus.RUNNING
  db_session.commit()
  return run


def _claimed_trial(
    db_session: orm.Session,
    gda_client,
    started_minutes_ago: int = 40,
    started_at: float | None = _PID_STARTED_AT,
):
  """One trial the way the manager leaves it after spawning a worker."""
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
  trial.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=started_minutes_ago)
  trial.trial_pid = _PID
  trial.trial_pid_started_at = started_at
  db_session.commit()
  return trial


def _process(created: float = _PID_STARTED_AT, ppid: int | None = None):
  """A psutil.Process stand-in carrying what the manager reads off one."""
  proc = mock.MagicMock()
  proc.ppid.return_value = os.getpid() if ppid is None else ppid
  proc.is_running.return_value = True
  proc.status.return_value = psutil.STATUS_RUNNING
  proc.create_time.return_value = created
  return proc


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def test_a_trial_whose_pid_was_recycled_does_not_read_as_alive(
    db_session, gda_client, manager
):
  """This is what a container restart leaves on every claimed trial.

  The process at the PID is up, and it is even one of ours, so the liveness
  pass called the trial healthy and its run kept the capacity spent on it
  until the half hour timeout. The start times do not match, so the trial's
  own worker is gone and the trial is owed a retry now.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)

  with mock.patch.object(
      worker.psutil, "Process", return_value=_process(_RECYCLED_STARTED_AT)
  ):
    manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING, (
      "A trial whose worker died before a restart stayed RUNNING, and its run"
      " stalled behind it."
  )
  assert after.retry_count == 1


def test_a_worker_that_matches_its_recorded_start_time_is_left_running(
    db_session, gda_client, manager
):
  """The pass runs every two seconds against every active trial.

  A false positive here fails a run that is working, so the match has to hold
  for the ordinary case of a live worker.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)

  with mock.patch.object(worker.psutil, "Process", return_value=_process()):
    manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.retry_count == 0


def test_a_recycled_pid_is_freed_without_a_kill(
    db_session, gda_client, manager
):
  """Half an hour is long enough for the PID to belong to someone else.

  The ppid told the old code nothing here: after a restart the process holding
  the PID is one of our own healthy workers, and it was SIGKILLed off another
  trial's row. The start time says the stale trial's process is already gone,
  so there is nothing to kill and the row is safe to free.
  """
  trial = _claimed_trial(db_session, gda_client)
  proc = _process(_RECYCLED_STARTED_AT)

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._recover_stale_trials()

  proc.kill.assert_not_called()
  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert after.trial_pid is None
  assert after.trial_pid_started_at is None


def test_a_trial_with_no_recorded_start_time_and_a_foreign_parent_is_kept(
    db_session, gda_client, manager
):
  """Trials claimed before the column existed cannot be told apart.

  A foreign parent is either a recycled PID or a child of ours that was
  reparented, and there is no way to say which. Freeing the row on the second
  reading spawns a second worker onto a trial that is still being written, so
  the row stays claimed until the process is gone and psutil says so.
  """
  trial = _claimed_trial(db_session, gda_client, started_at=None)
  proc = _process(ppid=os.getpid() + 1)

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._recover_stale_trials()

  proc.kill.assert_not_called()
  assert _reread(db_session, trial).status == execution.RunStatus.RUNNING


def test_the_manager_records_the_start_time_when_it_spawns_a_worker(
    db_session, gda_client, manager
):
  """Nothing downstream can compare a start time that was never written."""
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]

  ctx = mock.MagicMock()
  ctx.Process.return_value.pid = _PID
  with (
      mock.patch.object(
          worker.multiprocessing, "get_context", return_value=ctx
      ),
      mock.patch.object(worker.psutil, "Process", return_value=_process()),
  ):
    manager._start_new_trials()

  after = _reread(db_session, trial)
  assert after.trial_pid == _PID
  assert after.trial_pid_started_at == pytest.approx(_PID_STARTED_AT), (
      "Without the start time the PID is the only identity again, which is"
      " what a restart breaks."
  )
