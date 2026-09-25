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

"""What the manager does about a run that was cancelled underneath it.

Cancel is a web request and the manager is a loop in another thread, so the
cancel lands in the middle of a pass. Two things went wrong with that.

The trials already in flight were left alone. cancel_run only cancels the
PENDING trials, so whatever had a worker on it ran to the end against the
agent, billed for it, and wrote its answer into a run nobody was going to read.
Those trials also held the run's capacity while they did it.

And the aggregator assigned COMPLETED without looking at the status it had read
a moment earlier. A run cancelled while the aggregator walked its trials came
back as COMPLETED with a fresh completed_at over the real one, which is what
Run.duration_ms is measured from.
"""

import datetime
import os
from unittest import mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server.repositories import run_repository
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

# When the run under test was cancelled, and what its duration is measured
# from afterwards.
_CANCELLED_AT = datetime.datetime(
    2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc
)


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


def _exec_service(db_session: orm.Session, gda_client) -> ExecutionService:
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  return ExecutionService(db_session, snap_service, gda_client)


def _run(db_session: orm.Session, gda_client, status):
  """A one trial run in the given status, at a concurrency of one."""
  exec_service = _exec_service(db_session, gda_client)
  agent = _agent(db_session)
  suite = _suite(db_session, "Q1")

  run = exec_service.create_run(agent.id, suite.id, concurrency=1)
  run.status = status
  db_session.commit()
  return run


def _trial_in_flight(
    db_session: orm.Session,
    run,
    pid: int | None = _PID,
    started_seconds_ago: int = 60,
):
  """The run's trial the way the manager leaves it after spawning a worker."""
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
  trial.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(seconds=started_seconds_ago)
  trial.trial_pid = pid
  trial.trial_pid_started_at = _PID_STARTED_AT if pid else None
  db_session.commit()
  return trial


def _process(created: float = _PID_STARTED_AT):
  """A psutil.Process stand-in carrying what the manager reads off one."""
  proc = mock.MagicMock()
  proc.ppid.return_value = os.getpid()
  proc.is_running.return_value = True
  proc.status.return_value = psutil.STATUS_RUNNING
  proc.create_time.return_value = created
  return proc


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def _cancel_while_the_aggregator_runs(db_session: orm.Session, run):
  """Cancels the run in the gap the aggregator walks its trials in.

  The aggregator lists the active runs, reads each one's trials and only then
  writes. Cancel arrives on the web request thread, and this puts it at the
  one point where the status the aggregator read is already out of date.
  """
  original = run_repository.RunRepository.list_active

  def list_then_cancel(repo):
    runs = original(repo)
    run.status = execution.RunStatus.CANCELLED
    run.completed_at = _CANCELLED_AT
    # Committed here, so the manager's own session sees a cancelled row and
    # is not waiting on a lock this session holds.
    db_session.commit()
    return runs

  return mock.patch.object(
      run_repository.RunRepository,
      "list_active",
      autospec=True,
      side_effect=list_then_cancel,
  )


def test_a_cancelled_run_stops_its_running_trials(
    db_session, gda_client, manager
):
  """Cancel reaches the queue, and the manager has to reach the workers.

  A trial already in flight ran to the end against the agent and billed for
  it, then wrote an answer into a run nobody was going to look at. It also
  held the run's capacity until it finished.
  """
  run = _run(db_session, gda_client, execution.RunStatus.CANCELLED)
  trial = _trial_in_flight(db_session, run)
  proc = _process()

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._check_active_trials()

  proc.kill.assert_called_once()
  after = _reread(db_session, trial)
  assert (
      after.status == execution.RunStatus.CANCELLED
  ), "A trial of a cancelled run went on running and went on being billed."
  assert (
      after.completed_at is not None
  ), "Without a completion time the trial shows an open-ended duration."


def test_a_trial_that_has_not_recorded_its_pid_yet_is_left_alone(
    db_session, gda_client, manager
):
  """The claim and the PID are two commits, and the loop can see the gap.

  A trial claimed a moment ago has a live worker behind it that the row does
  not name yet. Stopping it here marks it CANCELLED while that worker keeps
  writing to the row, so the ten second grace period leaves it for the next
  pass, by which time the PID is there to kill.
  """
  run = _run(db_session, gda_client, execution.RunStatus.CANCELLED)
  trial = _trial_in_flight(db_session, run, pid=None, started_seconds_ago=2)

  manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.completed_at is None


def test_a_trial_still_missing_its_pid_after_the_grace_period_is_stopped(
    db_session, gda_client, manager
):
  """The grace period is ten seconds, not indefinite.

  A minute on, there is no worker coming, so the trial is not left RUNNING in
  a run that has been cancelled.
  """
  run = _run(db_session, gda_client, execution.RunStatus.CANCELLED)
  trial = _trial_in_flight(db_session, run, pid=None, started_seconds_ago=60)

  manager._check_active_trials()

  assert _reread(db_session, trial).status == execution.RunStatus.CANCELLED


def test_a_trial_of_a_run_that_is_still_going_is_not_stopped(
    db_session, gda_client, manager
):
  """Guards the check above. This pass runs against every active trial.

  Stopping a live trial of a healthy run throws away an answer the run has
  already paid for.
  """
  run = _run(db_session, gda_client, execution.RunStatus.RUNNING)
  trial = _trial_in_flight(db_session, run)
  proc = _process()

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._check_active_trials()

  proc.kill.assert_not_called()
  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.retry_count == 0


def test_a_run_cancelled_during_the_aggregator_pass_stays_cancelled(
    db_session, gda_client, manager
):
  """The aggregator wrote COMPLETED over a status it had read minutes ago.

  Every trial of a cancelled run is terminal, which is what the aggregator
  calls done, so the run came back COMPLETED and its real completion time was
  replaced by the time the aggregator got there.
  """
  run = _run(db_session, gda_client, execution.RunStatus.RUNNING)
  run.trials[0].status = execution.RunStatus.COMPLETED
  db_session.commit()

  with _cancel_while_the_aggregator_runs(db_session, run):
    manager._aggregate_run_statuses()

  after = _reread(db_session, run)
  assert after.status == execution.RunStatus.CANCELLED
  assert (
      after.completed_at == _CANCELLED_AT
  ), "Run.duration_ms is measured from this, so it has to be the real one."


@pytest.mark.parametrize(
    "trial_status",
    [execution.RunStatus.COMPLETED, execution.RunStatus.FAILED],
)
def test_a_running_run_whose_trials_are_all_done_still_completes(
    db_session, gda_client, manager, trial_status
):
  """Guards the check above. Completing runs is the aggregator's job.

  A failed trial is done too. The run is over either way, and waiting on one
  would leave it RUNNING for good.
  """
  run = _run(db_session, gda_client, execution.RunStatus.RUNNING)
  run.trials[0].status = trial_status
  db_session.commit()

  manager._aggregate_run_statuses()

  after = _reread(db_session, run)
  assert after.status == execution.RunStatus.COMPLETED
  assert after.completed_at is not None
