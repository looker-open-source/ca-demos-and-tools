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

"""Unit tests for AgentService."""

from unittest import mock

from prism.common.schemas import agent as schemas
from prism.server.clients.gemini_data_analytics_client import get_gda_endpoint
from prism.server.config import settings
from prism.server.repositories import agent_repository
from prism.server.services import agent_service
import pytest
from sqlalchemy.orm import Session


def test_create_agent_service(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = service.create_agent(name="Service Bot", config=config)

  assert agent.name == "Service Bot"
  assert agent.id is not None


def test_get_agent_service(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  created = service.create_agent(name="Getter Bot", config=config)

  fetched = service.get_agent(created.id)
  assert fetched is not None
  assert fetched.name == "Getter Bot"


def test_update_agent_service(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = service.create_agent(name="Updater", config=config)

  updated = service.update_agent(agent.id, name="New Updater")
  assert updated.name == "New Updater"


def test_archive_agent_service(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = service.create_agent(name="To Archive", config=config)

  service.archive_agent(agent.id)
  fetched = service.get_agent(agent.id)
  assert fetched.is_archived


def test_looker_credentials_service(db_session: Session):
  """A non-Looker agent needs no credentials, so it counts as having them."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  # BQ agent, not Looker
  bq_config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r1",
      datasource={"tables": ["t1"]},
  )
  bq_agent = service.create_agent(name="BQ Bot", config=bq_config)
  assert not service.is_looker_agent(bq_agent.id)
  assert service.has_looker_credentials(bq_agent.id)

  # Looker agent without credentials
  looker_config_no_creds = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r2",
      datasource={"instance_uri": "https://looker.com", "explores": ["e1"]},
  )
  looker_agent_no_creds = service.create_agent(
      name="Looker Bot No Creds", config=looker_config_no_creds
  )
  assert service.is_looker_agent(looker_agent_no_creds.id)
  assert not service.has_looker_credentials(looker_agent_no_creds.id)

  # Looker agent with credentials
  looker_config_with_creds = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r3",
      datasource={"instance_uri": "https://looker.com", "explores": ["e1"]},
      looker_client_id="id",
      looker_client_secret="secret",
  )
  looker_agent_with_creds = service.create_agent(
      name="Looker Bot With Creds", config=looker_config_with_creds
  )
  assert service.is_looker_agent(looker_agent_with_creds.id)
  assert service.has_looker_credentials(looker_agent_with_creds.id)


def test_test_looker_credentials(db_session: Session):
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  with (
      mock.patch(
          "prism.server.services.agent_service.looker_sdk"
      ) as mock_looker,
      mock.patch(
          "prism.server.services.agent_service.looker_settings"
      ) as mock_settings,
  ):
    # Success case
    mock_sdk = mock.MagicMock()
    mock_looker.init40.return_value = mock_sdk
    mock_settings.ApiSettings.return_value = mock.MagicMock()
    mock_sdk.me.return_value = mock.MagicMock(
        first_name="Test", last_name="User", email="test@example.com"
    )

    result = service.test_looker_credentials(
        instance_uri="https://looker.com",
        client_id="id",
        client_secret="secret",
    )
    assert result["success"]
    assert result["message"] == "Connected to the Looker instance."
    # The message goes straight into an alert on the agent form. It used to
    # name the person behind the client id, so a screenshot of a working
    # connection carried their email.
    assert "test@example.com" not in result["message"]
    assert "Test User" not in result["message"]

    # Failure case
    mock_sdk.me.side_effect = Exception("Auth failed")
    result = service.test_looker_credentials(
        instance_uri="https://looker.com",
        client_id="id",
        client_secret="secret",
    )
    assert not result["success"]
    # The SDK text is logged, not rendered. It carries the instance hostname
    # and the alert shows this message verbatim.
    assert "Authentication failed" in result["message"]
    assert "Auth failed" not in result["message"]


def test_normalize_location():
  assert schemas.normalize_location(None) == "global"
  assert schemas.normalize_location("") == "global"
  assert schemas.normalize_location("   ") == "global"
  assert schemas.normalize_location("us") == "us"
  assert schemas.normalize_location("US") == "us"
  assert schemas.normalize_location("Us") == "us"
  assert schemas.normalize_location("eu") == "eu"
  assert schemas.normalize_location("EU") == "eu"
  assert schemas.normalize_location("global") == "global"
  assert schemas.normalize_location("GLOBAL") == "global"
  assert schemas.normalize_location("us-central1") == "us-central1"
  assert schemas.normalize_location("europe-west1") == "europe-west1"


def test_agent_config_location_normalization():
  config_default = schemas.AgentConfig()
  assert config_default.location == "global"

  config_us = schemas.AgentConfig(location="us")
  assert config_us.location == "us"

  config_us_caps = schemas.AgentConfig(location="US")
  assert config_us_caps.location == "us"

  config_none = schemas.AgentConfig(location=None)
  assert config_none.location == "global"

  config_regional = schemas.AgentConfig(location="us-central1")
  assert config_regional.location == "us-central1"


def test_discover_gcp_agents_multi_location(db_session: Session):
  """Discovery queries global, us and eu when no location is given."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  with mock.patch(
      "prism.server.services.agent_service.GeminiDataAnalyticsClient"
  ) as mock_client_cls:
    mock_instance = mock.MagicMock()
    mock_instance.list_agents.return_value = []
    mock_client_cls.return_value = mock_instance

    # Default location queries configured locations (global, us, eu)
    service.discover_gcp_agents(project_id="my-project")
    assert mock_client_cls.call_count == 3
    mock_client_cls.assert_any_call(
        project="projects/my-project/locations/global"
    )
    mock_client_cls.assert_any_call(project="projects/my-project/locations/us")
    mock_client_cls.assert_any_call(project="projects/my-project/locations/eu")

    mock_client_cls.reset_mock()

    # Explicit 'us' multi-region
    service.discover_gcp_agents(project_id="my-project", location="us")
    mock_client_cls.assert_called_once_with(
        project="projects/my-project/locations/us"
    )

    mock_client_cls.reset_mock()

    # Valid region preserved
    service.discover_gcp_agents(project_id="my-project", location="us-central1")
    mock_client_cls.assert_called_once_with(
        project="projects/my-project/locations/us-central1"
    )

    mock_client_cls.reset_mock()

    # Custom configured locations
    with mock.patch.object(
        settings, "gcp_gda_locations_raw", "us,asia-northeast1"
    ):
      service.discover_gcp_agents(project_id="my-project")
      assert mock_client_cls.call_count == 2
      mock_client_cls.assert_any_call(
          project="projects/my-project/locations/us"
      )
      mock_client_cls.assert_any_call(
          project="projects/my-project/locations/asia-northeast1"
      )


def test_discovery_says_so_when_every_location_failed(db_session: Session):
  """An empty result from a total failure read as "no agents in this project".

  One location down still returns what the others found. All of them down is
  a different answer and has to reach the caller as one.
  """
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  with mock.patch(
      "prism.server.services.agent_service.GeminiDataAnalyticsClient"
  ) as mock_client_cls:
    mock_client_cls.side_effect = RuntimeError("no credentials")

    with pytest.raises(RuntimeError, match="Every location failed"):
      service.discover_gcp_agents(project_id="my-project")


def test_discovery_keeps_the_locations_that_answered(db_session: Session):
  """One location down is a log line, not an error."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  working = mock.MagicMock()
  working.list_agents.return_value = [
      schemas.AgentBase(
          name="Bot",
          config=schemas.AgentConfig(
              project_id="my-project",
              location="us",
              agent_resource_id="r",
          ),
      )
  ]

  def _client(project: str):
    if project.endswith("/us"):
      return working
    raise RuntimeError("region unavailable")

  with mock.patch(
      "prism.server.services.agent_service.GeminiDataAnalyticsClient",
      side_effect=_client,
  ):
    found = service.discover_gcp_agents(project_id="my-project")

  assert [a.name for a in found] == ["Bot"]


def test_every_gda_client_the_service_builds_is_closed(db_session: Session):
  """Only discover_gcp_agents released one, and the rest leaked a channel.

  Each client is a gRPC channel and its thread pool, and the gunicorn worker
  lives as long as the container. Two hundred agent page loads left two
  hundred channels open until Cloud Run killed the container mid-run.
  """
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="us-central1",
      agent_resource_id="r",
  )
  agent = service.create_agent(name="Closer", config=config)

  with mock.patch(
      "prism.server.services.agent_service.GeminiDataAnalyticsClient"
  ) as mock_client_cls:
    client = mock_client_cls.return_value
    client.__enter__.return_value = client
    client.create_agent.return_value = schemas.AgentBase(
        name="Registered", config=config.model_copy()
    )

    service.register_gcp_agent(name="Registered", config=config.model_copy())
    service.get_gcp_agent_details(agent.id)
    service.get_published_context(agent.id)
    service.update_agent(
        agent.id,
        config=schemas.AgentConfig(system_instruction="Answer in French."),
    )

  assert mock_client_cls.call_count == 4
  # __exit__, because the class is a mock here and close() is its job.
  # test_gda_transport_lifecycle.py holds the other half of that.
  assert client.__exit__.call_count == 4, (
      "A client built per call and never closed is a channel per call in a"
      " worker that outlives every request."
  )


def test_the_bigquery_client_the_table_check_builds_is_closed(
    db_session: Session,
):
  """It holds an HTTP session, and the agent form checks tables on each save."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  with mock.patch(
      "prism.server.services.agent_service.bigquery"
  ) as mock_bigquery:
    client = mock_bigquery.Client.return_value
    service.check_bigquery_tables(["p.d.a", "p.d.b"])

  mock_bigquery.Client.assert_called_once()
  client.close.assert_called_once()


def test_a_failing_table_check_still_closes_its_client(db_session: Session):
  """The close has to sit in a finally, or the raising path is the leaky one."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  with mock.patch(
      "prism.server.services.agent_service.bigquery"
  ) as mock_bigquery:
    client = mock_bigquery.Client.return_value
    client.get_table.side_effect = KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
      service.check_bigquery_tables(["p.d.a"])

  client.close.assert_called_once()


def test_gda_endpoint_resolution():
  """No endpoint for global, a regional one for everything else."""
  assert get_gda_endpoint(None) is None
  assert get_gda_endpoint("") is None
  assert get_gda_endpoint("global") is None
  assert get_gda_endpoint("GLOBAL") is None
  assert get_gda_endpoint("us") == "geminidataanalytics.us.rep.googleapis.com"
  assert get_gda_endpoint("US") == "geminidataanalytics.us.rep.googleapis.com"
  assert get_gda_endpoint("eu") == "geminidataanalytics.eu.rep.googleapis.com"
  # A region takes the same form as a multi-region. us-east4 is the one the
  # locations documentation lists.
  assert (
      get_gda_endpoint("us-east4")
      == "geminidataanalytics.us-east4.rep.googleapis.com"
  )
