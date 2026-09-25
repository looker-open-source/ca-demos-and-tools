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

import unittest.mock
from google.cloud import geminidataanalytics
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.execution import RunStatus
from prism.server.clients.gemini_data_analytics_client import AskQuestionResponse
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_execute_trial_skips_suggestions_when_false(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}

  response_mock = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response_mock.protobuf_response = [
      geminidataanalytics.Message(system_message={"text": {"parts": ["Test"]}})
  ]
  response_mock.duration = unittest.mock.MagicMock(total_duration=123)
  response_mock.error_message = None
  mock_client.ask_question.return_value = response_mock

  mock_suggestion_service = unittest.mock.MagicMock()

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
      suggestion_service=mock_suggestion_service,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="No Sug Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")

  run = service.create_run(agent.id, suite.id, generate_suggestions=False)
  trial = run.trials[0]

  service.execute_trial(trial.id)

  # COMPLETED first. _execute_trial swallows everything into an except that
  # writes FAILED, so without this a trial that blew up before the suggestion
  # block satisfies the assertion below and the flag could be ignored outright.
  assert trial.status == RunStatus.COMPLETED
  mock_suggestion_service.suggest_assertions_from_trace.assert_not_called()


def test_execute_trial_generates_suggestions_when_true(db_session: Session):
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}

  response_items = [{"system_message": {"text": {"parts": ["Test Answer"]}}}]
  response_mock = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response_mock.response = response_items
  response_mock.protobuf_response = [
      geminidataanalytics.Message(system_message=r["system_message"])
      for r in response_items
  ]
  response_mock.duration = unittest.mock.MagicMock(total_duration=123)
  response_mock.error_message = None
  mock_client.ask_question.return_value = response_mock

  mock_suggestion_service = unittest.mock.MagicMock()
  mock_suggestion_service.suggest_assertions_from_trace.return_value = []

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
      suggestion_service=mock_suggestion_service,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Sug Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")

  run = service.create_run(agent.id, suite.id, generate_suggestions=True)
  trial = run.trials[0]

  service.execute_trial(trial.id)

  mock_suggestion_service.suggest_assertions_from_trace.assert_called_once()
