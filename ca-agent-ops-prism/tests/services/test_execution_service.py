import unittest.mock

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.server.clients.gemini_data_analytics_client import AskQuestionResponse
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


def test_create_run_service(db_session: Session):
  """Tests creating a run via execution service."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Execute Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")

  run = service.create_run(agent.id, suite.id)

  assert run.id is not None
  # Check if context snapshot was captured correctly (raw, no wrapping)
  assert run.agent_context_snapshot == {"system_instruction": "Test"}
  # project_id, location, etc are already in the run model itself, no need to duplicate in snapshot

  # Check if trials were created
  assert len(run.trials) == 1
  assert run.trials[0].example_snapshot.question == "Q1"


def test_execute_run_service(db_session: Session):
  """Tests executing a run loop."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  # Setup mock response
  response_mock = unittest.mock.MagicMock(spec=AskQuestionResponse)
  response_mock.protobuf_response = []
  response_mock.duration = unittest.mock.MagicMock(total_duration=123)
  response_mock.error_message = None
  mock_client.ask_question.return_value = response_mock

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
  )

  # Setup Data
  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Execute Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")

  run = service.create_run(agent.id, suite.id)

  # Execute trials manually for test
  for trial in run.trials:
    service.execute_trial(trial.id)

  # Verify Run
  db_session.refresh(run)
  assert len(run.trials) == 1
  trial = run.trials[0]
  assert trial.status == RunStatus.COMPLETED
  assert trial.duration_ms is not None
  assert trial.duration_ms >= 0

  mock_client.ask_question.assert_called_once()
  # Verify call args
  call_args = mock_client.ask_question.call_args[1]
  assert call_args["question"] == "Q1"
  assert call_args["agent_id"] == "projects/p/locations/l/dataAgents/r"


def test_execute_trial_failure(db_session: Session):
  """Tests that trial failure captures traceback and stage."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = unittest.mock.MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}
  # Simulate a crash during execution
  mock_client.ask_question.side_effect = Exception("Agent Explosion!")

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
  )

  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="Fail Bot", config=config)
  suite = suite_repo.create(name="Suite")
  example_repo.create(suite.id, "Q1")
  run = service.create_run(agent.id, suite.id)

  # Execute - this will raise the Exception because it's re-raised in
  # execute_trial
  try:
    service.execute_trial(run.trials[0].id)
  except Exception:  # pylint: disable=broad-exception-caught
    pass

  # Verify Trial state
  trial_repo = TrialRepository(db_session)
  trials = trial_repo.list_for_run(run.id)
  trial = trials[0]

  assert trial.status == RunStatus.FAILED
  assert trial.failed_stage == "EXECUTING"
  assert "Agent Explosion!" in trial.error_message
  assert "traceback" in trial.error_traceback.lower()
  assert "ask_question" in trial.error_traceback
