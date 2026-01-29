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

"""Agents Client implementation."""

from typing import Any
from typing import Sequence

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import agent as agent_schemas
from prism.server.services.agent_service import AgentService


def _map_agent(model: Any) -> agent_schemas.Agent:
  """Maps an agent model to an agent schema."""

  if isinstance(model, agent_schemas.Agent):
    return model

  # If it looks like a flat SQLAlchemy model (has project_id)
  if hasattr(model, "project_id") or (
      isinstance(model, dict) and "project_id" in model
  ):
    # Helper to get values from either object or dict
    def gv(key: str, default: Any = None) -> Any:
      if isinstance(model, dict):
        return model.get(key, default)
      return getattr(model, key, default)

    ds_config = gv("datasource_config")
    datasource = None
    if ds_config:
      if "tables" in ds_config:
        datasource = agent_schemas.BigQueryConfig(**ds_config)
      elif "instance_uri" in ds_config:
        datasource = agent_schemas.LookerConfig(**ds_config)

    try:
      return agent_schemas.Agent(
          id=gv("id"),
          name=gv("name"),
          config=agent_schemas.AgentConfig(
              project_id=gv("project_id"),
              location=gv("location"),
              agent_resource_id=gv("agent_resource_id"),
              env=gv("env"),
              datasource=datasource,
              looker_client_id=gv("looker_client_id"),
              looker_client_secret=gv("looker_client_secret"),
          ),
          created_at=gv("created_at"),
          modified_at=gv("modified_at"),
          is_archived=gv("is_archived", False),
      )
    except Exception:  # pylint: disable=broad-exception-caught
      pass

  # Fallback to standard validation
  return agent_schemas.Agent.model_validate(model)


class AgentsClient:
  """Agents Client implementation."""

  @inject
  def list_agents(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> Sequence[agent_schemas.Agent]:
    models = service.list_agents()
    return [_map_agent(m) for m in models]

  @inject
  def get_agent(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent | None:
    model = service.get_agent(agent_id)
    result = _map_agent(model) if model else None
    print(result)
    return result

  @inject
  def create_agent(
      self,
      name: str,
      config: agent_schemas.AgentConfig,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Creates a new agent."""
    model = service.create_agent(
        name=name,
        config=config,
    )
    return _map_agent(model)

  @inject
  def update_agent(
      self,
      agent_id: int,
      name: str | None = None,
      config: agent_schemas.AgentConfig | None = None,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Updates an agent."""
    model = service.update_agent(
        agent_id=agent_id,
        name=name,
        config=config,
    )
    return _map_agent(model)

  @inject
  def get_unique_datasources(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.UniqueDatasources:
    return service.get_unique_datasources()

  @inject
  def get_unique_project_ids(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> list[str]:
    return service.get_unique_project_ids()

  @inject
  def get_configured_gda_projects(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> list[str]:
    return service.get_configured_gda_projects()

  @inject
  def register_gcp_agent(
      self,
      name: str,
      config: agent_schemas.AgentConfig,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    model = service.register_gcp_agent(name=name, config=config)
    return _map_agent(model)

  @inject
  def onboard_gcp_agent(
      self,
      name: str,
      config: agent_schemas.AgentConfig,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    model = service.onboard_gcp_agent(name=name, config=config)
    return _map_agent(model)

  @inject
  def get_current_gcp_project(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> str | None:
    """Identifies the current GCP project ID."""
    return service.get_current_gcp_project()

  @inject
  def list_gda_agents(
      self,
      project_id: str,
      location: str,
      env: str,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> Sequence[agent_schemas.AgentBase]:
    return service.discover_gcp_agents(
        project_id=project_id, location=location, env=env
    )

  @inject
  def get_gcp_agent_details(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.AgentBase | None:
    return service.get_gcp_agent_details(agent_id)

  @inject
  def get_published_context(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> dict[str, Any] | None:
    """Retrieves the raw published context from GCP."""
    return service.get_published_context(agent_id)

  @inject
  def is_looker_agent(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> bool:
    """Returns True if the agent is a Looker agent."""
    return service.is_looker_agent(agent_id)

  @inject
  def has_looker_credentials(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> bool:
    """Returns True if the Looker agent has valid credentials."""
    return service.has_looker_credentials(agent_id)

  @inject
  def duplicate_agent(
      self,
      agent_id: int,
      new_name: str,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Duplicates an agent."""
    model = service.duplicate_agent(agent_id=agent_id, new_name=new_name)
    return _map_agent(model)

  @inject
  def test_looker_credentials(
      self,
      instance_uri: str,
      client_id: str,
      client_secret: str,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> dict[str, Any]:
    """Tests Looker credentials."""
    return service.test_looker_credentials(
        instance_uri=instance_uri,
        client_id=client_id,
        client_secret=client_secret,
    )
