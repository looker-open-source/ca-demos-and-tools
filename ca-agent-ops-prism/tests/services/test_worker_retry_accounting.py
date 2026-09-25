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

"""Retries are counted, spent once a pass, and clear what the last one left.

Three separate ways the count was wrong. Stale recovery reset the row to
PENDING by hand and spent no retry, so a trial that wedged the same way every
time came back for ever: its run never reached a terminal status, and
promote_next_run will not promote past a run that is still going, so
everything queued behind it waited too. A spawn failure went on to the next
turn of the claim loop, and pick_next_pending_trial orders by id, so the loop
picked the same trial again and one pass burned all three of its retries. And
the reset left failed_stage and suggested_asserts on the row, so the trial page
captioned a retry with the stage the first attempt died in and the suggestions
panel offered assertions written against an answer that had been thrown away.
"""

import datetime
import errno
import os
from unittest import mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.common.schemas.assertion import AssertionType
from prism.server.models.assertion import SuggestedAssertion
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


@pytest.fixture(name="answering_client")
def _answering_client():
  """A GDA client whose answer is empty but well formed, so the trial passes."""
  client = mock.MagicMock()
  client.get_agent_context.return_value = {"sys": "test"}
  response = mock.MagicMock()
  response.protobuf_response = []
  response.error_message = None
  client.ask_question.return_value = response
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


def _exec_service(db_session: orm.Session, client) -> ExecutionService:
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  return ExecutionService(
      db_session,
      snap_service,
      client,
      # Passed in so the empty assertion pass does not build a real one.
      gen_ai_client=mock.MagicMock(),
  )


def _running_run(db_session: orm.Session, client, *questions: str, **kwargs):
  """A RUNNING run with one PENDING trial per question."""
  exec_service = _exec_service(db_session, client)
  agent = _agent(db_session)
  suite = _suite(db_session, *questions)

  run = exec_service.create_run(agent.id, suite.id, **kwargs)
  run.status = execution.RunStatus.RUNNING
  db_session.commit()
  return run


def _stale_trial(db_session: orm.Session, gda_client, retry_count: int = 0):
  """A trial claimed forty minutes ago, which is past the 30 minute timeout."""
  run = _running_run(db_session, gda_client, "Q1", concurrency=1)
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
  trial.started_at = datetime.datetime.now(
      datetime.timezone.utc
  ) - datetime.timedelta(minutes=40)
  trial.trial_pid = _PID
  trial.trial_pid_started_at = _PID_STARTED_AT
  trial.retry_count = retry_count
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


def _spawn_context(side_effect=None, pid: int = _PID):
  """A multiprocessing context whose Process fails, or pretends to start."""
  ctx = mock.MagicMock()
  process = ctx.Process.return_value
  # An integer, because psutil is handed this and a MagicMock blows up inside
  # it.
  process.pid = pid
  process.start.side_effect = side_effect
  return ctx


def _add_suggestion(db_session: orm.Session, trial, value: str):
  """One suggestion of the kind the last attempt's answer produced."""
  db_session.add(
      SuggestedAssertion(
          trial_id=trial.id,
          type=AssertionType.TEXT_CONTAINS,
          weight=1.0,
          params={"value": value},
      )
  )
  db_session.commit()


def _stored_suggestions(db_session: orm.Session, trial_id: int) -> list[str]:
  db_session.expire_all()
  rows = (
      db_session.query(SuggestedAssertion)
      .filter(SuggestedAssertion.trial_id == trial_id)
      .order_by(SuggestedAssertion.id)
      .all()
  )
  return [row.params["value"] for row in rows]


def _reread(db_session: orm.Session, row):
  """Reads a row back after the manager committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(type(row), row.id)


def test_a_stale_trial_spends_one_of_its_retries(
    db_session, gda_client, manager
):
  """Recovery used to hand the row straight back to PENDING and count nothing.

  A trial that wedges the same way every time then recovers for ever. Its run
  never reaches a terminal status, and promote_next_run will not promote past
  a run that is still going, so the whole queue behind it stops.
  """
  trial = _stale_trial(db_session, gda_client)

  with mock.patch.object(worker.psutil, "Process", return_value=_process()):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.PENDING
  assert (
      after.retry_count == 1
  ), "A recovery that costs nothing lets one wedged trial loop for ever."


def test_a_stale_trial_out_of_retries_is_failed_not_requeued(
    db_session, gda_client, manager
):
  """Counting the retries only helps if the last one ends it.

  The trial is terminal, so the run can finish and the next one can be
  promoted.
  """
  trial = _stale_trial(db_session, gda_client, retry_count=3)

  with mock.patch.object(worker.psutil, "Process", return_value=_process()):
    manager._recover_stale_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.FAILED
  assert "made no progress" in after.error_message


def test_a_retried_trial_drops_the_stage_and_suggestions_of_the_last_attempt(
    db_session, gda_client, manager
):
  """Both of these outlived the reset the manager does before a retry.

  The trial page captions its error card with failed_stage, so a retry showed
  the stage the first attempt died in. The suggestions panel offered
  assertions written against an answer that had already been thrown away.
  """
  run = _running_run(db_session, gda_client, "Q1", concurrency=1)
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
  trial.failed_stage = "EVALUATING"
  trial.error_message = "the last attempt"
  db_session.commit()
  _add_suggestion(db_session, trial, "revenue")

  manager._retry_or_fail(db_session, trial, "Worker process crashed")

  assert trial.status == execution.RunStatus.PENDING
  assert (
      trial.failed_stage is None
  ), "The retry is captioned with the stage the attempt before it died in."
  assert not _stored_suggestions(
      db_session, trial.id
  ), "The suggestions were written against an answer that no longer exists."


def test_a_re_executed_trial_drops_them_too(db_session, answering_client):
  """The same two fields, cleared at the other end of the retry.

  ExecutionService resets the row when the worker picks the trial back up, and
  a field it misses survives the retry just as well as one the manager misses.
  """
  run = _running_run(db_session, answering_client, "Q1", concurrency=1)
  trial = run.trials[0]
  trial.failed_stage = "EXECUTING"
  db_session.commit()
  _add_suggestion(db_session, trial, "revenue")

  service = _exec_service(db_session, answering_client)
  service.execute_trial(trial.id)

  # COMPLETED first. _execute_trial swallows everything into an except that
  # writes FAILED, so without this a trial that blew up early still satisfies
  # the two assertions below.
  assert trial.status == execution.RunStatus.COMPLETED
  assert trial.failed_stage is None
  assert not _stored_suggestions(db_session, trial.id)


def test_one_spawn_failure_costs_one_retry_not_all_three(
    db_session, gda_client, manager
):
  """The claim loop used to carry on to the next trial after a failed spawn.

  _retry_or_fail puts the trial back to PENDING and pick_next_pending_trial
  orders by id, so the next turn picked the same trial again. A machine that
  could not fork for a few seconds spent every retry the first trial had in a
  single pass, and the trials behind it were never looked at.
  """
  run = _running_run(db_session, gda_client, "Q1", "Q2", "Q3", concurrency=3)
  first, second, third = run.trials

  with mock.patch.object(
      worker.multiprocessing,
      "get_context",
      return_value=_spawn_context(side_effect=_EAGAIN),
  ):
    manager._start_new_trials()

  after = _reread(db_session, first)
  assert after.status == execution.RunStatus.PENDING
  assert (
      after.retry_count == 1
  ), "One pass, one attempt. Three means the pass kept reclaiming this trial."
  for trial in (second, third):
    assert _reread(db_session, trial).retry_count == 0
