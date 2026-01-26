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

"""Service for managing Agents."""

from __future__ import annotations

import logging
from typing import Any
from typing import Sequence

from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import UniqueDatasources
from prism.server.clients.gemini_data_analytics_client import ClientEnv
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.config import settings
from prism.server.models.agent import Agent
from prism.server.repositories.agent_repository import AgentRepository
from sqlalchemy.orm import Session

try:
  import google.auth
except ImportError:
  google = None

try:
  import looker_sdk
  from looker_sdk.rtl import api_settings as looker_settings
except ImportError:
  looker_sdk = None
  looker_settings = None


class AgentService:
  """Service for Agent operations."""

  def __init__(
      self,
      session: Session,
      agent_repository: AgentRepository,
  ):
    """Initializes the AgentService."""
    self.session = session
    self.agent_repository = agent_repository

  def create_agent(
      self,
      name: str,
      config: AgentConfig,
  ) -> Agent:
    """Creates a new agent record in the local database."""
    return self.agent_repository.create(
        name=name,
        config=config,
    )

  def register_gcp_agent(self, name: str, config: AgentConfig) -> Agent:
    """Creates an agent on GCP and then persists it locally."""
    parent = f"projects/{config.project_id}/locations/{config.location}"
    client = GeminiDataAnalyticsClient(
        project=parent, env=ClientEnv(config.env)
    )

    # 1. Create on GCP
    gcp_agent_base = client.create_agent(display_name=name, config=config)

    # Move credentials from original config to returned config
    # (GCP doesn't return secrets)
    gcp_agent_base.config.looker_client_id = config.looker_client_id
    gcp_agent_base.config.looker_client_secret = config.looker_client_secret

    # 2. Persist locally with the returned resource information
    return self.agent_repository.create(
        name=name,
        config=gcp_agent_base.config,
    )

  def onboard_gcp_agent(self, name: str, config: AgentConfig) -> Agent:
    """Onboards an already existing GCP agent into the local database.

    Note: We do NOT persist system_instruction locally per requirement.

    Args:
      name: Display name for the agent.
      config: Full GCP configuration for the agent.

    Returns:
      The created Agent database entity.
    """
    # Create copy of config to avoid mutating original if needed,
    # though schemas are usually fine to pass around.
    local_config = config.model_copy()
    local_config.system_instruction = None  # Do not persist

    return self.agent_repository.create(name=name, config=local_config)

  def get_agent(self, agent_id: int) -> Agent | None:
    """Retrieves an agent by ID."""
    return self.agent_repository.get_by_id(agent_id)

  def list_agents(self, include_archived: bool = False) -> Sequence[Agent]:
    """Lists all agents."""
    return self.agent_repository.list_all(include_archived=include_archived)

  def get_gcp_agent_details(self, agent_id: int) -> AgentBase | None:
    """Retrieves full agent details from GCP for a local agent."""
    agent = self.get_agent(agent_id)
    if not agent:
      return None

    parent = f"projects/{agent.project_id}/locations/{agent.location}"
    client = GeminiDataAnalyticsClient(project=parent, env=ClientEnv(agent.env))

    agent_name = f"{parent}/dataAgents/{agent.agent_resource_id}"
    gcp_agent = client.get_agent(agent_name)

    if gcp_agent and gcp_agent.config:
      # Merge credentials from local DB
      if not gcp_agent.config.looker_client_id:
        gcp_agent.config.looker_client_id = agent.looker_client_id
      if not gcp_agent.config.looker_client_secret:
        gcp_agent.config.looker_client_secret = agent.looker_client_secret

    return gcp_agent

  def get_published_context(self, agent_id: int) -> dict[str, Any] | None:
    """Retrieves the raw published context from GCP for a local agent."""
    agent = self.get_agent(agent_id)
    if not agent:
      return None

    parent = f"projects/{agent.project_id}/locations/{agent.location}"
    client = GeminiDataAnalyticsClient(project=parent, env=ClientEnv(agent.env))

    agent_name = f"{parent}/dataAgents/{agent.agent_resource_id}"
    return client.get_agent_context(agent_name, context_target="published")

  def update_agent(
      self,
      agent_id: int,
      name: str | None = None,
      config: AgentConfig | None = None,
  ) -> Agent:
    """Updates an existing agent locally and on GCP if needed."""
    agent = self.get_agent(agent_id)
    if not agent:
      raise ValueError(f"Agent {agent_id} not found")

    # 1. Update on GCP if instruction or config provided
    system_instruction = config.system_instruction if config else None
    if system_instruction is not None:
      parent = f"projects/{agent.project_id}/locations/{agent.location}"
      client = GeminiDataAnalyticsClient(
          project=parent, env=ClientEnv(agent.env)
      )
      agent_name = f"{parent}/dataAgents/{agent.agent_resource_id}"
      client.update_agent(
          agent_name=agent_name,
          system_instruction=system_instruction,
          config=config,
      )

    # 2. Update local DB
    return self.agent_repository.update(
        agent_id=agent_id,
        name=name,
        config=config,
    )

  def archive_agent(self, agent_id: int) -> Agent:
    """Archives an agent."""
    return self.agent_repository.archive(agent_id=agent_id)

  def get_unique_datasources(self) -> UniqueDatasources:
    """Returns unique datasource names grouped by type (BQ, Looker)."""
    agents = self.list_agents()
    bq_sources = set()
    looker_sources = set()

    for a in agents:
      config = a.datasource_config
      if not config:
        continue

      # Heuristic to determine type from JSON config
      if "tables" in config:
        # For BQ, we might have multiple tables.
        # For now, let's just use the table name.
        for table in config.get("tables", []):
          bq_sources.add(table)
      elif "instance_uri" in config:
        looker_sources.add(config["instance_uri"])

    return UniqueDatasources(
        bq=sorted(list(bq_sources)),
        looker=sorted(list(looker_sources)),
    )

  def get_unique_project_ids(self) -> list[str]:
    """Returns a unique set of all project IDs from monitored agents."""
    agents = self.list_agents()
    return sorted(list(set(a.project_id for a in agents)))

  def get_configured_gda_projects(self) -> list[str]:
    """Returns the list of GDA projects from app settings."""
    return settings.gcp_gda_projects

  def get_current_gcp_project(self) -> str | None:
    """Identifies the current GCP project ID using ADC."""
    if not google:
      return None
    try:
      _, project_id = google.auth.default()
      return project_id
    except Exception:  # pylint: disable=broad-except
      return None

  def discover_gcp_agents(
      self, project_id: str, location: str, env: str
  ) -> Sequence[AgentBase]:
    """Lists available agents from GCP."""
    parent = f"projects/{project_id}/locations/{location}"
    client = GeminiDataAnalyticsClient(project=parent, env=ClientEnv(env))
    return client.list_agents()

  def is_looker_agent(self, agent_id: int) -> bool:
    """Returns True if the agent is a Looker agent."""
    agent = self.get_agent(agent_id)
    if not agent or not agent.datasource_config:
      return False
    return "instance_uri" in agent.datasource_config

  def has_looker_credentials(self, agent_id: int) -> bool:
    """Returns True if the Looker agent has valid credentials."""
    agent = self.get_agent(agent_id)
    if not agent or not self.is_looker_agent(agent_id):
      return True  # Not a Looker agent, so it "has" what it needs (nothing)
    return bool(agent.looker_client_id and agent.looker_client_secret)

  def duplicate_agent(self, agent_id: int, new_name: str) -> Agent:
    """Duplicates an existing agent with a new name.

    Args:
      agent_id: ID of the agent to duplicate.
      new_name: Name for the new agent.

    Returns:
      The newly created Agent.
    """
    agent = self.get_agent(agent_id)
    if not agent:
      raise ValueError(f"Agent {agent_id} not found")

    gcp_details = self.get_gcp_agent_details(agent_id)
    if not gcp_details or not gcp_details.config:
      raise ValueError(f"Full config for agent {agent_id} not found on GCP")

    config = gcp_details.config.model_copy()
    # Pull secrets from local DB if missing (GCP doesn't return them)
    if not config.looker_client_id:
      config.looker_client_id = agent.looker_client_id
    if not config.looker_client_secret:
      config.looker_client_secret = agent.looker_client_secret

    return self.register_gcp_agent(name=new_name, config=config)

  def test_looker_credentials(
      self,
      instance_uri: str,
      client_id: str,
      client_secret: str,
  ) -> dict[str, Any]:
    """Tests Looker credentials using looker-sdk.

    Args:
      instance_uri: Looker instance URI.
      client_id: Looker client ID.
      client_secret: Looker client secret.

    Returns:
      A dict with 'success' (bool) and 'message' (str).
    """
    if not looker_sdk or not looker_settings:
      return {
          "success": False,
          "message": "looker-sdk is not installed on the server.",
      }

    class _LookerSettings(looker_settings.ApiSettings):
      """Internal settings class for dynamic config."""

      def __init__(self, base_url: str, c_id: str, c_secret: str, **kwargs):
        self._custom_base_url = base_url
        self._custom_client_id = c_id
        self._custom_client_secret = c_secret
        super().__init__(**kwargs)

      def read_config(self) -> looker_settings.SettingsConfig:
        return {
            "base_url": self._custom_base_url,
            "client_id": self._custom_client_id,
            "client_secret": self._custom_client_secret,
            "verify_ssl": "False",
        }

    try:
      settings = _LookerSettings(
          base_url=instance_uri,
          c_id=client_id,
          c_secret=client_secret,
      )
      sdk = looker_sdk.init40(config_settings=settings)
      me = sdk.me()
      return {
          "success": True,
          "message": (
              f"Successfully authenticated as {me.first_name} {me.last_name}"
              f" ({me.email})"
          ),
      }
    except Exception as e:  # pylint: disable=broad-except
      return {"success": False, "message": f"Authentication failed: {str(e)}"}
