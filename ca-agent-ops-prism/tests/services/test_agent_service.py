"""Unit tests for AgentService."""
from unittest import mock

from prism.common.schemas import agent as schemas
from prism.server.repositories import agent_repository
from prism.server.services import agent_service
from sqlalchemy.orm import Session


def test_create_agent_service(db_session: Session):
  """Tests creating an agent via service."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      env=schemas.AgentEnv.STAGING,
  )
  agent = service.create_agent(name="Service Bot", config=config)

  assert agent.name == "Service Bot"
  assert agent.id is not None


def test_get_agent_service(db_session: Session):
  """Tests getting an agent via service."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      env=schemas.AgentEnv.STAGING,
  )
  created = service.create_agent(name="Getter Bot", config=config)

  fetched = service.get_agent(created.id)
  assert fetched is not None
  assert fetched.name == "Getter Bot"


def test_update_agent_service(db_session: Session):
  """Tests updating an agent via service."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      env=schemas.AgentEnv.STAGING,
  )
  agent = service.create_agent(name="Updater", config=config)

  updated = service.update_agent(agent.id, name="New Updater")
  assert updated.name == "New Updater"


def test_archive_agent_service(db_session: Session):
  """Tests archiving an agent via service."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)
  config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      env=schemas.AgentEnv.STAGING,
  )
  agent = service.create_agent(name="To Archive", config=config)

  service.archive_agent(agent.id)
  fetched = service.get_agent(agent.id)
  assert fetched.is_archived


def test_looker_credentials_service(db_session: Session):
  """Tests Looker credential check methods in AgentService."""
  repo = agent_repository.AgentRepository(db_session)
  service = agent_service.AgentService(db_session, repo)

  # 1. BQ Agent (Not Looker)
  bq_config = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r1",
      env=schemas.AgentEnv.STAGING,
      datasource={"tables": ["t1"]},
  )
  bq_agent = service.create_agent(name="BQ Bot", config=bq_config)
  assert not service.is_looker_agent(bq_agent.id)
  assert service.has_looker_credentials(bq_agent.id)

  # 2. Looker Agent without Credentials
  looker_config_no_creds = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r2",
      env=schemas.AgentEnv.STAGING,
      datasource={"instance_uri": "https://looker.com", "explores": ["e1"]},
  )
  looker_agent_no_creds = service.create_agent(
      name="Looker Bot No Creds", config=looker_config_no_creds
  )
  assert service.is_looker_agent(looker_agent_no_creds.id)
  assert not service.has_looker_credentials(looker_agent_no_creds.id)

  # 3. Looker Agent with Credentials
  looker_config_with_creds = schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r3",
      env=schemas.AgentEnv.STAGING,
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
  """Tests the test_looker_credentials method with mocking."""
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
    # 1. Success case
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
    if not result["success"]:
      print(f"DEBUG RESULT: {result}")
    assert result["success"]
    assert "Successfully authenticated" in result["message"]

    # 2. Failure case
    mock_sdk.me.side_effect = Exception("Auth failed")
    result = service.test_looker_credentials(
        instance_uri="https://looker.com",
        client_id="id",
        client_secret="secret",
    )
    assert not result["success"]
    assert "Auth failed" in result["message"]
