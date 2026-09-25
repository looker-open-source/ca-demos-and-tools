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

"""A failed update operation must not come back looking like a saved edit.

The operation result is what says the write landed. When waiting on it fails
the agent is read back, because a timeout can sit on either side of a write
that did land. The read used to be the whole test. The agent always exists, so
it always succeeded, and whatever it returned was handed back as the result of
the update. agent_service then wrote the local row from it, so a rejected edit
reported as saved and prism went on describing an agent GCP does not have.

Real protos here, not the module-wide mock the rest of the client tests use.
The check is a comparison of two contexts, and a mock would answer it however
it was asked.
"""

from unittest import mock

from google.api_core import exceptions as api_exceptions
from google.cloud import geminidataanalytics_v1beta as gda
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import LookerConfig
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest

_PROJECT = "projects/test-project/locations/us-central1"
_AGENT_NAME = f"{_PROJECT}/dataAgents/agent-123"
_INSTANCE = "https://example.cloud.looker.com"


def _bq_references() -> gda.DatasourceReferences:
  return gda.DatasourceReferences(
      bq=gda.BigQueryTableReferences(
          table_references=[
              gda.BigQueryTableReference(
                  project_id="p", dataset_id="d", table_id="t"
              )
          ]
      )
  )


def _looker_references(credentials=None) -> gda.DatasourceReferences:
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


def _credentials() -> gda.Credentials:
  return gda.Credentials(
      oauth=gda.OAuthCredentials(
          secret=gda.OAuthCredentials.SecretBased(
              client_id="stored-id", client_secret="stored-secret"
          )
      )
  )


def _agent(instruction, references=None) -> gda.DataAgent:
  return gda.DataAgent(
      name=_AGENT_NAME,
      display_name="Update Bot",
      data_analytics_agent=gda.DataAnalyticsAgent(
          published_context=gda.Context(
              system_instruction=instruction,
              datasource_references=references or _bq_references(),
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


def _timing_out(client, stored, live_or_error):
  """A client whose update times out, and whose read back answers with live.

  A timeout is the one failure where the write may still have landed, so it
  is the failure the read back exists for.
  """
  client.agent_client.get_data_agent.side_effect = [stored, live_or_error]
  client.agent_client.update_data_agent.return_value.result.side_effect = (
      api_exceptions.DeadlineExceeded("operation timed out")
  )


def test_an_agent_that_took_the_update_is_reported_as_saved(client):
  """The case the read back is there for: the write landed, the wait did not.

  Failing this one sends the user back to retype an edit that is already on
  the agent.
  """
  _timing_out(client, _agent("old"), _agent("new"))

  updated = client.update_agent(_AGENT_NAME, system_instruction="new")

  assert updated.config.system_instruction == "new"


def test_an_agent_that_did_not_take_the_update_still_fails(client):
  """The bug. The stale agent was returned, so the edit read as saved."""
  _timing_out(client, _agent("old"), _agent("old"))

  with pytest.raises(api_exceptions.DeadlineExceeded):
    client.update_agent(_AGENT_NAME, system_instruction="new")


def test_a_read_back_that_fails_reports_the_update_failure(client):
  """The update is what the caller asked for, so its error is the one to give.

  A permission error on the read says nothing about whether the write landed.
  """
  _timing_out(client, _agent("old"), api_exceptions.PermissionDenied("nope"))

  with pytest.raises(api_exceptions.DeadlineExceeded):
    client.update_agent(_AGENT_NAME, system_instruction="new")


def test_looker_credentials_the_service_withholds_are_not_a_difference(client):
  """The sent context carries the secret, and the answer need not carry it.

  update_agent merges the stored Looker credentials into the context it
  sends, because the update replaces the published context wholesale. A
  service that does not hand the secret back would otherwise make every
  Looker agent's read back look like a rejected edit.
  """
  stored = _agent("old", _looker_references(_credentials()))
  live = _agent("new", _looker_references())
  _timing_out(client, stored, live)

  config = AgentConfig(
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource=LookerConfig(
          instance_uri=_INSTANCE, explores=["orders.order_items"]
      ),
  )

  updated = client.update_agent(
      _AGENT_NAME, system_instruction="new", config=config
  )

  assert updated.config.system_instruction == "new"
