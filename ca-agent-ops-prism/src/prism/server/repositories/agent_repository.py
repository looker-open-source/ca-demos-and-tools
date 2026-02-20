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

"""Repository for managing Agent entities."""

import logging

from prism.common.schemas.agent import AgentConfig
from prism.server.models.agent import Agent
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AgentRepository:
  """Repository for Agent operations."""

  def __init__(self, session: Session):
    self.session = session

  def create(
      self,
      name: str,
      config: AgentConfig,
  ) -> Agent:
    """Creates a new agent."""
    datasource_config = None
    if config.datasource:
      # Pydantic model dump
      datasource_config = config.datasource.model_dump()

    if config.golden_queries:
      if datasource_config is None:
        datasource_config = {}
      datasource_config["golden_queries"] = [
          gq.model_dump(mode="json") for gq in config.golden_queries
      ]

    agent = Agent(
        name=name,
        project_id=config.project_id,
        location=config.location,
        agent_resource_id=config.agent_resource_id,
        datasource_config=datasource_config,
        looker_client_id=config.looker_client_id,
        looker_client_secret=config.looker_client_secret,
    )
    self.session.add(agent)
    self.session.commit()
    self.session.refresh(agent)
    logger.info("Created agent in database: %s (ID: %s)", agent.name, agent.id)
    return agent

  def get_by_id(self, agent_id: int) -> Agent | None:
    """Retrieves an agent by ID."""
    return self.session.get(Agent, agent_id)

  def list_all(self, include_archived: bool = False) -> list[Agent]:
    """Lists all agents."""
    query = self.session.query(Agent)
    if not include_archived:
      query = query.filter(Agent.is_archived == False)  # pylint: disable=singleton-comparison
    return query.all()

  def update(
      self,
      agent_id: int,
      name: str | None = None,
      config: AgentConfig | None = None,
  ) -> Agent:
    """Updates an agent."""
    agent = self.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    if name is not None:
      agent.name = name

    if config is not None:
      agent.project_id = config.project_id
      agent.location = config.location
      agent.agent_resource_id = config.agent_resource_id
      if config.datasource:
        agent.datasource_config = config.datasource.model_dump()
      else:
        agent.datasource_config = None

      if config.looker_client_secret is not None:
        agent.looker_client_secret = config.looker_client_secret

      # Store golden_queries in datasource_config if present
      if config.golden_queries is not None and agent.datasource_config:
        # We need to ensure we don't handle this if datasource_config is None,
        # but the previous block sets it to None if config.datasource is None.
        # However, if config.datasource was None, we probably shouldn't have golden queries?
        # Actually GDA allows updates.

        # If we updated datasource above, agent.datasource_config is set.
        current_ds = (
            agent.datasource_config.copy() if agent.datasource_config else {}
        )
        if config.golden_queries:
          current_ds["golden_queries"] = [
              gq.model_dump(mode="json") for gq in config.golden_queries
          ]
        else:
          # Explicitly set to empty list or remove if None/Empty passed?
          # config.golden_queries is a list or None.
          # If empty list, we store empty list.
          current_ds["golden_queries"] = []

        agent.datasource_config = current_ds

    self.session.commit()
    self.session.refresh(agent)
    return agent

  def archive(self, agent_id: int) -> Agent:
    """Archives an agent."""
    agent = self.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    agent.is_archived = True
    self.session.commit()
    self.session.refresh(agent)
    return agent

  def unarchive(self, agent_id: int) -> Agent:
    """Unarchives an agent."""
    agent = self.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    agent.is_archived = False
    self.session.commit()
    self.session.refresh(agent)
    return agent
