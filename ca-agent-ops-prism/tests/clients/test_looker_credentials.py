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

"""Where a Looker agent's OAuth client secret is allowed to end up.

The secret reaches this client twice. It comes back on the agent's published
context, which every run snapshots onto its row and from there onto the run
page, into the comparison diff and out to BigQuery. It also goes out on every
chat request, which used to be logged whole. These tests build real protos and
pin both paths.
"""

import logging
from unittest import mock

from google.cloud import geminidataanalytics_v1beta as gda
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest

_SECRET = "s3cret"


@pytest.fixture(name="client")
def _client():
  """A client whose transport is stubbed, over the real proto library."""
  with (
      mock.patch("google.auth.default", return_value=(None, "test-project")),
      mock.patch.object(gda, "DataChatServiceClient"),
      mock.patch.object(gda, "DataAgentServiceClient"),
  ):
    yield GeminiDataAnalyticsClient(
        project="projects/test-project/locations/us-central1"
    )


def _looker_context(with_credentials: bool) -> gda.Context:
  """The context a Looker agent is published with."""
  looker = gda.LookerExploreReferences(
      explore_references=[
          gda.LookerExploreReference(lookml_model="thelook", explore="orders")
      ]
  )
  if with_credentials:
    looker.credentials = gda.Credentials(
        oauth=gda.OAuthCredentials(
            secret=gda.OAuthCredentials.SecretBased(
                client_id="an-id", client_secret=_SECRET
            )
        )
    )
  return gda.Context(
      system_instruction="answer questions about orders",
      datasource_references=gda.DatasourceReferences(looker=looker),
  )


def _publish(client: GeminiDataAnalyticsClient, context: gda.Context):
  """Puts the context where get_agent_context reads it from."""
  client.agent_client.get_data_agent.return_value = gda.DataAgent(
      name="projects/p/locations/l/dataAgents/a",
      data_analytics_agent=gda.DataAnalyticsAgent(published_context=context),
  )


def test_the_client_secret_is_not_in_the_snapshot(client):
  _publish(client, _looker_context(with_credentials=True))

  snapshot = client.get_agent_context("agent", "published")

  assert _SECRET not in str(snapshot)


def test_the_credentials_block_is_gone_not_blanked(client):
  """A blanked-out secret still shows the reader an OAuth setup that is not.

  It also still round-trips through the comparison diff as a changed value
  every time the agent is republished.
  """
  _publish(client, _looker_context(with_credentials=True))

  snapshot = client.get_agent_context("agent", "published")

  assert "credentials" not in snapshot["datasource_references"]["looker"]


def test_the_rest_of_a_looker_context_is_kept(client):
  """The explores and the instruction are what the snapshot exists to record."""
  _publish(client, _looker_context(with_credentials=True))

  snapshot = client.get_agent_context("agent", "published")

  assert snapshot["system_instruction"] == "answer questions about orders"
  [explore] = snapshot["datasource_references"]["looker"]["explore_references"]
  assert explore == {"lookml_model": "thelook", "explore": "orders"}


def test_a_looker_context_without_credentials_is_unchanged(client):
  _publish(client, _looker_context(with_credentials=False))

  snapshot = client.get_agent_context("agent", "published")

  assert snapshot["datasource_references"]["looker"]["explore_references"]


def test_a_bigquery_context_gains_no_empty_looker_block(client):
  """Deleting through the proto wrapper creates the parents it passes.

  Without the presence check every BigQuery agent's snapshot would grow an
  empty looker reference, which the comparison diff would report as a change.
  """
  _publish(
      client,
      gda.Context(
          system_instruction="answer questions",
          datasource_references=gda.DatasourceReferences(
              bq=gda.BigQueryTableReferences(
                  table_references=[
                      gda.BigQueryTableReference(
                          project_id="p", dataset_id="d", table_id="t"
                      )
                  ]
              )
          ),
      ),
  )

  snapshot = client.get_agent_context("agent", "published")

  assert "looker" not in snapshot["datasource_references"]


def test_the_agent_itself_is_left_alone(client):
  """The redaction copies. Editing the response would corrupt a cached agent."""
  context = _looker_context(with_credentials=True)
  _publish(client, context)

  client.get_agent_context("agent", "published")

  assert (
      context.datasource_references.looker.credentials.oauth.secret.client_secret
      == _SECRET
  )


def test_the_staging_context_is_redacted_too(client):
  """Both targets come from the same agent, so both carry the same secret."""
  client.agent_client.get_data_agent.return_value = gda.DataAgent(
      name="projects/p/locations/l/dataAgents/a",
      data_analytics_agent=gda.DataAnalyticsAgent(
          staging_context=_looker_context(with_credentials=True)
      ),
  )

  snapshot = client.get_agent_context("agent", "staging")

  assert _SECRET not in str(snapshot)


def test_asking_a_question_does_not_log_the_secret(client, caplog):
  """The whole ChatRequest was logged, and the credentials ride on it."""
  client.chat_client.chat.return_value = []

  with caplog.at_level(logging.DEBUG):
    client.ask_question(
        agent_id="projects/p/locations/l/dataAgents/a",
        question="how many orders",
        client_id="an-id",
        client_secret=_SECRET,
    )

  assert _SECRET not in caplog.text


def test_asking_a_question_still_logs_what_was_asked(client, caplog):
  """Dropping the request log entirely would take the debugging with it."""
  client.chat_client.chat.return_value = []

  with caplog.at_level(logging.DEBUG):
    client.ask_question(
        agent_id="projects/p/locations/l/dataAgents/a",
        question="how many orders",
        client_id="an-id",
        client_secret=_SECRET,
    )

  assert "how many orders" in caplog.text
  assert "dataAgents/a" in caplog.text
