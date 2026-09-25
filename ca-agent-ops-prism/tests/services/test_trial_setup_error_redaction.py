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

"""What a setup failure is allowed to say on the trial detail page.

prism has no authentication of its own, so the page is readable by anyone who
can reach the port and it lands in the screenshots attached to bugs.
_fail_trial_during_setup stored str(error) and the full traceback. Setup is
where the credential, the location and the client construction failures happen,
so it was the writer whose exceptions carried the most: the project, the
dataAgents path and the service account that was refused.

It goes through the same sanitiser ExecutionService uses now, and stores a
reference id instead of the traceback. tests/services/test_trial_error_redaction
covers the ExecutionService half. These cover the worker half, where the
exception text is the config the user got wrong.
"""

import logging
import re
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
import pytest
from sqlalchemy import orm

_REFERENCE_ID = re.compile(r"\(ref ([0-9a-f]{6})\)")

# The caller identity and the resource path, which is what a refused setup
# comes back carrying.
_SERVICE_ACCOUNT = "prism-runner@secret-project.iam.gserviceaccount.com"
_RESOURCE_PATH = (
    "projects/secret-project/locations/us-central1/dataAgents/sales"
)

_SETUP_ERROR = RuntimeError(
    f"403 Permission denied on {_RESOURCE_PATH} for {_SERVICE_ACCOUNT}"
)


@pytest.fixture(name="trial")
def _trial(db_session: orm.Session) -> run_models.Trial:
  """One claimed trial, the way the manager leaves it before spawning."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
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


@pytest.fixture(name="child_logging_left_alone")
def _child_logging_left_alone():
  """Keeps execute_trial from tearing down the handler caplog is reading.

  execute_trial configures logging for the spawned child it usually runs in,
  with force=True, and that removes every handler already on the root logger.
  Nothing is spawned here, so there is nothing to configure.
  """
  with mock.patch.object(worker.logging, "basicConfig"):
    yield


def _reread(db_session: orm.Session, trial: run_models.Trial):
  """Reads the trial back after the worker committed from its own session."""
  db_session.commit()
  db_session.expire_all()
  return db_session.get(run_models.Trial, trial.id)


def test_a_setup_failure_keeps_the_caller_and_the_resource_off_the_trial(
    db_session, trial, broken_setup
):
  """str(error) put both on a page with nothing in front of it.

  What is left names the exception type, which is as much as the page needs to
  say that this was not the agent getting the question wrong.
  """
  worker.execute_trial(trial.id)

  after = _reread(db_session, trial)
  assert after.status == execution.RunStatus.FAILED
  assert _SERVICE_ACCOUNT not in after.error_message
  assert "secret-project" not in after.error_message
  assert "dataAgents" not in after.error_message
  assert "RuntimeError" in after.error_message


def test_a_setup_failure_stores_no_traceback(db_session, trial, broken_setup):
  """The traceback adds the filesystem layout and the library versions.

  It was rendered on the trial page along with the message.
  """
  worker.execute_trial(trial.id)

  assert _reread(db_session, trial).error_traceback is None


def test_the_reference_id_on_the_trial_finds_the_log_line(
    db_session,
    trial,
    broken_setup,
    child_logging_left_alone,
    caplog: pytest.LogCaptureFixture,
):
  """The id is the only thing tying the page to the detail that was dropped.

  Without it the page says a RuntimeError happened and there is no way to find
  out which one.
  """
  del child_logging_left_alone  # Keeps caplog's handler on the root logger.
  with caplog.at_level(logging.ERROR):
    worker.execute_trial(trial.id)

  message = _reread(db_session, trial).error_message
  match = _REFERENCE_ID.search(message)
  assert match, f"No reference id in {message!r}"
  assert (
      match.group(1) in caplog.text
  ), "The id on the page does not appear in the log, so it finds nothing."
  # The log line is the half that keeps the detail.
  assert _SERVICE_ACCOUNT in caplog.text
