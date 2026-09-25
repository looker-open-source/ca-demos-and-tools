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

"""What happens when the machine has no application default credentials.

GeminiDataAnalyticsClient.__init__ calls google.auth.default purely to find out
who it is running as, and catches DefaultCredentialsError so a missing gcloud
login does not take the constructor down. The catch is narrow and it does not
recover: it writes one line to the log and carries on. The two service clients
open on first use, so that is where the same missing credentials surface.

Which matters because that log line is the only place the real cause is
written. A developer who has not run `gcloud auth application-default login`
otherwise sees whatever the transport says on the first request, which names
neither credentials nor the command that fixes them.

Every other file in this directory patches google.auth.default into succeeding
before it builds a client, because it is testing something else. This one
stubs only the two service clients and leaves google.auth.default to each
test, so the failing arm is the arm under test here.
"""

import logging
from unittest import mock

from google.auth import exceptions as auth_exceptions
from google.cloud import geminidataanalytics_v1beta as gda
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
import pytest

_PROJECT = "projects/test-project/locations/us-central1"


@pytest.fixture(name="stub_transport")
def _stub_transport():
  """Stubs the two service clients, leaving google.auth.default to the test."""
  with (
      mock.patch.object(gda, "DataChatServiceClient") as chat_class,
      mock.patch.object(gda, "DataAgentServiceClient") as agent_class,
  ):
    yield chat_class, agent_class


def test_missing_default_credentials_do_not_take_the_constructor_down(
    stub_transport,
):
  """The lookup is for the log only, so failing it decides nothing.

  Raising here would break every page that builds a client to list agents,
  including the settings page a user would go to in order to fix the problem.
  """
  chat_class, agent_class = stub_transport

  with mock.patch(
      "google.auth.default",
      side_effect=auth_exceptions.DefaultCredentialsError("no ADC found"),
  ):
    client = GeminiDataAnalyticsClient(project=_PROJECT)

  assert client.location == "us-central1"
  assert client.chat_client is chat_class.return_value
  assert client.agent_client is agent_class.return_value


def test_missing_default_credentials_are_logged_with_the_reason(
    stub_transport, caplog
):
  """The swallowed exception's own text has to survive.

  google.auth writes the path it looked in and the command to run into that
  message. Logging "auth failed" instead would leave the developer with
  nothing.
  """
  del stub_transport

  with caplog.at_level(logging.ERROR):
    with mock.patch(
        "google.auth.default",
        side_effect=auth_exceptions.DefaultCredentialsError(
            "Your default credentials were not found. Run gcloud auth"
            " application-default login"
        ),
    ):
      GeminiDataAnalyticsClient(project=_PROJECT)

  assert "gcloud auth application-default login" in caplog.text


def test_an_auth_failure_that_is_not_about_credentials_is_not_swallowed(
    stub_transport,
):
  """Only the "you are not logged in" case is written off.

  A refresh that fails against a credential that does exist is a different
  problem, and one the caller has to see.
  """
  del stub_transport

  with mock.patch(
      "google.auth.default",
      side_effect=auth_exceptions.RefreshError("token endpoint returned 400"),
  ):
    with pytest.raises(auth_exceptions.RefreshError):
      GeminiDataAnalyticsClient(project=_PROJECT)


def test_the_logged_line_is_all_the_arm_does(stub_transport):
  """Opening the transport is still the thing that fails.

  The transport is stubbed in the tests above, so the constructor gets to the
  end. Against the real SDK the same missing credentials stop
  DataChatServiceClient instead, now on the first property read rather than in
  the constructor. The catch buys a log entry and a clearer message, not a
  working client, and a reader of the arm should not come away thinking prism
  keeps running without credentials.
  """
  del stub_transport

  with (
      mock.patch(
          "google.auth.default",
          side_effect=auth_exceptions.DefaultCredentialsError("no ADC found"),
      ),
      mock.patch.object(
          gda,
          "DataChatServiceClient",
          side_effect=auth_exceptions.DefaultCredentialsError("no ADC found"),
      ),
      mock.patch.object(gda, "DataAgentServiceClient"),
  ):
    client = GeminiDataAnalyticsClient(project=_PROJECT)
    with pytest.raises(auth_exceptions.DefaultCredentialsError):
      client.chat_client  # pylint: disable=pointless-statement
