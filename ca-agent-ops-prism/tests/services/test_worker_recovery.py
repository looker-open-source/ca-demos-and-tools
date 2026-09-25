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

"""What the worker manager does when a trial, a run or itself goes wrong.

Three of these failures reached users. A trial whose worker process died sat
RUNNING on the run page until someone restarted the server. A run created
against a suite with no questions sat there forever, and promote_next_run will
not promote past it, so one empty suite jammed every run queued behind it. And
stop() returned as soon as the stop event was set, leaving a thread that woke
up two seconds later and queried a schema the test had already dropped, which
failed some later test instead of the one that started it.

The recovery paths are the dangerous kind of code: they act on other
processes. So each fix is pinned here together with the case it must not
catch, a live worker, a PID that now belongs to something else, and a run that
does have questions.
"""

import datetime
import os
from unittest import mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server.models import run as run_models
from prism.server.models import snapshot as snapshot_models
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
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

# The PID on the trials below. Nothing is ever spawned, psutil is faked.
_PID = 4242


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


def _claimed_trial(
    db_session: orm.Session,
    gda_client,
    status=execution.RunStatus.RUNNING,
    started_minutes_ago: int = 40,
):
  """One trial the way the manager leaves it after spawning a worker."""
  exec_service = _exec_service(db_session, gda_client)
  agent = _agent(db_session)
  suite = _suite(db_session, "Q1")

  run = exec_service.create_run(agent.id, suite.id)
  run.status = execution.RunStatus.RUNNING
  trial = run.trials[0]
  trial.status = status
  trial.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=started_minutes_ago)
  trial.trial_pid = _PID
  db_session.commit()
  return trial


def _process(ppid: int | None = None, zombie: bool = False):
  """A psutil.Process stand-in carrying what the manager reads off one."""
  proc = mock.MagicMock()
  proc.ppid.return_value = os.getpid() if ppid is None else ppid
  proc.is_running.return_value = True
  proc.status.return_value = (
      psutil.STATUS_ZOMBIE if zombie else psutil.STATUS_RUNNING
  )
  return proc


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


@pytest.mark.parametrize(
    "status",
    [
        execution.RunStatus.RUNNING,
        execution.RunStatus.EXECUTING,
        execution.RunStatus.EVALUATING,
    ],
)
def test_a_stale_trial_is_freed_whichever_active_status_it_is_in(
    db_session, gda_client, manager, status
):
  """A trial wedges in whatever status it was in when it stopped moving.

  EXECUTING and EVALUATING are as stuck as RUNNING, and were recovered from
  neither.
  """
  trial = _claimed_trial(db_session, gda_client, status=status)

  with mock.patch.object(worker.psutil, "Process", return_value=_process()):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert after.trial_pid is None
  assert after.started_at is None


def test_a_wedged_process_of_ours_is_killed(db_session, gda_client, manager):
  """The kill comes first, then the row is freed.

  Freeing the row first lets _start_new_trials spawn a second worker for a
  trial the first one is still writing to, and both bill the agent API.
  """
  _claimed_trial(db_session, gda_client)
  proc = _process()

  with mock.patch.object(worker.psutil, "Process", return_value=proc) as lookup:
    manager._recover_stale_trials()

  lookup.assert_called_once_with(_PID)
  proc.kill.assert_called_once()


def test_a_pid_with_another_parent_is_left_alone(
    db_session, gda_client, manager
):
  """Half an hour is long enough for the PID to have been recycled.

  Trials are spawned by this process, so a different parent means the PID is
  not ours and the kill would land on something unrelated. With no recorded
  start time there is no way to tell a recycled PID from one of our own
  reparented children, so the row stays claimed rather than being freed into
  a second worker.
  """
  trial = _claimed_trial(db_session, gda_client)
  proc = _process(ppid=os.getpid() + 1)

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._recover_stale_trials()

  proc.kill.assert_not_called()
  assert _reread(db_session, trial).status == execution.RunStatus.RUNNING


def test_a_kill_that_keeps_failing_is_given_up_on_eventually(
    db_session, gda_client, manager
):
  """Leaving the row claimed is only a plan while the kill might yet work.

  Four hours of failing to reach the process is not a transient. The run
  cannot aggregate while one of its trials is in flight and nothing else is
  allowed to start, so the whole queue was stopped on a process there was no
  way to reach. It is failed rather than retried, because a retry would spawn
  a second worker while whatever is holding the first one is still up.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=5 * 60)
  proc = _process(ppid=os.getpid() + 1)

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._recover_stale_trials()

  proc.kill.assert_not_called()
  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.FAILED
  assert after.completed_at is not None
  assert after.retry_count == 0


def test_a_trial_stale_for_under_four_hours_is_still_waited_on(
    db_session, gda_client, manager
):
  """Pairs with the test above: giving up has a deadline, not a hair trigger.

  Most unkillable processes are a PID check that could not prove ownership,
  and those clear themselves on a later pass.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=3 * 60)

  with mock.patch.object(
      worker.psutil, "Process", return_value=_process(ppid=os.getpid() + 1)
  ):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.trial_pid == _PID


def test_a_process_that_already_exited_is_not_an_error(
    db_session, gda_client, manager
):
  """Recovery swallows its own exceptions.

  A NoSuchProcess escaping the kill shows up as a trial left RUNNING, not as
  a traceback.
  """
  trial = _claimed_trial(db_session, gda_client)

  with mock.patch.object(
      worker.psutil, "Process", side_effect=psutil.NoSuchProcess(_PID)
  ):
    manager._recover_stale_trials()

  assert _reread(db_session, trial).status == execution.RunStatus.PENDING


def test_a_trial_younger_than_the_timeout_is_left_alone(
    db_session, gda_client, manager
):
  """The timeout is for work that has stopped moving.

  Five minutes in, a trial is just slow, and killing it loses a paid-for answer.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=5)

  with mock.patch.object(worker.psutil, "Process") as lookup:
    manager._recover_stale_trials()

  lookup.assert_not_called()
  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.trial_pid == _PID


def test_a_live_worker_keeps_its_trial_running(db_session, gda_client, manager):
  """A false positive here fails a run that was working.

  The liveness pass runs every two seconds against every active trial.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)

  with mock.patch.object(worker.psutil, "Process", return_value=_process()):
    manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.retry_count == 0


def test_a_trial_whose_worker_is_gone_is_retried(
    db_session, gda_client, manager
):
  """Nothing else notices a dead worker.

  The trial showed as RUNNING on the run page until the server was restarted.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)

  with mock.patch.object(
      worker.psutil, "Process", side_effect=psutil.NoSuchProcess(_PID)
  ):
    manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert after.retry_count == 1


def test_a_trial_killed_before_its_pid_landed_is_retried(
    db_session, gda_client, manager
):
  """A missing PID past the grace period costs a retry, not the trial.

  The claim and the PID write are two commits, so the loop can catch a trial
  RUNNING with trial_pid still unset. Past the ten second window it failed the
  trial outright, ignoring retry_count and max_retries. That trial was failed
  for good and scored 0.0 against the run, while the trial one step further
  on, with a PID that was dead, was retried.
  """
  # A minute old, so the ten second grace period has passed.
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)
  trial.trial_pid = None
  db_session.commit()

  manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert after.retry_count == 1


def test_a_zombie_worker_does_not_count_as_alive(
    db_session, gda_client, manager
):
  """A dead child still resolves as a process until it is reaped.

  is_running() on its own reports that corpse as up.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)

  with mock.patch.object(
      worker.psutil, "Process", return_value=_process(zombie=True)
  ):
    manager._check_active_trials()

  assert _reread(db_session, trial).status == execution.RunStatus.PENDING


def test_a_run_on_a_suite_with_no_questions_is_rejected(db_session, gda_client):
  """There is nothing to execute, and the caller is the only one who can fix it.

  The error names the suite and says what to do.
  """
  agent = _agent(db_session)
  suite = _suite(db_session)
  exec_service = _exec_service(db_session, gda_client)

  with pytest.raises(ValueError, match="has no active questions"):
    exec_service.create_run(agent.id, suite.id)


def test_a_rejected_run_leaves_nothing_behind(db_session, gda_client):
  """The check sits before the snapshot, so a refused run writes no rows."""
  agent = _agent(db_session)
  suite = _suite(db_session)
  exec_service = _exec_service(db_session, gda_client)

  with pytest.raises(ValueError):
    exec_service.create_run(agent.id, suite.id)

  assert not db_session.scalars(sqlalchemy.select(run_models.Run)).all()
  assert not db_session.scalars(
      sqlalchemy.select(snapshot_models.TestSuiteSnapshot)
  ).all()


def test_a_suite_with_questions_still_gets_its_run(db_session, gda_client):
  """The guard is on an empty suite, not on creating a run."""
  agent = _agent(db_session)
  suite = _suite(db_session, "Q1", "Q2")
  exec_service = _exec_service(db_session, gda_client)

  run = exec_service.create_run(agent.id, suite.id)

  assert run.status == execution.RunStatus.PENDING
  assert len(run.trials) == 2


def test_a_run_with_no_trials_completes_instead_of_staying_running(
    db_session, gda_client, manager
):
  """Runs created before the guard are still in the database.

  No trial will ever finish and move one of these along, and while it is
  RUNNING the queue behind it does not move either. The aggregator counts it
  as trivially done.
  """
  del gda_client  # The run is built from the repositories, not create_run.
  agent = _agent(db_session)
  suite = _suite(db_session)
  snap_service = SnapshotService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  )
  snapshot = snap_service.create_snapshot(suite.id)
  run = RunRepository(db_session).create(snapshot.id, agent.id)
  run.status = execution.RunStatus.RUNNING
  db_session.commit()

  manager._aggregate_run_statuses()

  after = _reread(db_session, run)
  assert after.status == execution.RunStatus.COMPLETED
  assert after.completed_at is not None


def test_stop_returns_with_the_management_thread_finished(manager):
  """stop() used to return as soon as it had set the event.

  The thread then woke up on its own two seconds later, mid-teardown, and
  queried a schema the test had already dropped. That failed whichever test
  came next, not the one that left the thread running.

  The loop waits on the stop event rather than sleeping, so this costs the
  length of one pass, not the two seconds between them.
  """
  manager.start()
  thread = manager._thread
  assert thread.is_alive()

  manager.stop()

  assert not thread.is_alive()
  assert manager._thread is None


def test_stop_on_a_manager_that_never_started_is_a_no_op(manager):
  """Shutdown runs whether or not the pool was ever brought up."""
  manager.stop()

  assert manager._thread is None
