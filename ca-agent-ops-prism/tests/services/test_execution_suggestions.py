import unittest.mock
from google.cloud import geminidataanalytics
from prism.common.schemas.agent import AgentConfig, BigQueryConfig
from prism.server.clients.gemini_data_analytics_client import AskQuestionResponse, GeminiDataAnalyticsClient
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_execute_trial_skips_suggestions_when_false(db_session: Session):
  """Tests that suggestions are NOT generated when generate_suggestions is False."""
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

  # Mock suggestion service
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

  # Create run with generate_suggestions=False (default)
  run = service.create_run(agent.id, suite.id, generate_suggestions=False)
  trial = run.trials[0]

  # Execute
  service.execute_trial(trial.id)

  # Verify suggestion service NOT called
  mock_suggestion_service.suggest_assertions_from_trace.assert_not_called()


def test_execute_trial_generates_suggestions_when_true(db_session: Session):
  """Tests that suggestions ARE generated when generate_suggestions is True."""
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

  # Mock suggestion service
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

  # Create run with generate_suggestions=True
  run = service.create_run(agent.id, suite.id, generate_suggestions=True)
  trial = run.trials[0]

  # Execute
  service.execute_trial(trial.id)

  # Verify suggestion service WAS called
  mock_suggestion_service.suggest_assertions_from_trace.assert_called_once()
