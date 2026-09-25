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

"""Unit tests for GeminiDataAnalyticsClient."""

from unittest import mock

from google.api_core import exceptions as api_exceptions
from google.cloud import geminidataanalytics_v1beta as gda
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerGoldenQuery
from prism.common.schemas.agent import LookerQuery
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.clients import gemini_data_analytics_client
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest


class _Clock:
  """Stands in for the time module, handing out the reads in order.

  Put over the client module's own ``time`` name rather than over
  ``time.time`` itself, so nothing else running in the process is slowed or
  stopped by it.
  """

  def __init__(self, reads: list[float]):
    self._reads = iter(reads)

  def time(self) -> float:
    return next(self._reads)


@pytest.fixture
def mock_gemini_lib():
  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.geminidataanalytics"
  ) as mock_lib:
    yield mock_lib


@pytest.fixture
def mock_auth():
  with mock.patch("google.auth.default") as mock_auth_default:
    mock_auth_default.return_value = (None, "test-project")
    yield mock_auth_default


@pytest.fixture
def mock_json_format():
  with mock.patch(
      "prism.server.clients.gemini_data_analytics_client.json_format.MessageToDict"
  ) as mock_proto_to_dict:
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
    golden_queries=None,
):
  mock_pb = mock.Mock()
  mock_pb.name = (
      f"projects/test-project/locations/us-central1/dataAgents/{resource_id}"
  )
  mock_pb.display_name = display_name

  mock_context = mock.Mock()
  mock_context.system_instruction = sys_instruct
  mock_context.datasource_references = None
  mock_context.looker_golden_queries = golden_queries or []

  mock_da = mock.Mock()
  mock_da.published_context = mock_context
  mock_pb.data_analytics_agent = mock_da

  return mock_pb


def test_init(client, mock_gemini_lib):
  """Construction costs nothing. The transports open on first use.

  Both used to be built in __init__, so discover_gcp_agents opened two gRPC
  channels per location it swept and dropped them unclosed.
  """
  assert client.project == "projects/test-project/locations/us-central1"
  mock_gemini_lib.DataChatServiceClient.assert_not_called()
  mock_gemini_lib.DataAgentServiceClient.assert_not_called()

  client.chat_client  # pylint: disable=pointless-statement
  client.agent_client  # pylint: disable=pointless-statement

  mock_gemini_lib.DataChatServiceClient.assert_called_once()
  mock_gemini_lib.DataAgentServiceClient.assert_called_once()


def test_list_agents(client):
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


def test_an_agent_with_no_published_context_still_lists(client):
  """Agents built by other tools have no data_analytics_agent at all.

  Reading the context unconditionally raised UnboundLocalError on the first
  one. See test_one_bad_agent_does_not_take_the_page_with_it for what that
  cost.
  """
  mock_pb = make_mock_agent_pb("agent-1")
  mock_pb.data_analytics_agent = None
  client.agent_client.list_data_agents.return_value = [mock_pb]

  agents = client.list_agents()

  assert [a.config.agent_resource_id for a in agents] == ["agent-1"]
  assert agents[0].config.datasource is None


def test_one_bad_agent_does_not_take_the_page_with_it(client):
  """The except was around the whole pager, so one raise ended the listing.

  A project with 58 agents showed 7, and the picker gave no sign the rest
  existed.
  """
  bad = make_mock_agent_pb("agent-2")
  type(bad).display_name = mock.PropertyMock(side_effect=ValueError("boom"))
  client.agent_client.list_data_agents.return_value = [
      make_mock_agent_pb("agent-1"),
      bad,
      make_mock_agent_pb("agent-3"),
  ]

  agents = client.list_agents()

  assert [a.config.agent_resource_id for a in agents] == ["agent-1", "agent-3"]


def test_a_failed_listing_is_not_an_empty_project(client):
  """The call used to swallow this and return an empty list.

  A project the caller cannot read then looked exactly like a project with no
  agents in it.
  """
  client.agent_client.list_data_agents.side_effect = (
      api_exceptions.PermissionDenied("nope")
  )

  with pytest.raises(api_exceptions.PermissionDenied):
    client.list_agents()


def test_create_agent(client, mock_gemini_lib):
  gq = LookerGoldenQuery(
      natural_language_questions=["Q1"],
      looker_query=LookerQuery(explore="v", fields=["f"]),
  )

  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="new-agent",
      system_instruction="desc",
      datasource=BigQueryConfig(tables=["p.d.t"]),
      golden_queries=[gq],
  )

  # What the service hands back for the golden query. The list fields have
  # to be real lists: the mapping iterates them.
  mock_proto_gq = mock.Mock()
  mock_proto_gq.natural_language_questions = ["Q1"]
  mock_proto_gq.looker_query.fields = ["f"]
  mock_proto_gq.looker_query.model = None
  mock_proto_gq.looker_query.explore = None
  mock_proto_gq.looker_query.limit = None
  mock_proto_gq.looker_query.filters = []
  mock_proto_gq.looker_query.sorts = []
  mock_proto_gq.looker_query.dynamic_fields = []

  mock_operation = mock.Mock()
  mock_operation.result.return_value = make_mock_agent_pb(
      "new-agent", "Test Agent", golden_queries=[mock_proto_gq]
  )
  client.agent_client.create_data_agent.return_value = mock_operation

  created_agent = client.create_agent(display_name="Test Agent", config=config)

  assert isinstance(created_agent, AgentBase)
  assert created_agent.config.agent_resource_id == "new-agent"
  assert created_agent.config.golden_queries is not None
  assert len(created_agent.config.golden_queries) == 1
  assert created_agent.config.golden_queries[0].natural_language_questions == [
      "Q1"
  ]

  client.agent_client.create_data_agent.assert_called_once()
  mock_gemini_lib.BigQueryTableReference.assert_called_with(
      project_id="p", dataset_id="d", table_id="t"
  )
  mock_gemini_lib.LookerGoldenQuery.assert_called()
  mock_gemini_lib.Context.assert_called()


def test_get_agent(client):
  mock_agent = make_mock_agent_pb("agent-123")
  client.agent_client.get_data_agent.return_value = mock_agent

  agent = client.get_agent("agents/agent-123")

  assert isinstance(agent, AgentBase)
  assert agent.config.agent_resource_id == "agent-123"
  client.agent_client.get_data_agent.assert_called_once()


def test_update_agent(client, mock_gemini_lib):
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
  # update_agent rebuilds the whole context, so the instruction has to reach
  # the constructor and not just the returned agent.
  _, kwargs = mock_gemini_lib.Context.call_args
  assert kwargs["system_instruction"] == "new desc"


def test_ask_question(client, mock_json_format, monkeypatch):
  """The response items, and the two durations timed around them.

  The clock is driven, because ask_question reads ``time.time()`` three times
  and the difference between two real reads is non-negative whatever the
  arithmetic does with it. The reads are the start, the first chunk and the
  end, in that order, and both figures are milliseconds.
  """
  mock_response = mock.Mock(_pb=mock.Mock())
  client.chat_client.chat.return_value = iter([mock_response])
  monkeypatch.setattr(
      gemini_data_analytics_client, "time", _Clock([100.0, 100.25, 100.5])
  )

  result = client.ask_question("agents/123", "Hello")

  assert len(result.response) == 1
  assert result.response[0] == {"mock_key": "mock_val"}
  assert result.duration.time_to_first_response == 250
  assert result.duration.total_duration == 500
  client.chat_client.chat.assert_called_once()
  mock_json_format.assert_called_once()


def test_an_api_error_is_recorded_without_the_server_detail(client):
  """A Looker agent with a stale credential fails here, and the trial shows it.

  The detail the service attaches is a few hundred characters of internal
  class names wrapped around the one sentence the reader needs.
  """
  client.chat_client.chat.side_effect = api_exceptions.PermissionDenied(
      "Permission denied on Looker datasource(s): Login failed",
      details=["[ORIGINAL ERROR] generic::permission_denied: com.google.x.y.Z"],
  )

  result = client.ask_question("agents/123", "Hello")

  assert result.error_message == (
      "SDK Request Failed: 403 Permission denied on Looker datasource(s):"
      " Login failed"
  )


def test_a_looker_agent_run_without_credentials_says_which_ones(client):
  """Prism cannot always tell an agent is Looker, so the service says it first.

  An agent whose published context holds no datasource prism can read is stored
  with no config, and the run starts because blocking it would also block the
  kinds prism does not model. A Looker one among those reaches the service, and
  every trial of the run used to fail with a proto field path. Captured
  verbatim from a live agent.
  """
  client.chat_client.chat.side_effect = api_exceptions.InvalidArgument(
      "request.context.datasource_references.looker.credentials.kind: invalid"
      " value: KIND_NOT_SET"
  )

  result = client.ask_question("agents/123", "Hello")

  assert result.error_message == (
      "SDK Request Failed: 400 This agent needs Looker credentials. Edit the"
      " agent to add a Looker client ID and secret."
  )


_BQ = gda.DatasourceReferences(
    bq=gda.BigQueryTableReferences(
        table_references=[
            gda.BigQueryTableReference(
                project_id="p", dataset_id="d", table_id="t"
            )
        ]
    )
)
_LOOKER = gda.DatasourceReferences(
    looker=gda.LookerExploreReferences(
        explore_references=[
            gda.LookerExploreReference(
                looker_instance_uri="https://x.looker.com",
                lookml_model="m",
                explore="e",
            )
        ]
    )
)


def _agent_pb(published=None, staging=None):
  """A real DataAgent whose two contexts name the given datasources."""
  da_agent = gda.DataAnalyticsAgent()
  if published is not None:
    da_agent.published_context = gda.Context(datasource_references=published)
  if staging is not None:
    da_agent.staging_context = gda.Context(datasource_references=staging)
  return gda.DataAgent(data_analytics_agent=da_agent)


@pytest.mark.parametrize(
    "published,staging,expected",
    [
        (_LOOKER, None, "looker"),
        (_BQ, None, "bq"),
        (_LOOKER, _BQ, "looker"),
        # An agent saved and never published answers from its staging context.
        # Reading published only would report this one as having no datasource.
        (None, _BQ, "bq"),
        (None, None, None),
    ],
)
def test_get_datasource_kind(client, published, staging, expected):
  """The kind decides whether the run needs Looker credentials."""
  client.agent_client.get_data_agent.return_value = _agent_pb(
      published, staging
  )

  assert client.get_datasource_kind("agents/123") == expected


def test_get_datasource_kind_names_a_kind_prism_does_not_parse(client):
  """Anything the oneof holds counts, or the run would be blocked for nothing.

  _pb_to_agent_base reads bq and looker, so every other kind reaches prism as
  an agent with no datasource.
  """
  other = next(
      f.name
      for f in gda.DatasourceReferences.pb(
          gda.DatasourceReferences()
      ).DESCRIPTOR.fields
      if f.name not in ("bq", "looker")
  )

  refs = gda.DatasourceReferences()
  # An empty one in the constructor does not set the oneof, and the live
  # agents this stands for carry an empty list.
  getattr(gda.DatasourceReferences.pb(refs), other).SetInParent()
  client.agent_client.get_data_agent.return_value = _agent_pb(published=refs)

  assert client.get_datasource_kind("agents/123") == other


def test_ask_question_response_reparsing():
  """A stored dict trace parses back into protos."""
  trace_data = [{"user_message": {"text": "hello"}}]
  result = AskQuestionResponse(
      response=trace_data,
      duration=DurationMetrics(total_duration=100),
  )

  pbs = result.protobuf_response
  assert len(pbs) == 1
  assert pbs[0].user_message.text == "hello"


def test_update_agent_with_golden_queries(client, mock_gemini_lib):
  mock_existing = make_mock_agent_pb("agent-123")
  client.agent_client.get_data_agent.return_value = mock_existing

  mock_proto_gq = mock.Mock()
  mock_proto_gq.natural_language_questions = ["New Q"]
  mock_proto_gq.looker_query.model = None
  mock_proto_gq.looker_query.limit = None
  mock_proto_gq.looker_query.explore = None
  mock_proto_gq.looker_query.fields = []
  mock_proto_gq.looker_query.filters = []
  mock_proto_gq.looker_query.sorts = []
  mock_proto_gq.looker_query.dynamic_fields = []

  mock_operation = mock.Mock()
  mock_operation.result.return_value = make_mock_agent_pb(
      "agent-123", golden_queries=[mock_proto_gq]
  )
  client.agent_client.update_data_agent.return_value = mock_operation

  gq = LookerGoldenQuery(
      natural_language_questions=["New Q"],
      looker_query=LookerQuery(explore="new_view", fields=["f"]),
  )
  config = AgentConfig(golden_queries=[gq])

  updated_agent = client.update_agent("agents/agent-123", config=config)

  assert isinstance(updated_agent, AgentBase)
  assert updated_agent.config.golden_queries is not None
  assert len(updated_agent.config.golden_queries) == 1
  assert updated_agent.config.golden_queries[0].natural_language_questions == [
      "New Q"
  ]

  client.agent_client.update_data_agent.assert_called_once()
  # The queries have to reach the context constructor, not only the agent
  # that comes back. Asserted by value: _get_looker_golden_queries returns []
  # when it maps nothing, and an empty list is not None either.
  _, kwargs = mock_gemini_lib.Context.call_args
  assert kwargs["looker_golden_queries"] == [
      mock_gemini_lib.LookerGoldenQuery.return_value
  ]
  _, gq_kwargs = mock_gemini_lib.LookerGoldenQuery.call_args
  assert gq_kwargs["natural_language_questions"] == ["New Q"]
  assert gq_kwargs["looker_query"] == mock_gemini_lib.LookerQuery.return_value
  _, lq_kwargs = mock_gemini_lib.LookerQuery.call_args
  assert lq_kwargs["explore"] == "new_view"
  assert lq_kwargs["fields"] == ["f"]
