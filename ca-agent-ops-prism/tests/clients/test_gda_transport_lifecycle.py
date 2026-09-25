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

"""Opening and closing the transports GeminiDataAnalyticsClient holds.

A channel is expensive and nothing released one. discover_gcp_agents builds a
client per configured location on every Discover click, and a resource outside
the client's own location used to get a transport built fresh and dropped on
every call, so the channels and their thread pools piled up in the gunicorn
worker until Cloud Run killed the container. The cache and close() are the fix,
and nothing referenced either of them.

The cache is read from several threads at once. gunicorn serves Dash with
--threads 8, so two requests for the same region can both miss it.
"""

import threading
import time
from unittest import mock

from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest

_PROJECT = "projects/test-project/locations/us-central1"


@pytest.fixture(name="client")
def _client():
  """A client whose constructor never looks for credentials."""
  with mock.patch("google.auth.default", return_value=(None, "test-project")):
    yield GeminiDataAnalyticsClient(project=_PROJECT)


def test_one_transport_per_location_and_only_one(client):
  """Two locations are two transports, and the same location is cached."""
  with mock.patch.object(
      GeminiDataAnalyticsClient,
      "_create_agent_client",
      side_effect=lambda location: mock.MagicMock(),
  ) as create:
    europe = client._transport_for_location("agent", "europe-west1")  # pylint: disable=protected-access
    europe_again = client._transport_for_location("agent", "europe-west1")  # pylint: disable=protected-access
    asia = client._transport_for_location("agent", "asia-east1")  # pylint: disable=protected-access

  assert europe_again is europe, "the second call built a second channel"
  assert asia is not europe
  assert create.call_count == 2


def test_the_two_kinds_do_not_share_a_cache_entry(client):
  """A chat transport and an agent transport are different objects.

  They are keyed on (kind, location), so a chat call after an agent call to the
  same region must not be answered with the agent transport.
  """
  with (
      mock.patch.object(
          GeminiDataAnalyticsClient,
          "_create_agent_client",
          side_effect=lambda location: mock.MagicMock(),
      ),
      mock.patch.object(
          GeminiDataAnalyticsClient,
          "_create_chat_client",
          side_effect=lambda location: mock.MagicMock(),
      ),
  ):
    agent = client._transport_for_location("agent", "europe-west1")  # pylint: disable=protected-access
    chat = client._transport_for_location("chat", "europe-west1")  # pylint: disable=protected-access

  assert agent is not chat


def test_two_threads_missing_the_same_location_open_one_transport(client):
  """Both used to build one, and the second overwrote the first in the dict.

  Nothing then held a reference to the first, so it could never be closed:
  the same leak the cache was added to stop, one per race instead of one per
  call.
  """
  built = []

  def _slow_create(location):
    del location
    # Wide enough that every thread is inside the miss window at once.
    time.sleep(0.05)
    transport = mock.MagicMock()
    built.append(transport)
    return transport

  got = []

  def _ask():
    got.append(
        client._transport_for_location("agent", "europe-west1")  # pylint: disable=protected-access
    )

  with mock.patch.object(
      GeminiDataAnalyticsClient,
      "_create_agent_client",
      side_effect=_slow_create,
  ):
    threads = [threading.Thread(target=_ask) for _ in range(8)]
    for thread in threads:
      thread.start()
    for thread in threads:
      thread.join(timeout=30)

  assert len(built) == 1, "a second thread opened a channel nothing can close"
  assert len(got) == 8
  assert all(transport is built[0] for transport in got)


def test_close_closes_every_transport_the_client_opened(client):
  """The two for its own location, and every cached one beside them."""
  own_chat = mock.MagicMock()
  own_agent = mock.MagicMock()
  client.chat_client = own_chat
  client.agent_client = own_agent

  regional = mock.MagicMock()
  with mock.patch.object(
      GeminiDataAnalyticsClient, "_create_chat_client", return_value=regional
  ):
    client._transport_for_location("chat", "europe-west1")  # pylint: disable=protected-access

  client.close()

  own_chat.close.assert_called_once()
  own_agent.close.assert_called_once()
  regional.close.assert_called_once()


def test_close_forgets_the_transports_it_closed(client):
  """Calling it twice must not close a channel that is already gone."""
  transport = mock.MagicMock()
  client.agent_client = transport

  client.close()
  client.close()

  transport.close.assert_called_once()


def test_one_transport_refusing_to_close_does_not_keep_the_rest_open(client):
  """Otherwise the first raise leaks every channel behind it."""
  broken = mock.MagicMock()
  broken.close.side_effect = RuntimeError("channel already shut down")
  other = mock.MagicMock()
  client.chat_client = broken
  client.agent_client = other

  client.close()

  other.close.assert_called_once()


def test_the_context_manager_closes_on_the_way_out(client):
  """__exit__ is the only reason `with GeminiDataAnalyticsClient(...)` works."""
  transport = mock.MagicMock()
  client.agent_client = transport

  with client as entered:
    assert entered is client

  transport.close.assert_called_once()
