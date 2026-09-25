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

"""What a failed trial is allowed to say on the trial detail page.

prism has no authentication of its own, so this page is readable by anyone who
can reach the port and it lands in the screenshots attached to bugs. The trial
row used to store str(e) and traceback.format_exc(), and the page rendered
both. A GDA error names the project, the dataAgents path, the Looker instance
and the caller service account. The traceback adds the container's filesystem
layout and the installed library versions.

What is stored now is a short description of the failure and a reference id.
The id is the only thing tying the page to the server log, so these check it is
there and that it is the same id the log line carries.
"""

from __future__ import annotations

import logging
import re
import unittest.mock

from google.api_core import exceptions as api_exceptions
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.components import cards
import pytest
from sqlalchemy.orm import Session

_REFERENCE_ID = re.compile(r"\(ref ([0-9a-f]{6})\)")


def _run_one_failing_trial(db_session: Session, error: Exception):
  """Runs a single trial whose agent call raises, and returns the trial."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  mock_client.ask_question.side_effect = error

  service = ExecutionService(db_session, snapshot_service, mock_client)

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Leaky Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  run = service.create_run(agent.id, suite.id)

  return service.execute_trial(run.trials[0].id)


def test_a_gcp_failure_stores_the_status_and_not_the_servers_detail_blob(
    db_session: Session, caplog: pytest.LogCaptureFixture
):
  """A denied ask_question carries the service account that was refused.

  GoogleAPICallError renders its details along with its message, and that is
  where the caller identity and the resource path sit. Only the status and the
  message survive onto the trial; the details stay in the log line the
  reference id points at.
  """
  error = api_exceptions.PermissionDenied(
      "Permission denied on data agent.",
      details=["caller: prism-runner@secret-project.iam.gserviceaccount.com"],
  )

  with caplog.at_level(logging.ERROR):
    trial = _run_one_failing_trial(db_session, error)

  assert trial.status == RunStatus.FAILED
  assert trial.failed_stage == "EXECUTING"
  assert "prism-runner@secret-project" not in trial.error_message
  assert trial.error_traceback is None

  match = _REFERENCE_ID.search(trial.error_message)
  assert match, f"No reference id in {trial.error_message!r}"
  # The page is only useful if the id finds the log line that has the rest.
  assert match.group(1) in caplog.text


def test_a_failure_inside_prism_stores_its_type_and_nothing_else(
    db_session: Session,
):
  """Not every trial failure is a GCP call.

  A SQLAlchemy error carries the statement and its bound parameters, which is
  the question text and the snapshot ids. Anything that is not a GCP error is
  named by its type alone.
  """
  error = RuntimeError(
      "UPDATE trials SET output_text=%(output_text)s -- 'salary of user 42'"
  )

  trial = _run_one_failing_trial(db_session, error)

  assert trial.status == RunStatus.FAILED
  assert "RuntimeError" in trial.error_message
  assert "salary of user 42" not in trial.error_message
  assert trial.error_traceback is None


def test_the_error_card_does_not_render_a_stored_traceback():
  """Trials that failed before this changed still have one on the row.

  The card is handed whatever is there and has to drop it, so an old trial
  stops leaking as soon as the page is redeployed.
  """
  card = cards.render_error_card(
      message="PermissionDenied raised while running this trial. (ref abc123)",
      traceback_str=(
          'Traceback (most recent call last):\n  File "/opt/prism/src/prism/'
          'server/services/execution_service.py", line 240, in _execute_trial'
      ),
      stage="EXECUTING",
  )

  rendered = str(card)
  assert "/opt/prism/src/prism" not in rendered
  assert "Traceback" not in rendered
  assert "(ref abc123)" in rendered
  assert "in the server log" in rendered
