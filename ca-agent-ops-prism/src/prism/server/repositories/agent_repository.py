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
    """Inserts an agent and commits, so the caller gets its id back populated.

    Golden queries have no column of their own. They are folded into
    datasource_config, which is why they are assembled here rather than
    passed straight through.
    """
    datasource_config = None
    if config.datasource:
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
    """Reads one agent, archived or not. None if there is no such row."""
    return self.session.get(Agent, agent_id)

  def list_all(self, include_archived: bool = False) -> list[Agent]:
    """Lists agents, archived ones only when asked for."""
    query = self.session.query(Agent)
    if not include_archived:
      query = query.filter(
          Agent.is_archived == False  # pylint: disable=singleton-comparison
      )
    return query.all()

  def update(
      self,
      agent_id: int,
      name: str | None = None,
      config: AgentConfig | None = None,
  ) -> Agent:
    """Applies the fields the caller passed, per the rules noted below.

    Most fields are keep-if-absent, golden_queries among them: an update that
    does not mention them keeps the stored ones, and an explicit empty list
    clears them. The datasource is the exception. A config with no datasource
    clears the stored one, and the golden queries go with it, because they are
    kept inside it.

    Raises:
      ValueError: If there is no agent with that id.
    """
    agent = self.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    if name is not None:
      agent.name = name

    if config is not None:
      # Read before the datasource assignment below replaces the dict these
      # live in.
      stored_golden_queries = (agent.datasource_config or {}).get(
          "golden_queries"
      )

      # These three are NOT NULL on the table but optional on the schema, and
      # the edit form sends a config built from scratch when it could not read
      # the stored one. Writing the Nones through raised IntegrityError at
      # commit. Same treatment as the Looker fields below: absent means keep.
      if config.project_id is not None:
        agent.project_id = config.project_id
      # Not "is not None": AgentConfig coerces an unset location to "global",
      # so the None check above can never be false for this one field, and an
      # agent in us-central1 was being moved to global by any edit that built
      # a config from scratch. model_fields_set holds only what the caller
      # actually passed, which is the question being asked here.
      if "location" in config.model_fields_set:
        agent.location = config.location
      if config.agent_resource_id is not None:
        agent.agent_resource_id = config.agent_resource_id
      if config.datasource:
        agent.datasource_config = config.datasource.model_dump()
      else:
        agent.datasource_config = None

      if config.looker_client_id is not None:
        agent.looker_client_id = config.looker_client_id

      if config.looker_client_secret is not None:
        agent.looker_client_secret = config.looker_client_secret

      # Golden queries live inside datasource_config, so start from whatever
      # the block above left there.
      if "golden_queries" in config.model_fields_set:
        # An empty list clears the stored queries. None does too: the field is
        # optional, and a caller that named it and passed nothing means it.
        golden_queries = [
            gq.model_dump(mode="json") for gq in config.golden_queries or []
        ]
      elif agent.datasource_config is not None:
        # Not "is not None" on the value: AgentConfig defaults golden_queries
        # to None, so an edit form that only changed the explore sent None and
        # the assignment above had already dropped the stored queries out of
        # datasource_config. Every golden query on the agent went with it, and
        # the next run's check_looker_query_match assertions all failed.
        golden_queries = stored_golden_queries
      else:
        golden_queries = None

      if golden_queries is not None:
        current_ds = (
            agent.datasource_config.copy() if agent.datasource_config else {}
        )
        current_ds["golden_queries"] = golden_queries
        agent.datasource_config = current_ds

    self.session.commit()
    self.session.refresh(agent)
    return agent

  def archive(self, agent_id: int) -> Agent:
    """Hides an agent from list_all. Raises ValueError if there is no row."""
    agent = self.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    agent.is_archived = True
    self.session.commit()
    self.session.refresh(agent)
    return agent

  def unarchive(self, agent_id: int) -> Agent:
    """Puts an agent back in list_all. Raises ValueError if there is no row."""
    agent = self.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    agent.is_archived = False
    self.session.commit()
    self.session.refresh(agent)
    return agent
