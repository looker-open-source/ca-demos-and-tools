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

"""Trials the manager cannot account for, and the rows it must not free.

Each of these paths freed a trial row while something else still owned it. A
kill that timed out left the wedged process writing to a trial that had already
been handed to a second worker, so both wrote the row and both billed the agent
API. A spawn that failed with EAGAIN, which is the transient the per-run
concurrency limit exists for, failed the trial outright, spent none of its
retries and scored 0.0 into the run's accuracy. And a trial that finished while
the liveness pass was still walking its snapshot of the list was reset on top of
its own result.
"""

import datetime
import errno
import os
from unittest import mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server.models import run as run_models
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

# What the kernel says when it will not fork another process right now.
_EAGAIN = OSError(errno.EAGAIN, "Resource temporarily unavailable")


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


def _running_run(db_session: orm.Session, gda_client):
  """A RUNNING run with one PENDING trial, which is what the manager picks up.

  Concurrency of one, so _start_new_trials makes a single pass at the trial.
  At the default of two it claims the same trial again on the second pass and
  the retry count under test counts two failures instead of one.
  """
  exec_service = _exec_service(db_session, gda_client)
  agent = _agent(db_session)
  suite = _suite(db_session, "Q1")

  run = exec_service.create_run(agent.id, suite.id, concurrency=1)
  run.status = execution.RunStatus.RUNNING
  db_session.commit()
  return run


def _claimed_trial(
    db_session: orm.Session,
    gda_client,
    status=execution.RunStatus.RUNNING,
    started_minutes_ago: int = 40,
):
  """One trial the way the manager leaves it after spawning a worker."""
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]
  trial.status = status
  trial.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=started_minutes_ago)
  trial.trial_pid = _PID
  trial.trial_pid_started_at = _PID_STARTED_AT
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


def _spawn_context(side_effect=None, pid: int = _PID, survives_kill=False):
  """A multiprocessing context whose Process fails, or pretends to start.

  is_alive is answered rather than left to MagicMock, which would return a
  truthy mock and read as a child that shrugged off SIGKILL.
  """
  ctx = mock.MagicMock()
  process = ctx.Process.return_value
  process.pid = pid
  process.start.side_effect = side_effect
  process.is_alive.return_value = survives_kill
  return ctx


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def test_a_trial_whose_kill_timed_out_is_not_requeued(
    db_session, gda_client, manager
):
  """SIGKILL not landing inside five seconds means the process is still there.

  The trial used to be reset to PENDING anyway, so _start_new_trials spawned a
  second worker onto a row the first one was still writing to. That is the
  double execution the kill exists to prevent, and it bills the agent API
  twice. A trial left claimed is picked up again on the next pass instead.
  """
  trial = _claimed_trial(db_session, gda_client)
  proc = _process()
  proc.wait.side_effect = psutil.TimeoutExpired(5)

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert (
      after.status == execution.RunStatus.RUNNING
  ), "A trial whose process survived the kill was freed for a second worker."
  assert (
      after.trial_pid == _PID
  ), "The PID is the only handle on the surviving process, so it has to stay."


def test_a_killed_and_reaped_trial_is_still_requeued(
    db_session, gda_client, manager
):
  """The timeout is the exception, not the rule.

  A kill that the process is reaped after leaves nothing writing to the row,
  so recovery goes ahead exactly as before.
  """
  trial = _claimed_trial(db_session, gda_client)
  proc = _process()

  with mock.patch.object(worker.psutil, "Process", return_value=proc):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert proc.kill.called, "A wedged process of ours still has to be killed."
  assert after.status == execution.RunStatus.PENDING
  assert after.trial_pid is None
  assert after.trial_pid_started_at is None


def test_a_spawn_failure_retries_the_trial_instead_of_failing_it(
    db_session, gda_client, manager
):
  """EAGAIN is the load the per-run concurrency limit is there to shed.

  Failing the trial on it was permanent: the trial never ran, spent none of
  its three retries, and scored 0.0 into the run's accuracy, which reads as
  the agent getting the question wrong.
  """
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]

  with mock.patch.object(
      worker.multiprocessing,
      "get_context",
      return_value=_spawn_context(side_effect=_EAGAIN),
  ):
    manager._start_new_trials()

  after = _reread(db_session, trial)
  assert (
      after.status == execution.RunStatus.PENDING
  ), "A trial nothing was spawned for is owed another attempt, not a score."
  assert (
      after.retry_count == 1
  ), "The retry has to be counted, or a machine that cannot fork loops here."


def test_a_child_that_died_before_it_was_recorded_is_retried(
    db_session, gda_client, manager
):
  """start() returning is not the child having survived its imports.

  A child that died in between left nothing to read a start time from. The PID
  went on the row anyway, and _is_trial_process reads a row with a PID and no
  start time as alive, so the trial held its run's capacity until the stale
  sweep took it half an hour later. It goes back on the queue now.
  """
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]

  with (
      mock.patch.object(
          worker.multiprocessing, "get_context", return_value=_spawn_context()
      ),
      mock.patch.object(worker, "_process_started_at", return_value=None),
  ):
    manager._start_new_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert after.retry_count == 1
  assert after.trial_pid is None
  assert after.trial_pid_started_at is None


def test_a_spawn_failure_fails_the_trial_once_the_retries_are_spent(
    db_session, gda_client, manager
):
  """Retrying is not the same as retrying forever.

  On the last attempt the trial fails, and the message has to name the spawn
  rather than the generic crash the manager reports for a dead PID.
  """
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]
  trial.retry_count = trial.max_retries
  db_session.commit()

  with mock.patch.object(
      worker.multiprocessing,
      "get_context",
      return_value=_spawn_context(side_effect=_EAGAIN),
  ):
    manager._start_new_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.FAILED
  assert (
      "Could not start a worker process" in after.error_message
  ), f"The failure reads {after.error_message!r}, which names nothing."
  # The OSError text is in the log, under the reference id on the row.
  assert "Resource temporarily unavailable" not in after.error_message


def test_a_worker_the_row_could_not_record_is_killed_before_the_retry(
    db_session, gda_client, manager
):
  """The spawn and the write to the row are two things that can fail.

  The claim already committed, so a write that fails leaves a RUNNING trial
  with a live process behind it and no PID on the row. Handing that trial
  straight back gave it a second worker: both ran the question and both billed
  the agent API. The process has to go first.
  """
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]

  # A PID no integer column will take, so the commit is what fails and the
  # spawn is left to have succeeded. The liveness check in front of the commit
  # is answered separately, because nothing is running at that PID and the
  # pass would otherwise stop there, on the branch for a child that died.
  ctx = _spawn_context(pid=2**40)

  with (
      mock.patch.object(
          worker.multiprocessing, "get_context", return_value=ctx
      ),
      mock.patch.object(worker, "_process_started_at", return_value=1.0),
  ):
    manager._start_new_trials()

  ctx.Process.return_value.terminate.assert_called_once()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert after.retry_count == 1
  assert after.trial_pid is None


def test_a_worker_that_will_not_die_keeps_the_trial_claimed(
    db_session, gda_client, manager
):
  """Pairs with the test above, for the child that takes neither signal.

  A worker inside a blocking GDA call does not take SIGTERM, and the outcome
  of the kill was thrown away, so the trial went back on the queue with its
  first process still asking the agent the question. It stays claimed instead,
  and the stale sweep collects it once the process has actually gone.
  """
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]
  ctx = _spawn_context(pid=2**40, survives_kill=True)

  with (
      mock.patch.object(
          worker.multiprocessing, "get_context", return_value=ctx
      ),
      mock.patch.object(worker, "_process_started_at", return_value=1.0),
  ):
    manager._start_new_trials()

  process = ctx.Process.return_value
  process.terminate.assert_called_once()
  process.kill.assert_called_once()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.retry_count == 0


def test_a_trial_that_completed_during_the_pass_is_not_clobbered(
    db_session, gda_client, manager, session_factory
):
  """The liveness pass acts on a list it read before the child finished.

  The status filter is applied once, in the SELECT. A trial that completed
  eighty milliseconds into the pass is still RUNNING in that snapshot, and the
  child's exit leaves a zombie the liveness check reads as dead. Resetting it
  here threw away an answer the agent had already been billed for.
  """
  trial = _claimed_trial(db_session, gda_client, started_minutes_ago=1)

  with session_factory() as pass_session:
    # What the manager is holding: the trial as it was at the top of the pass.
    snapshot = pass_session.get(run_models.Trial, trial.id)
    assert snapshot.status == execution.RunStatus.RUNNING

    # The child commits its result from its own session while the pass runs.
    trial.status = execution.RunStatus.COMPLETED
    trial.output_text = "42"
    trial.completed_at = datetime.datetime.now(datetime.timezone.utc)
    db_session.commit()

    manager._retry_or_fail(pass_session, snapshot, "Worker process crashed")

  after = _reread(db_session, trial)
  assert (
      after.status == execution.RunStatus.COMPLETED
  ), "A finished trial was reopened, so its run will execute it twice."
  assert after.output_text == "42", "The answer the run was billed for is gone."
  assert after.retry_count == 0
