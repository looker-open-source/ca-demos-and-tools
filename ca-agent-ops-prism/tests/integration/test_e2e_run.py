"""End-to-end integration tests for Prism."""

import json
import os
from unittest.mock import MagicMock
from unittest.mock import patch

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import AgentEnv
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.assertion import ChartCheckType
from prism.common.schemas.assertion import DataCheckRow
from prism.common.schemas.assertion import DataCheckRowCount
from prism.common.schemas.assertion import DurationMaxMs
from prism.common.schemas.assertion import LookerQueryMatch
from prism.common.schemas.assertion import QueryContains
from prism.common.schemas.assertion import TextContains
from prism.server.clients.gemini_data_analytics_client import AskQuestionResponse
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.models.run import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.snapshot_service import SnapshotService
from sqlalchemy.orm import Session


class MockProtoMessage:
  """Helper to mock a proto-plus message wrapper."""

  def __init__(self, data_dict):
    self._data_dict = data_dict
    for k, v in data_dict.items():
      if isinstance(v, dict):
        setattr(self, k, MockProtoMessage(v))
      else:
        setattr(self, k, v)

    # Mock _pb for ExecutionService
    self._pb = MagicMock()
    # expose data_dict for the patch
    self._pb.data_dict = data_dict

  def __contains__(self, key):
    return key in self._data_dict

  def __getitem__(self, key):
    return self._data_dict[key]

  def __iter__(self):
    return iter(self._data_dict)

  def keys(self):
    return self._data_dict.keys()

  def values(self):
    return self._data_dict.values()

  def items(self):
    return self._data_dict.items()

  def to_dict(self):
    """Support for type(msg).to_dict(msg) usage."""
    return self._data_dict

  def get(self, key, default=None):
    return self._data_dict.get(key, default)


def load_mock_response(filename: str) -> list[dict]:
  """Loads a mock response from the data directory."""
  base_path = os.path.dirname(__file__)
  file_path = os.path.join(base_path, "data", filename)
  with open(file_path, "r", encoding="utf-8") as f:
    return json.load(f)


def test_successful_run_flow(db_session: Session):
  """Tests a complete run flow with successful assertions."""
  # 1. Setup Services and Repos
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)

  mock_client = MagicMock(spec=GeminiDataAnalyticsClient)
  mock_client.get_agent_context.return_value = {"system_instruction": "Test"}

  mock_gen_ai_client = MagicMock(spec=GenAIClient)

  service = ExecutionService(
      db_session,
      snapshot_service,
      mock_client,
      gen_ai_client=mock_gen_ai_client,
  )

  # 2. Setup Database Entities
  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      env=AgentEnv.STAGING,
      datasource=BigQueryConfig(tables=["t1"]),
  )
  agent = agent_repo.create(name="E2E Agent", config=config)
  suite = suite_repo.create(name="Revenue Suite")

  # Create Example with Assertions
  # Use Pydantic models for assertions

  example_input = {
      "question": "What is the revenue?",
      "asserts": [
          # Expected to PASS
          TextContains(value="revenue"),
          DurationMaxMs(value=5000),
          QueryContains(value="SELECT *"),
          ChartCheckType(value="bar"),
          DataCheckRowCount(value=2),
          DataCheckRow(columns={"col": "val"}),
          LookerQueryMatch(params={"model": "the_model"}),
          # Expected to FAIL
          TextContains(value="this should fail"),
          DurationMaxMs(value=1),
          QueryContains(value="DELETE FROM"),
          ChartCheckType(value="line"),
          DataCheckRowCount(value=99),
          DataCheckRow(columns={"col": "does_not_exist"}),
          LookerQueryMatch(params={"model": "wrong_model"}),
      ],
  }
  # We need to manually add assertions since ExampleRepository.create might take just a question
  # But ExampleRepository.create signature is (suite_id, question, ...)
  # Let's check ExampleRepository.update or just use create then update if needed
  # Assuming create returns the example
  example = example_repo.create(suite.id, example_input["question"])
  # Now add assertions individually
  for assertion in example_input["asserts"]:
    example_repo.add_assertion(example.id, assertion)

  # 3. Prepare Mock Data
  trace_data = load_mock_response("success_response.json")

  # Construct response object
  # specific mocking to bypass json_format.MessageToDict
  # We patch json_format.MessageToDict in the ExecutionService scope essentially by
  # ensuring the objects in protobuf_response work with it, OR we patch the library.
  # A robust integration test might prefer patching the library to avoid complex Proto mocking.

  with patch("google.protobuf.json_format.MessageToDict") as mock_to_dict:
    # Configure mock_to_dict to return the dict for our fake protos
    # The side_effect returns the .data attribute of our MockProtoMessage
    mock_to_dict.side_effect = (
        lambda pb, **kwargs: pb.data_dict if hasattr(pb, "data_dict") else pb
    )

    response_messages = []
    for item in trace_data:
      msg = MockProtoMessage(item)
      # Hack to attach valid data for our patched MessageToDict
      msg._pb.data_dict = item
      response_messages.append(msg)

    response_mock = MagicMock(spec=AskQuestionResponse)
    response_messages = []
    for item in trace_data:
      msg = MockProtoMessage(item)
      # Hack to attach valid data for our patched MessageToDict
      msg._pb.data_dict = item
      response_messages.append(msg)

    response_mock.protobuf_response = response_messages
    response_mock.error_message = None
    # response_mock.duration is expected to be a Duration-like object
    # It needs a total_duration attribute (int ms)
    response_mock.duration = MagicMock()
    response_mock.duration.total_duration = 100

    mock_client.ask_question.return_value = response_mock

    # 4. Execute Run
    run = service.create_run(agent.id, suite.id)
    for trial in run.trials:
      service.execute_trial(trial.id)

    # 5. Verify Results
    db_session.refresh(run)
    assert len(run.trials) == 1
    trial = run.trials[0]

    assert trial.status == RunStatus.COMPLETED
    assert trial.duration_ms is not None
    assert trial.duration_ms >= 0

    # Check Assertions
    # We expect 2 passed assertions
    assert len(trial.assertion_results) == 14
    passed_count = sum(1 for res in trial.assertion_results if res.passed)
    failed_count = sum(1 for res in trial.assertion_results if not res.passed)
    # Debug print failed assertions
    if passed_count != 7:
      print("\n\n=== DEBUGGING FAILED ASSERTIONS ===")
      for res in trial.assertion_results:
        if not res["passed"]:
          # Print assertion type and value for clarity
          print(f"FAILED: {res['assertion']['type']} - {res['reason']}")
      print("===================================\n")
    assert passed_count == 7
    assert failed_count == 7
