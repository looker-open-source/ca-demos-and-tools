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

import logging
from typing import Any
from typing import Sequence

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import agent as agent_schemas
from prism.server.services import ai_service
from prism.server.services.agent_service import AgentService

logger = logging.getLogger(__name__)


def _map_agent(model: Any) -> agent_schemas.Agent:
  """Returns an Agent schema for a row, a dict or an Agent.

  The ORM row is flat and the schema nests the connection settings under
  config, so a row has to be rebuilt field by field. Anything else is handed
  to pydantic.
  """

  if isinstance(model, agent_schemas.Agent):
    return model

  # A dict gets the same treatment, because the edit form round-trips the row
  # as one.
  if hasattr(model, "project_id") or (
      isinstance(model, dict) and "project_id" in model
  ):

    def gv(key: str, default: Any = None) -> Any:
      if isinstance(model, dict):
        return model.get(key, default)
      return getattr(model, key, default)

    try:
      ds_config = gv("datasource_config")
      datasource = None
      if ds_config:
        if "tables" in ds_config:
          datasource = agent_schemas.BigQueryConfig(**ds_config)
        elif "instance_uri" in ds_config:
          datasource = agent_schemas.LookerConfig(**ds_config)

      return agent_schemas.Agent(
          id=gv("id"),
          name=gv("name"),
          config=agent_schemas.AgentConfig(
              project_id=gv("project_id"),
              location=gv("location"),
              agent_resource_id=gv("agent_resource_id"),
              datasource=datasource,
              looker_client_id=gv("looker_client_id"),
              looker_client_secret=gv("looker_client_secret"),
              golden_queries=ds_config.get("golden_queries")
              if ds_config
              else None,
          ),
          created_at=gv("created_at"),
          modified_at=gv("modified_at"),
          is_archived=gv("is_archived", False),
      )
    except Exception:
      # Raise, do not fall through. The ORM row carries no config attribute, so
      # the model_validate below always succeeded and handed back an Agent with
      # an empty AgentConfig. A row whose datasource_config failed validation
      # then rendered with no project, no resource id, no datasource and no
      # golden queries, and saving Edit wrote that empty config back over the
      # real one.
      logger.exception("Could not map agent row %s field by field", gv("id"))
      raise

  return agent_schemas.Agent.model_validate(model)


class AgentsClient:
  """Local agent rows, and the GCP agents they are registered against."""

  @inject
  def list_agents(
      self,
      include_archived: bool = False,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> Sequence[agent_schemas.Agent]:
    """Lists agents, archived ones only when asked for."""
    models = service.list_agents(include_archived=include_archived)
    return [_map_agent(m) for m in models]

  @inject
  def get_agent(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent | None:
    """Returns the agent, or None if there is no row with that id."""
    model = service.get_agent(agent_id)
    return _map_agent(model) if model else None

  @inject
  def update_agent(
      self,
      agent_id: int,
      name: str | None = None,
      config: agent_schemas.AgentConfig | None = None,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Updates the agent locally, and on GCP when the config changed."""
    model = service.update_agent(
        agent_id=agent_id,
        name=name,
        config=config,
    )
    return _map_agent(model)

  @inject
  def archive_agent(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Archives the agent, so it drops out of the default listings."""
    model = service.archive_agent(agent_id=agent_id)
    return _map_agent(model)

  @inject
  def unarchive_agent(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Unarchives the agent, putting it back in the default listings."""
    model = service.unarchive_agent(agent_id=agent_id)
    return _map_agent(model)

  @inject
  def get_configured_gda_projects(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> list[str]:
    """Returns the GDA projects the app is configured with."""
    return service.get_configured_gda_projects()

  @inject
  def register_gcp_agent(
      self,
      name: str,
      config: agent_schemas.AgentConfig,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Creates the agent on GCP, then stores it locally."""
    model = service.register_gcp_agent(name=name, config=config)
    return _map_agent(model)

  @inject
  def onboard_gcp_agent(
      self,
      name: str,
      config: agent_schemas.AgentConfig,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Stores an agent that already exists on GCP in the local database."""
    model = service.onboard_gcp_agent(name=name, config=config)
    return _map_agent(model)

  @inject
  def get_current_gcp_project(
      self,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> str | None:
    """Returns the project ADC is configured for, or None if it has none."""
    return service.get_current_gcp_project()

  @inject
  def discover_gcp_agents(
      self,
      project_id: str,
      location: str | None = None,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> Sequence[agent_schemas.AgentBase]:
    """Lists a project's GCP agents across the supported locations."""
    return service.discover_gcp_agents(project_id=project_id, location=location)

  @inject
  def get_gcp_agent_details(
      self,
      agent_id: int,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.AgentBase | None:
    """Reads the agent's live definition from GCP, not from the local row."""
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
  def duplicate_agent(
      self,
      agent_id: int,
      new_name: str,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> agent_schemas.Agent:
    """Copies an existing agent's config under a new name."""
    model = service.duplicate_agent(agent_id=agent_id, new_name=new_name)
    return _map_agent(model)

  @inject
  def test_looker_credentials(
      self,
      instance_uri: str,
      client_id: str,
      client_secret: str,
      agent_id: int | None = None,
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> dict[str, Any]:
    """Tries the credentials against the instance.

    A blank client_secret with an agent_id tests the secret already stored
    against that agent. Returns a dict with 'success' and a 'message', rather
    than raising.
    """
    return service.test_looker_credentials(
        instance_uri=instance_uri,
        client_id=client_id,
        client_secret=client_secret,
        agent_id=agent_id,
    )

  @inject
  def check_bigquery_tables(
      self,
      tables: Sequence[str],
      service: AgentService = Depends(dependencies.get_agent_service),
  ) -> list[dict[str, str]]:
    """Checks BigQuery tables exist and are readable."""
    return service.check_bigquery_tables(tables=tables)

  @inject
  def format_golden_queries_with_ai(
      self,
      text: str,
      service: ai_service.AIService = Depends(dependencies.get_ai_service),
  ) -> str:
    """Asks Gemini to rewrite pasted text as golden queries."""
    return service.format_golden_queries(text)
