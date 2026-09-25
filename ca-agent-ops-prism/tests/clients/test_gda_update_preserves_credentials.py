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

"""Editing a Looker agent must not take its Looker credentials with it.

update_agent replaces the whole published context: the update mask is
data_analytics_agent.published_context, so whatever is not in the new context
is gone from the agent. The new datasource references are built by
_get_datasource_references, which works off the explores in AgentConfig, and
AgentConfig has nowhere to put OAuth credentials. get_agent_context strips them
on the way out too, so prism never holds a copy.

The result was that changing a system instruction wiped the credentials, and
every question after that failed on a datasource with no way to authenticate.
The old ones are carried across now, and these pin that.

Real protos here, not the module-wide mock the rest of the client tests use.
The fix is a oneof check and a CopyFrom, and a mock would answer both however
it was asked.
"""

from unittest import mock

from google.cloud import geminidataanalytics_v1beta as gda
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest

_PROJECT = "projects/test-project/locations/us-central1"
_AGENT_NAME = f"{_PROJECT}/dataAgents/agent-123"
_INSTANCE = "https://example.cloud.looker.com"


def _credentials(client_id="stored-id", client_secret="stored-secret"):
  return gda.Credentials(
      oauth=gda.OAuthCredentials(
          secret=gda.OAuthCredentials.SecretBased(
              client_id=client_id, client_secret=client_secret
          )
      )
  )


def _looker_references(credentials=None):
  return gda.DatasourceReferences(
      looker=gda.LookerExploreReferences(
          explore_references=[
              gda.LookerExploreReference(
                  looker_instance_uri=_INSTANCE,
                  lookml_model="orders",
                  explore="order_items",
              )
          ],
          credentials=credentials,
      )
  )


def _published(references, instruction="old instruction"):
  """The agent as the service holds it today."""
  return gda.DataAgent(
      name=_AGENT_NAME,
      data_analytics_agent=gda.DataAnalyticsAgent(
          published_context=gda.Context(
              system_instruction=instruction,
              datasource_references=references,
          )
      ),
  )


@pytest.fixture(name="client")
def _client():
  """A real client with only the two transports and the ADC lookup stubbed."""
  with (
      mock.patch.object(gda, "DataChatServiceClient"),
      mock.patch.object(gda, "DataAgentServiceClient"),
      mock.patch("google.auth.default", return_value=(None, "test-project")),
  ):
    yield GeminiDataAnalyticsClient(project=_PROJECT)


def _sent_context(client) -> gda.Context:
  """The published context the client asked the service to write."""
  request = client.agent_client.update_data_agent.call_args.kwargs["request"]
  return request.data_agent.data_analytics_agent.published_context


def _edit(client, stored, config, system_instruction="new instruction"):
  client.agent_client.get_data_agent.return_value = stored
  client.agent_client.update_data_agent.return_value.result.return_value = (
      stored
  )
  client.update_agent(
      _AGENT_NAME, system_instruction=system_instruction, config=config
  )


def test_an_instruction_only_edit_keeps_the_stored_credentials(client):
  """The edit the UI sends. It carries the config, but not the credentials."""
  stored = _published(_looker_references(_credentials()))
  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource=LookerConfig(
          instance_uri=_INSTANCE, explores=["orders.order_items"]
      ),
  )

  _edit(client, stored, config)

  context = _sent_context(client)
  assert context.system_instruction == "new instruction"
  secret = context.datasource_references.looker.credentials.oauth.secret
  assert secret.client_id == "stored-id"
  assert secret.client_secret == "stored-secret"


def test_the_explores_in_the_edit_still_win(client):
  """Carrying the credentials must not carry the old datasource with them."""
  stored = _published(_looker_references(_credentials()))
  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource=LookerConfig(
          instance_uri=_INSTANCE, explores=["sales.line_items"]
      ),
  )

  _edit(client, stored, config)

  looker = _sent_context(client).datasource_references.looker
  assert [e.explore for e in looker.explore_references] == ["line_items"]
  assert looker.credentials.oauth.secret.client_id == "stored-id"


def test_an_agent_stored_without_credentials_gains_none(client):
  """Nothing to carry, so the field stays unset rather than becoming empty."""
  stored = _published(_looker_references())
  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource=LookerConfig(
          instance_uri=_INSTANCE, explores=["orders.order_items"]
      ),
  )

  _edit(client, stored, config)

  references = _sent_context(client).datasource_references
  assert not references.looker._pb.HasField("credentials")  # pylint: disable=protected-access


def test_switching_a_looker_agent_to_bigquery_drops_the_credentials(client):
  """The new references are not Looker, so there is nothing to carry onto."""
  stored = _published(_looker_references(_credentials()))
  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource=BigQueryConfig(tables=["p.d.t"]),
  )

  _edit(client, stored, config)

  references = _sent_context(client).datasource_references
  assert references._pb.WhichOneof("references") == "bq"  # pylint: disable=protected-access


def test_credentials_in_the_edit_beat_the_stored_ones(client):
  """An edit that brings its own means them.

  Nothing in prism sends these today. It is here so that whatever does later
  is not silently overwritten by the copy the agent already had.
  """
  stored = _published(_looker_references(_credentials()))
  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource=LookerConfig(
          instance_uri=_INSTANCE, explores=["orders.order_items"]
      ),
  )

  client.agent_client.get_data_agent.return_value = stored
  client.agent_client.update_data_agent.return_value.result.return_value = (
      stored
  )
  with mock.patch.object(
      GeminiDataAnalyticsClient,
      "_get_datasource_references",
      return_value=_looker_references(_credentials("new-id", "new-secret")),
  ):
    client.update_agent(
        _AGENT_NAME, system_instruction="new instruction", config=config
    )

  secret = _sent_context(
      client
  ).datasource_references.looker.credentials.oauth.secret
  assert secret.client_id == "new-id"
