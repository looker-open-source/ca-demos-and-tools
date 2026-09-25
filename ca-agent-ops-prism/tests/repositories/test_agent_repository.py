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

"""Unit tests for AgentRepository."""

from prism.common.schemas.agent import AgentConfig
from prism.server.repositories.agent_repository import AgentRepository
from sqlalchemy.orm import Session


def test_create_agent(db_session: Session):
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

  fetched = repo.get_by_id(agent.id)
  assert fetched.name == "New Name"
  assert fetched.project_id == "p2"


def test_update_keeps_the_location_the_caller_did_not_mention(
    db_session: Session,
):
  """An edit that says nothing about location must not move the agent.

  AgentConfig defaults an unset location to "global", so a config built from
  scratch is indistinguishable from one that asked for global by value alone.
  The edit form sends exactly that, and it was relocating every regional
  agent it touched.
  """
  repo = AgentRepository(db_session)
  agent = repo.create(
      name="Regional Bot",
      config=AgentConfig(
          project_id="p",
          location="us-central1",
          agent_resource_id="r",
      ),
  )

  repo.update(agent.id, config=AgentConfig(project_id="p2"))

  fetched = repo.get_by_id(agent.id)
  assert fetched.location == "us-central1"
  assert fetched.project_id == "p2"


def test_update_moves_the_agent_when_the_caller_passes_a_location(
    db_session: Session,
):
  repo = AgentRepository(db_session)
  agent = repo.create(
      name="Moving Bot",
      config=AgentConfig(
          project_id="p",
          location="us-central1",
          agent_resource_id="r",
      ),
  )

  repo.update(agent.id, config=AgentConfig(project_id="p", location="global"))

  assert repo.get_by_id(agent.id).location == "global"


def test_archive_agent(db_session: Session):
  """Archiving hides the agent from list_all unless it asks for archived."""
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

  all_agents = repo.list_all(include_archived=False)
  assert agent not in all_agents

  with_archived = repo.list_all(include_archived=True)
  assert agent in with_archived
