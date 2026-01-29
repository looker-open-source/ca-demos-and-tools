"""Unit tests for AgentRepository."""

from prism.common.schemas.agent import AgentConfig
from prism.server.repositories.agent_repository import AgentRepository
from sqlalchemy.orm import Session


def test_create_agent(db_session: Session):
  """Tests creating a new agent."""
  repo = AgentRepository(db_session)
  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = repo.create(name="Test Bot", config=config)

  assert agent.id is not None
  assert agent.name == "Test Bot"
  assert agent.project_id == "p"
  assert not agent.is_archived


def test_get_agent(db_session: Session):
  """Tests retrieving an agent."""
  repo = AgentRepository(db_session)
  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  created = repo.create(name="Finder Bot", config=config)

  fetched = repo.get_by_id(created.id)
  assert fetched is not None
  assert fetched.id == created.id
  assert fetched.name == "Finder Bot"


def test_update_agent(db_session: Session):
  """Tests updating an agent."""
  repo = AgentRepository(db_session)
  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = repo.create(name="Updater Bot", config=config)

  new_config = AgentConfig(
      project_id="p2",
      location="l2",
      agent_resource_id="r2",
  )
  updated = repo.update(agent.id, name="New Name", config=new_config)
  assert updated.name == "New Name"
  assert updated.project_id == "p2"

  # Verify persistence
  fetched = repo.get_by_id(agent.id)
  assert fetched.name == "New Name"
  assert fetched.project_id == "p2"


def test_archive_agent(db_session: Session):
  """Tests archiving an agent."""
  repo = AgentRepository(db_session)
  config = AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  agent = repo.create(name="Old Bot", config=config)

  repo.archive(agent.id)

  fetched = repo.get_by_id(agent.id)
  assert fetched.is_archived

  # Check listing excludes archived
  all_agents = repo.list_all(include_archived=False)
  assert agent not in all_agents

  all_start = repo.list_all(include_archived=True)
  assert agent in all_start
