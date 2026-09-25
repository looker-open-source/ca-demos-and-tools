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

from concurrent import futures
import logging
from typing import Any
from typing import Sequence

from google.api_core import exceptions as gcp_exceptions
import google.auth
from google.cloud import bigquery
import looker_sdk
from looker_sdk.rtl import api_settings as looker_settings
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import normalize_location
from prism.server.clients.gemini_data_analytics_client import (
    GeminiDataAnalyticsClient,
)
from prism.server.config import settings
from prism.server.models.agent import Agent
from prism.server.repositories.agent_repository import AgentRepository
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# What a failed BigQuery check may say on the page. prism has no
# authentication, so an alert body is readable by anyone who can reach the
# port, and a BigQuery error names the dataset, the table and the service
# account that was refused.
_BQ_UNREACHABLE = "Could not reach BigQuery. The details are in the server log."
_BQ_CHECK_FAILED = (
    "Could not check this table. The details are in the server log."
)


def _looker_failure_message(e: Exception) -> str:
  """What a failed Looker credentials test may say on the page.

  The SDK reports a bad credential and a host it could not open as the same
  SDKError, and the text of the second one is the connection pool's, carrying
  the instance hostname. Both callers render this message verbatim in an
  alert, so the exception text is read here and never shown.
  """
  text = str(e).lower()
  if "certificate" in text or "sslerror" in text or "ssl:" in text:
    return (
        "Could not verify the Looker instance's TLS certificate. The details"
        " are in the server log."
    )
  if (
      "max retries exceeded" in text
      or "connection" in text
      or "timed out" in text
      or "name or service not known" in text
  ):
    return (
        "Could not reach the Looker instance. Check the instance URI. The"
        " details are in the server log."
    )
  return (
      "Authentication failed. Check the client ID and secret. The details are"
      " in the server log."
  )


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
    loc = normalize_location(config.location)
    config.location = loc
    parent = f"projects/{config.project_id}/locations/{loc}"

    # A client per call, closed on the way out. Each one is a gRPC channel and
    # a thread pool, and the gunicorn worker lives for as long as the
    # container, so the ones this used to drop piled up until Cloud Run killed
    # it mid-run.
    with GeminiDataAnalyticsClient(project=parent) as client:
      gcp_agent_base = client.create_agent(display_name=name, config=config)

    # GCP does not return the secrets, so carry them over from what was sent.
    gcp_agent_base.config.looker_client_id = config.looker_client_id
    gcp_agent_base.config.looker_client_secret = config.looker_client_secret

    return self.agent_repository.create(
        name=name,
        config=gcp_agent_base.config,
    )

  def onboard_gcp_agent(self, name: str, config: AgentConfig) -> Agent:
    """Onboards an already existing GCP agent into the local database.

    The system instruction is left on GCP. The Agent table has no column for
    it, and get_gcp_agent_details reads it from GCP when a caller needs it, so
    a local copy would only go stale.

    Args:
      name: Display name for the agent.
      config: Full GCP configuration for the agent.

    Returns:
      The created Agent database entity.
    """
    # Copy the config so the caller's object is not mutated.
    local_config = config.model_copy()
    local_config.location = normalize_location(local_config.location)
    local_config.system_instruction = None

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

    loc = normalize_location(agent.location)
    parent = f"projects/{agent.project_id}/locations/{loc}"

    agent_name = f"{parent}/dataAgents/{agent.agent_resource_id}"
    with GeminiDataAnalyticsClient(project=parent) as client:
      gcp_agent = client.get_agent(agent_name)

    if gcp_agent and gcp_agent.config:
      # GCP does not return the secrets, so fill them from the local row.
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

    loc = normalize_location(agent.location)
    parent = f"projects/{agent.project_id}/locations/{loc}"

    agent_name = f"{parent}/dataAgents/{agent.agent_resource_id}"
    with GeminiDataAnalyticsClient(project=parent) as client:
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

    # Only when the caller passed one. Assigning here would add "location" to
    # model_fields_set, and AgentRepository.update reads that set to decide
    # whether the stored location is being changed or left alone.
    if config and "location" in config.model_fields_set:
      config.location = normalize_location(config.location)

    # Only a system instruction triggers the GCP update. A config without one
    # is persisted locally only, which would leave a datasource or golden
    # query edit unpublished. A blank one is not the same as none: it is
    # published, and it overwrites. The Edit button on the detail page stays
    # disabled unless fetch_remote_config loaded the GCP config, which is the
    # only source the textarea is filled from, so the form cannot submit an
    # instruction it never read. submit_edit is the only caller.
    system_instruction = config.system_instruction if config else None
    if system_instruction is not None:
      loc = normalize_location(agent.location)
      parent = f"projects/{agent.project_id}/locations/{loc}"
      agent_name = f"{parent}/dataAgents/{agent.agent_resource_id}"
      with GeminiDataAnalyticsClient(project=parent) as client:
        client.update_agent(
            agent_name=agent_name,
            system_instruction=system_instruction,
            config=config,
        )

    return self.agent_repository.update(
        agent_id=agent_id,
        name=name,
        config=config,
    )

  def archive_agent(self, agent_id: int) -> Agent:
    """Archives an agent."""
    return self.agent_repository.archive(agent_id=agent_id)

  def unarchive_agent(self, agent_id: int) -> Agent:
    """Unarchives an agent."""
    return self.agent_repository.unarchive(agent_id=agent_id)

  def get_configured_gda_projects(self) -> list[str]:
    """Returns the list of GDA projects from app settings."""
    return settings.gcp_gda_projects

  def get_current_gcp_project(self) -> str | None:
    """Identifies the current GCP project ID using ADC."""
    try:
      _, project_id = google.auth.default()
      return project_id
    except Exception:  # pylint: disable=broad-except
      return None

  def discover_gcp_agents(
      self, project_id: str, location: str | None = None
  ) -> Sequence[AgentBase]:
    """Lists available agents from GCP across supported locations."""
    if location and location not in ("all", "both"):
      locations = [normalize_location(location)]
    else:
      locations = settings.gcp_gda_locations

    if not locations:
      return []

    seen_keys: set[tuple[str, str]] = set()
    all_agents: list[AgentBase] = []
    failed_locations: list[str] = []

    def _fetch_location_agents(loc: str) -> list[AgentBase]:
      parent = f"projects/{project_id}/locations/{loc}"
      client = None
      try:
        client = GeminiDataAnalyticsClient(project=parent)
        return client.list_agents()
      except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "Failed to discover GCP agents in %s for project %s: %s",
            loc,
            project_id,
            e,
        )
        failed_locations.append(loc)
        return []
      finally:
        # One client per location per sweep, and the settings page sweeps on
        # every load. The channels were never released.
        if client is not None:
          client.close()

    def _add_agents(agent_list: list[AgentBase]):
      for agent in agent_list:
        loc = (
            agent.config.location
            if agent.config and agent.config.location
            else "global"
        )
        res_id = agent.config.agent_resource_id if agent.config else agent.name
        key = (loc, res_id)
        if key not in seen_keys:
          seen_keys.add(key)
          all_agents.append(agent)

    if len(locations) > 1:
      with futures.ThreadPoolExecutor(
          max_workers=min(len(locations), 8)
      ) as pool:
        for result in pool.map(_fetch_location_agents, locations):
          _add_agents(result)
    else:
      _add_agents(_fetch_location_agents(locations[0]))

    # One location down is worth a log and the agents from the others. Every
    # location down is not a project with no agents in it, which is what the
    # empty list told the user.
    if len(failed_locations) == len(locations):
      raise RuntimeError(
          f"Could not list agents in project {project_id}. Every location"
          f" failed ({', '.join(failed_locations)}); the cause is in the"
          " server log."
      )

    return all_agents

  def is_looker_agent(self, agent_id: int) -> bool:
    """Returns True if the agent is a Looker agent."""
    agent = self.get_agent(agent_id)
    if not agent or not agent.datasource_config:
      return False
    return "instance_uri" in agent.datasource_config

  def has_looker_credentials(self, agent_id: int) -> bool:
    """Returns True unless a Looker agent is missing its id or its secret.

    Only checks that the two fields are set. Nothing here talks to Looker, so
    a wrong id or a revoked secret still passes.
    """
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
    # GCP does not return the secrets, so fill them from the local row.
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
      agent_id: int | None = None,
  ) -> dict[str, Any]:
    """Tests Looker credentials using looker-sdk.

    Args:
      instance_uri: Looker instance URI.
      client_id: Looker client ID.
      client_secret: Looker client secret.
      agent_id: Fills a blank secret from the stored row. The edit modal never
        renders the stored secret, so blank there means keep it, the same
        contract update_agent follows. Without this the button refused the one
        case it exists for, testing the credentials an agent already has, and
        the only way past it was to retype the value the UI will not show.

    Returns:
      A dict with 'success' (bool) and 'message' (str). Both callers render
      the message verbatim, so a failure names the kind of failure and leaves
      the SDK error in the server log.
    """
    if not client_secret and agent_id is not None:
      agent = self.get_agent(agent_id)
      if agent:
        client_secret = agent.looker_client_secret or ""

    if not client_secret:
      return {
          "success": False,
          "message": "No client secret to test. Enter one and try again.",
      }

    class _LookerSettings(looker_settings.ApiSettings):
      """Internal settings class for dynamic config."""

      def __init__(self, base_url: str, c_id: str, c_secret: str, **kwargs):
        self._custom_base_url = base_url
        self._custom_client_id = c_id
        self._custom_client_secret = c_secret
        super().__init__(**kwargs)

      def read_config(self) -> looker_settings.SettingsConfig:
        # verify_ssl stays on. This posts the client id and secret to whatever
        # instance_uri the form was given, so the certificate is the only thing
        # saying the host is the Looker instance the user meant.
        return {
            "base_url": self._custom_base_url,
            "client_id": self._custom_client_id,
            "client_secret": self._custom_client_secret,
            "verify_ssl": "True",
        }

    try:
      custom_settings = _LookerSettings(
          base_url=instance_uri,
          c_id=client_id,
          c_secret=client_secret,
      )
      sdk = looker_sdk.init40(config_settings=custom_settings)
      # The call is the test. Its answer is the name and email of the person
      # behind the client id, and the alert that shows this is on a screen
      # people screenshot into bugs, so none of that is repeated back.
      sdk.me()
      return {
          "success": True,
          "message": "Connected to the Looker instance.",
      }
    except Exception as e:  # pylint: disable=broad-except
      logger.exception("Looker credentials test failed for %s", instance_uri)
      return {"success": False, "message": _looker_failure_message(e)}

  def check_bigquery_tables(
      self, tables: Sequence[str]
  ) -> list[dict[str, str]]:
    """Checks each BigQuery table against BigQuery.

    The form only checks that a path has three dotted parts, so a typo or a
    missing grant first showed up as a run where every trial failed. Not found
    and permission denied are reported apart, because one is fixed by editing
    the path and the other by granting the service account access.

    Args:
      tables: Full table paths, project.dataset.table.

    Returns:
      One result per table, in the order given, with 'table', 'status' and
      'message'. Status is ok, invalid, not_found, denied or error. The
      caller counts these against the tables it passed, so a server with no
      credentials still gets an entry per table rather than one for the list.
    """
    results: list[dict[str, str]] = []
    client = None
    client_failed = False
    try:
      for table in tables:
        parts = table.split(".")
        if len(parts) != 3 or not all(parts):
          results.append({
              "table": table,
              "status": "invalid",
              "message": "Not a project.dataset.table path.",
          })
          continue

        if client is None and not client_failed:
          try:
            # Reading table metadata runs no job, so the client's project only
            # has to exist. The first table's own project always does.
            client = bigquery.Client(project=parts[0])
          except Exception:  # pylint: disable=broad-except
            logger.exception("Could not build a BigQuery client")
            client_failed = True

        if client_failed:
          # No credentials on the server. Every table reports the same thing,
          # and it is reported once per table because the caller counts the
          # entries against the tables it passed. Stopping at the first one
          # showed "1 of 1 tables could not be read" for five unchecked tables.
          results.append({
              "table": table,
              "status": "error",
              "message": _BQ_UNREACHABLE,
          })
          continue

        try:
          client.get_table(table)
          results.append({
              "table": table,
              "status": "ok",
              "message": "Found.",
          })
        except gcp_exceptions.NotFound:
          results.append({
              "table": table,
              "status": "not_found",
              "message": "No such table, or its dataset does not exist.",
          })
        except gcp_exceptions.Forbidden:
          results.append({
              "table": table,
              "status": "denied",
              "message": (
                  "Permission denied. The agent's service account needs"
                  " bigquery.tables.get on this table."
              ),
          })
        except Exception:  # pylint: disable=broad-except
          logger.exception("Checking BigQuery table %s failed", table)
          results.append({
              "table": table,
              "status": "error",
              "message": _BQ_CHECK_FAILED,
          })
    finally:
      # The client holds an HTTP session and a connection pool, and this runs
      # on every save of the agent form inside a worker that outlives the
      # request.
      if client is not None:
        client.close()

    return results
