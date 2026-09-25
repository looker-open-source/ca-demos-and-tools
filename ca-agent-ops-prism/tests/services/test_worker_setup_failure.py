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

"""What a trial says when the worker dies before execution starts.

The child process builds the agent lookup and two clients before it hands the
trial to ExecutionService. ExecutionService records its own failures. That
setup did not, so a wrong location or a missing credential exited the process
with nothing written down. The manager saw a dead PID and retried three times,
and each retry cleared the trial, before settling on "Worker process crashed".

The trial carries the failure now. It goes through the same sanitiser
ExecutionService uses, so the row gets the exception type and a reference id,
and the message and the traceback stay in the log under that id. These tests
pin the trial being failed and labelled, pin what the row is allowed to say,
and pin the retries not happening.
"""

import logging
import re
from typing import Any
import unittest.mock as mock

from prism.common.schemas import execution
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server import db
from prism.server.models import run as run_models
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services import worker
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.server.services.worker import WorkerProcessManager
import pytest
from sqlalchemy import orm

# What a bad location or an expired credential looks like from here.
_SETUP_ERROR = RuntimeError("403 Permission denied on location us-central1")

# The reference id the handler appends to the message it stores.
_REFERENCE_ID = re.compile(r"\(ref ([0-9a-f]{6})\)")


@pytest.fixture(name="manager")
def _manager(session_factory: orm.sessionmaker):
  """The manager, reset either side because it is a singleton.

  Reset on the way out as well, or this one stays bound to a session factory
  whose tables are dropped at teardown and dependencies.get_worker_pool_service
  hands it to whichever test runs next.
  """
  WorkerProcessManager._instance = None
  yield WorkerProcessManager(session_factory=session_factory)
  WorkerProcessManager._instance = None


@pytest.fixture(name="trial")
def _trial(db_session: orm.Session) -> run_models.Trial:
  """One claimed trial, the way the manager leaves it before spawning."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  # create_run stores whatever the client reports as the agent's context, and
  # the column is JSON.
  client = mock.MagicMock()
  client.get_agent_context.return_value = {"sys": "test"}
  exec_service = ExecutionService(db_session, snap_service, client)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=BigQueryConfig(tables=["t"]),
      ),
  )
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  db_session.commit()

  run = exec_service.create_run(agent.id, suite.id)
  run.status = execution.RunStatus.RUNNING
  trial = run.trials[0]
  trial.status = execution.RunStatus.RUNNING
  trial.trial_pid = 424242
  db_session.commit()
  return trial


@pytest.fixture(name="broken_setup")
def _broken_setup():
  """The GDA client refuses to build, which is what a bad config does."""
  with mock.patch.object(
      worker.gemini_data_analytics_client,
      "GeminiDataAnalyticsClient",
      side_effect=_SETUP_ERROR,
  ):
    yield


@pytest.fixture(name="gda_client")
def _gda_client():
  """A GDA client that answers, so the trial runs to completion."""
  with mock.patch.object(
      worker.gemini_data_analytics_client, "GeminiDataAnalyticsClient"
  ) as client_class:
    client = client_class.return_value
    client.get_agent_context.return_value = {"sys": "test"}
    response = mock.MagicMock()
    response.protobuf_response = []
    response.duration = mock.MagicMock(total_duration=50)
    response.error_message = None
    client.ask_question.return_value = response
    yield client


@pytest.fixture(name="captured_logs")
def _captured_logs(caplog: pytest.LogCaptureFixture):
  """caplog, kept alive across execute_trial's own logging setup.

  The child entry point calls logging.basicConfig with force=True, which
  removes and closes every handler on the root logger. In a spawned child
  there is nothing there to remove. Here there is, caplog's handler included,
  so without this the log line the reference id points at is never captured.
  """
  with mock.patch.object(worker.logging, "basicConfig"):
    with caplog.at_level(logging.ERROR):
      yield caplog


def _reread(db_session: orm.Session, trial: run_models.Trial):
  """Reads the trial back after the worker committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(run_models.Trial, trial.id)


def test_a_client_that_will_not_build_fails_the_trial(
    db_session, trial, broken_setup
):
  """It used to exit RUNNING and wait for the manager to notice."""
  worker.execute_trial(trial.id)

  assert _reread(db_session, trial).status == execution.RunStatus.FAILED


def test_the_trial_names_the_failure_and_not_its_text(
    db_session, trial, broken_setup, captured_logs
):
  """ "Worker process crashed" sent the reader to the Prism logs.

  What the row says now is the exception type and a reference id. Setup is
  where the credential and location failures happen, so the text of the error
  is the one thing it must not repeat onto a page with no authentication in
  front of it.
  """
  worker.execute_trial(trial.id)

  message = _reread(db_session, trial).error_message
  assert "RuntimeError" in message
  assert "crashed" not in message
  assert "Permission denied" not in message
  assert "us-central1" not in message

  match = _REFERENCE_ID.search(message)
  assert match, f"No reference id in {message!r}"
  # The page is only useful if the id finds the log line that has the rest.
  assert match.group(1) in captured_logs.text


def test_the_traceback_stays_in_the_log(
    db_session, trial, broken_setup, captured_logs
):
  """It used to be on the row, and the error card rendered it.

  It names the container's filesystem layout and the installed library
  versions. The log line under the same reference id keeps it.
  """
  worker.execute_trial(trial.id)

  after = _reread(db_session, trial)
  assert after.error_traceback is None

  ref = _REFERENCE_ID.search(after.error_message).group(1)
  assert f"(ref {ref})" in captured_logs.text
  assert "Traceback (most recent call last)" in captured_logs.text


def test_the_failure_stage_says_setup(db_session, trial, broken_setup):
  """Trial detail reads it as "Failed during SETUP".

  Every other stage on that card comes from ExecutionService, which never ran.
  """
  worker.execute_trial(trial.id)

  assert _reread(db_session, trial).failed_stage == "SETUP"


@pytest.mark.parametrize(
    "status",
    [execution.RunStatus.EXECUTING, execution.RunStatus.EVALUATING],
)
def test_a_failure_past_setup_keeps_the_stage_it_died_in(
    db_session: orm.Session, trial: run_models.Trial, status
):
  """The except this handler runs under covers execution as well as setup.

  So an exception that got past ExecutionService's own handling arrives here
  too, and SETUP went on unconditionally. That captioned the error card with
  the wrong stage and sent whoever read it looking at credentials for a trial
  that had died scoring assertions. RUNNING is the status the claim leaves,
  so it is the only one that means the child never reached execution.
  """
  trial.status = status
  db_session.commit()

  worker._fail_trial_during_setup(trial.id, _SETUP_ERROR, "abc123")

  after = _reread(db_session, trial)
  assert after.failed_stage == status.value
  assert after.status == execution.RunStatus.FAILED


def test_the_trial_is_finished_not_still_running(
    db_session, trial, broken_setup
):
  """Without a completion time the trial shows an open-ended duration."""
  worker.execute_trial(trial.id)

  assert _reread(db_session, trial).completed_at is not None


def test_the_manager_does_not_retry_a_setup_failure(
    db_session, trial, broken_setup, manager
):
  """Setup fails the same way every time, so four attempts bought nothing.

  Worse, _retry_or_fail nulls the trial's output and hard-deletes its assertion
  results on the way past, so the retries also threw away the evidence.
  """
  worker.execute_trial(trial.id)

  # The PID on the trial belongs to nothing, which is what the manager used to
  # act on.
  manager._check_active_trials()

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.FAILED
  assert after.retry_count == 0
  assert "retries" not in after.error_message


def test_the_run_finishes_instead_of_sitting_running(
    db_session, trial, broken_setup, manager
):
  """A run is done when every trial is done, and now the trial is done.

  It used to take three retry cycles for the run to reach that point.
  """
  worker.execute_trial(trial.id)

  manager._aggregate_run_statuses()

  db_session.commit()
  db_session.expire_all()
  run = db_session.get(run_models.Run, trial.run_id)
  assert run.status == execution.RunStatus.COMPLETED


def test_a_trial_that_no_longer_exists_is_not_an_error(session_factory):
  """Deleting a run while its trials are in flight is allowed.

  The handler runs in the child's except block, so raising here would bury the
  setup failure under a second exception nobody can read.
  """
  del session_factory  # For the tables.
  # Third argument is the reference id, six hex characters out of a uuid4.
  worker._fail_trial_during_setup(999999, _SETUP_ERROR, "abc123")

  with db.SessionLocal() as session:
    assert session.get(run_models.Trial, 999999) is None


def test_a_trial_that_ran_is_not_labelled_a_setup_failure(
    db_session: orm.Session, trial: run_models.Trial, gda_client: Any
):
  """The handler only fires on the way out, so success has to be untouched."""
  worker.execute_trial(trial.id)

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.COMPLETED
  assert after.failed_stage is None
  assert after.error_message is None


def test_the_worker_writes_through_its_own_session(db_session, trial):
  """The session the setup failed in is already closed by then.

  Reusing it would leave the failure unrecorded for the case that matters
  most, a database error, so the handler opens a new one.
  """
  with mock.patch.object(db, "SessionLocal", wraps=db.SessionLocal) as factory:
    with mock.patch.object(
        worker.gemini_data_analytics_client,
        "GeminiDataAnalyticsClient",
        side_effect=_SETUP_ERROR,
    ):
      worker.execute_trial(trial.id)

  assert factory.call_count == 2
