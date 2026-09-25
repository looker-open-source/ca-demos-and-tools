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

"""What a failed Looker credentials test puts in front of the user.

Both callers render this message verbatim in an alert, and prism has no
authentication of its own. The message used to be str(e) from the SDK: a host
it could not open comes back as a connection pool error naming the internal
hostname and port, and a rejected key comes back with the request that carried
it. The kind of failure is worked out here and the SDK text stays in the log.

The SDK collapses a transport failure and a bad credential into the same
SDKError, so the classification reads the text. These pin the three classes
apart, which is what tells the user whether to fix the URI or the key.
"""

from __future__ import annotations

from unittest import mock

from prism.server.models.agent import Agent
from prism.server.repositories import agent_repository
from prism.server.services import agent_service
import pytest
from sqlalchemy.orm import Session

_HOSTNAME = "looker.example.com"

_CONNECTION_FAILURE = Exception(
    f"HTTPSConnectionPool(host='{_HOSTNAME}', port=443): Max retries exceeded"
)
_CERTIFICATE_FAILURE = Exception(
    f"SSLError(SSLCertVerificationError(1, 'hostname {_HOSTNAME} doesn't"
    " match'))"
)
_REJECTED_KEY = Exception(
    "POST /api/4.0/login failed: Invalid client_id/client_secret for"
    " prism-eval-key"
)


def _test_credentials(db_session: Session, error: Exception) -> dict[str, str]:
  """Runs the credentials test against an SDK that raises error."""
  service = agent_service.AgentService(
      db_session, agent_repository.AgentRepository(db_session)
  )

  with (
      mock.patch.object(agent_service, "looker_sdk") as mock_looker,
      mock.patch.object(agent_service, "looker_settings") as mock_settings,
  ):
    mock_settings.ApiSettings.return_value = mock.MagicMock()
    mock_looker.init40.side_effect = error

    return service.test_looker_credentials(
        instance_uri=f"https://{_HOSTNAME}",
        client_id="id",
        client_secret="secret",
    )


@pytest.mark.parametrize(
    "error,expected",
    [
        (_CONNECTION_FAILURE, "Check the instance URI"),
        (_CERTIFICATE_FAILURE, "TLS certificate"),
        (_REJECTED_KEY, "Check the client ID and secret"),
    ],
    ids=["unreachable", "certificate", "rejected"],
)
def test_the_three_ways_this_fails_read_differently(
    db_session: Session, error: Exception, expected: str
):
  """Each one has a different fix, so each has to name a different thing.

  Unreachable is the URI, a certificate failure is the instance or the proxy
  in front of it, and a rejected key is the key. All three arrive as the same
  exception type.
  """
  result = _test_credentials(db_session, error)

  assert not result["success"]
  assert expected in result["message"]


@pytest.mark.parametrize(
    "error",
    [_CONNECTION_FAILURE, _CERTIFICATE_FAILURE, _REJECTED_KEY],
    ids=["unreachable", "certificate", "rejected"],
)
def test_no_failure_puts_the_sdk_text_on_the_page(
    db_session: Session, error: Exception
):
  """The hostname and the key name are in the exception, not on the page."""
  result = _test_credentials(db_session, error)

  assert _HOSTNAME not in result["message"]
  assert "prism-eval-key" not in result["message"]
  assert "server log" in result["message"]


def test_a_blank_secret_tests_the_one_the_agent_already_has(
    db_session: Session,
):
  """The edit modal never renders the stored secret, so blank means keep it.

  Read as incomplete, the button refused the case it exists for: checking the
  credentials a saved agent is already running with. The only way past it was
  to retype the value the UI has decided not to show.
  """
  service = agent_service.AgentService(
      db_session, agent_repository.AgentRepository(db_session)
  )
  agent = Agent(
      name="Looker Agent",
      project_id="p",
      location="us-central1",
      agent_resource_id="r",
      datasource_config={"type": "looker"},
      looker_client_id="id",
      looker_client_secret="stored-secret",
  )
  db_session.add(agent)
  db_session.commit()

  # looker_settings is left real here. Subclassing the MagicMock the other
  # tests patch it with gives back the mock's read_config, not the one the
  # method defines, and that is the method under test.
  with mock.patch.object(agent_service, "looker_sdk") as mock_looker:
    result = service.test_looker_credentials(
        instance_uri=f"https://{_HOSTNAME}",
        client_id="id",
        client_secret="",
        agent_id=agent.id,
    )

  assert result["success"]
  # The settings class is built in the method and only the SDK sees it, so the
  # secret it was given is read back off the config it was initialised with.
  settings = mock_looker.init40.call_args.kwargs["config_settings"]
  assert settings.read_config()["client_secret"] == "stored-secret"


def test_a_blank_secret_with_nothing_stored_is_refused(db_session: Session):
  """Without an agent to read from there is nothing to test."""
  service = agent_service.AgentService(
      db_session, agent_repository.AgentRepository(db_session)
  )

  with mock.patch.object(agent_service, "looker_sdk") as mock_looker:
    result = service.test_looker_credentials(
        instance_uri=f"https://{_HOSTNAME}",
        client_id="id",
        client_secret="",
    )

  assert not result["success"]
  assert "No client secret" in result["message"]
  assert not mock_looker.init40.called
