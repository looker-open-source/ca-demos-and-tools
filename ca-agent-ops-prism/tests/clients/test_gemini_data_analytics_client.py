"""Unit tests for GeminiDataAnalyticsClient."""

from unittest import mock

from google.cloud import geminidataanalytics
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest


@pytest.fixture
def mock_gemini_lib():
  """Mocks the geminidataanalytics library."""
  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.geminidataanalytics"
  ) as mock_lib:
    yield mock_lib


@pytest.fixture
def mock_auth():
  """Mocks google.auth.default."""
  with mock.patch("google.auth.default") as mock_auth_default:
    mock_auth_default.return_value = (None, "test-project")
    yield mock_auth_default


@pytest.fixture
def mock_json_format():
  """Mocks json_format.MessageToDict."""
  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.json_format.MessageToDict"
  ) as mock_proto_to_dict:
    # return a simple dict
    mock_proto_to_dict.return_value = {"mock_key": "mock_val"}
    yield mock_proto_to_dict


@pytest.fixture
def client(mock_gemini_lib, mock_auth):
  """Creates a GeminiDataAnalyticsClient instance with mocks."""
  return GeminiDataAnalyticsClient(
      project="projects/test-project/locations/us-central1",
  )


def make_mock_agent_pb(
    resource_id="agent-123",
    display_name="Test Agent",
    sys_instruct="instruction",
):
  """Helper to create a mock DataAgent protobuf."""
  mock_pb = mock.Mock()
  mock_pb.name = (
      f"projects/test-project/locations/us-central1/dataAgents/{resource_id}"
  )
  mock_pb.display_name = display_name

  # Context
  mock_context = mock.Mock()
  mock_context.system_instruction = sys_instruct
  mock_context.datasource_references = None  # Simplest case

  mock_da = mock.Mock()
  mock_da.published_context = mock_context
  mock_pb.data_analytics_agent = mock_da

  return mock_pb


def test_init(client, mock_gemini_lib):
  """Tests initialization."""
  assert client.project == "projects/test-project/locations/us-central1"
  mock_gemini_lib.DataChatServiceClient.assert_called_once()
  mock_gemini_lib.DataAgentServiceClient.assert_called_once()


def test_list_agents(client):
  """Tests list_agents."""
  mock_pager = [
      make_mock_agent_pb("agent-1"),
      make_mock_agent_pb("agent-2"),
  ]
  client.agent_client.list_data_agents.return_value = mock_pager

  agents = client.list_agents()

  assert len(agents) == 2
  assert isinstance(agents[0], AgentBase)
  assert agents[0].config.agent_resource_id == "agent-1"
  assert agents[1].config.agent_resource_id == "agent-2"
  client.agent_client.list_data_agents.assert_called_once()


def test_create_agent(client, mock_gemini_lib):
  """Tests create_agent."""
  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="new-agent",
      system_instruction="desc",
      datasource=BigQueryConfig(tables=["p.d.t"]),
  )

  mock_operation = mock.Mock()
  mock_operation.result.return_value = make_mock_agent_pb(
      "new-agent", "Test Agent"
  )
  client.agent_client.create_data_agent.return_value = mock_operation

  created_agent = client.create_agent(display_name="Test Agent", config=config)

  assert isinstance(created_agent, AgentBase)
  assert created_agent.config.agent_resource_id == "new-agent"

  client.agent_client.create_data_agent.assert_called_once()
  # Verify BQ datasource construction
  mock_gemini_lib.BigQueryTableReference.assert_called_with(
      project_id="p", dataset_id="d", table_id="t"
  )
  mock_gemini_lib.Context.assert_called()


def test_get_agent(client):
  """Tests get_agent."""
  mock_agent = make_mock_agent_pb("agent-123")
  client.agent_client.get_data_agent.return_value = mock_agent

  agent = client.get_agent("agents/agent-123")

  assert isinstance(agent, AgentBase)
  assert agent.config.agent_resource_id == "agent-123"
  client.agent_client.get_data_agent.assert_called_once()


def test_update_agent(client, mock_gemini_lib):
  """Tests update_agent."""
  mock_existing = make_mock_agent_pb("agent-123", sys_instruct="old")
  client.agent_client.get_data_agent.return_value = mock_existing

  mock_operation = mock.Mock()
  mock_operation.result.return_value = make_mock_agent_pb(
      "agent-123", sys_instruct="new desc"
  )
  client.agent_client.update_data_agent.return_value = mock_operation

  updated_agent = client.update_agent(
      "agents/agent-123", system_instruction="new desc"
  )

  assert isinstance(updated_agent, AgentBase)
  assert updated_agent.config.system_instruction == "new desc"

  client.agent_client.get_data_agent.assert_called_once()
  client.agent_client.update_data_agent.assert_called_once()
  # Verify Context called with new instruction
  # Note: mock_gemini_lib.Context is called to create the NEW context
  args, kwargs = mock_gemini_lib.Context.call_args
  assert kwargs["system_instruction"] == "new desc"


def test_ask_question(client, mock_json_format):
  """Tests ask_question."""
  mock_response = mock.Mock(_pb=mock.Mock())
  client.chat_client.chat.return_value = iter([mock_response])

  result = client.ask_question("agents/123", "Hello")

  assert len(result.response) == 1
  # Should be the dict returned by MessageToDict
  assert result.response[0] == {"mock_key": "mock_val"}
  assert result.duration.total_duration >= 0
  client.chat_client.chat.assert_called_once()
  mock_json_format.assert_called_once()


def test_ask_question_response_reparsing():
  """Tests AskQuestionResponse.protobuf_response property."""
  from prism.common.schemas.trace import AskQuestionResponse
  from prism.common.schemas.trace import DurationMetrics

  trace_data = [{"user_message": {"text": "hello"}}]
  result = AskQuestionResponse(
      response=trace_data,
      duration=DurationMetrics(total_duration=100),
  )

  # Should use geminidataanalytics.Message constructor
  pbs = result.protobuf_response
  assert len(pbs) == 1
  # proto-plus access
  assert pbs[0].user_message.text == "hello"
