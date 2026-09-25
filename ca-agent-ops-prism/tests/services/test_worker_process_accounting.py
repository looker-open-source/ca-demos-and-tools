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

"""What the manager knows about the children it spawned, and how it waits.

Two ways it lost track of one. A spawn whose PID could not be committed left
the trial claimed on purpose, but the rollback took the PID with it, so the row
said RUNNING with nothing recorded against it. Ten seconds of joins later the
liveness pass was past the PID grace period, read the trial as a worker that
never started and retried it, which spawned a second child onto a question the
first one was still asking the agent.

And the kill waited through psutil, which calls os.waitpid on what is our own
multiprocessing child. That reaps it behind multiprocessing's back: the handle
is never discarded from _children and the Finalize that closes the two parent
pipe descriptors never runs, so every killed trial cost a long lived server two
descriptors and an entry.
"""

import datetime
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
import sqlalchemy
from sqlalchemy import orm

# pylint: disable=protected-access

# The PID the fake spawn reports. Nothing is spawned, psutil is faked.
_PID = 4242

# The start time recorded beside that PID.
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
    db_session: orm.Session, gda_client, started_minutes_ago: int = 40
):
  """One trial the way the manager leaves it after spawning a worker."""
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
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
  proc.is_running.return_value = True
  proc.status.return_value = psutil.STATUS_RUNNING
  proc.create_time.return_value = created
  return proc


def _child_handle(alive_after_join: bool = False):
  """The multiprocessing handle for a child of ours sitting on _PID."""
  child = mock.MagicMock()
  child.pid = _PID
  child.is_alive.return_value = alive_after_join
  return child


def _spawn_context():
  """A context whose Process starts and then takes neither signal.

  is_alive is answered rather than left to MagicMock, which hands back a truthy
  mock and reads as a child that shrugged off SIGKILL either way.
  """
  ctx = mock.MagicMock()
  ctx.Process.return_value.pid = _PID
  ctx.Process.return_value.is_alive.return_value = True
  return ctx


def _factory_refusing_the_pid_commit(session_factory: orm.sessionmaker):
  """A factory whose first session will not commit the PID.

  The manager claims the trial and records the PID on one session, so the
  commit to refuse is the one carrying a Trial with a PID on it. Sessions
  opened after it commit normally, which is what the write the manager makes
  afterwards needs.
  """
  opened = []

  def open_session():
    session = session_factory()
    opened.append(session)
    if len(opened) > 1:
      return session

    real_commit = session.commit

    def commit():
      carries_pid = any(
          isinstance(obj, run_models.Trial) and obj.trial_pid is not None
          for obj in session.dirty
      )
      if carries_pid:
        raise sqlalchemy.exc.OperationalError(
            "COMMIT", {}, Exception("server closed the connection")
        )
      return real_commit()

    session.commit = commit
    return session

  return open_session


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def _spawn_a_worker_that_will_not_die(
    manager, session_factory, db_session, gda_client
):
  """Leaves the manager holding a claimed trial and a live process.

  The spawn works, the commit that records it does not, and neither SIGTERM nor
  SIGKILL lands. Returns the trial.
  """
  run = _running_run(db_session, gda_client)
  trial = run.trials[0]
  manager.session_factory = _factory_refusing_the_pid_commit(session_factory)

  with (
      mock.patch.object(
          worker.multiprocessing, "get_context", return_value=_spawn_context()
      ),
      mock.patch.object(worker.psutil, "Process", return_value=_process()),
  ):
    manager._start_new_trials()

  return trial


def test_a_worker_that_survived_the_kill_is_recorded_on_its_trial(
    db_session, gda_client, manager, session_factory
):
  """Leaving the trial claimed is worth nothing if the row says nothing.

  The rollback took the PID off the row, so the claim was all that was left and
  there was no way to tell later whether the process had gone. The PID goes
  back on from a session of its own.
  """
  trial = _spawn_a_worker_that_will_not_die(
      manager, session_factory, db_session, gda_client
  )

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert after.trial_pid == _PID, (
      "Without the PID the trial is claimed by nobody, and the next pass reads"
      " it as a worker that never started."
  )
  assert after.trial_pid_started_at == pytest.approx(_PID_STARTED_AT)


def test_the_surviving_worker_is_not_given_a_second_child_next_pass(
    db_session, gda_client, manager, session_factory
):
  """This is the double execution the branch above exists to prevent.

  The kill spends two joins of five seconds, so the trial is out of the PID
  grace period by the time the liveness pass reads it. A RUNNING trial with no
  PID is retried, and the retry spawned a second worker onto a question the
  first process was still asking the agent, billing for it twice.
  """
  trial = _spawn_a_worker_that_will_not_die(
      manager, session_factory, db_session, gda_client
  )

  # Where the joins leave it: well past the ten second grace period.
  claimed = _reread(db_session, trial)
  claimed.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(seconds=30)
  db_session.commit()

  with mock.patch.object(worker.psutil, "Process", return_value=_process()):
    manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING, (
      "The trial went back on the queue with its first process still running"
      " against the agent."
  )
  assert after.retry_count == 0


def test_a_child_of_ours_is_waited_on_through_its_own_handle(
    db_session, gda_client, manager
):
  """psutil's wait() reaps the child behind multiprocessing's back.

  It calls os.waitpid itself, so Popen.poll() afterwards gets
  ChildProcessError, returncode stays None, the handle is never discarded from
  multiprocessing's _children and the Finalize that closes the two parent pipe
  descriptors never runs. A server that had killed a few hundred trials was
  holding all of it.
  """
  trial = _claimed_trial(db_session, gda_client)
  proc = _process()
  child = _child_handle()

  with (
      mock.patch.object(worker.psutil, "Process", return_value=proc),
      mock.patch.object(
          worker.multiprocessing, "active_children", return_value=[child]
      ),
  ):
    manager._recover_stale_trials()

  proc.kill.assert_called_once()
  child.join.assert_called_once_with(timeout=5)
  assert (
      not proc.wait.called
  ), "psutil reaped our own child, so multiprocessing can never close it out."
  assert _reread(db_session, trial).status == execution.RunStatus.PENDING


def test_a_handle_still_alive_after_the_join_keeps_the_trial_claimed(
    db_session, gda_client, manager
):
  """Guards the change above: the join has a timeout and it means something.

  Reaching it says the process is still there, and freeing the row on that
  answer hands the trial to a second worker while the first is still writing
  it.
  """
  trial = _claimed_trial(db_session, gda_client)
  child = _child_handle(alive_after_join=True)

  with (
      mock.patch.object(worker.psutil, "Process", return_value=_process()),
      mock.patch.object(
          worker.multiprocessing, "active_children", return_value=[child]
      ),
  ):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.RUNNING
  assert (
      after.trial_pid == _PID
  ), "The PID is the only handle on the surviving process, so it has to stay."
