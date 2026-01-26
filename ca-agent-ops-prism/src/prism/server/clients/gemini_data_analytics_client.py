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

"""Client for interacting with the Google Gemini Data Analytics API."""

import enum
import logging
import re
import time
from typing import Any

from google.api_core import client_options
import google.auth
from google.auth import exceptions as auth_exceptions
from google.cloud import geminidataanalytics
from google.protobuf import field_mask_pb2
from google.protobuf import json_format
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import AgentEnv
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics


class ClientEnv(str, enum.Enum):
  """Environment for the Gemini Data Analytics Client."""

  PROD = "prod"
  STAGING = "staging"
  AUTOPUSH = "autopush"


class GeminiDataAnalyticsClient:
  """A client for interacting with the Google Gemini Data Analytics API."""

  def __init__(self, project: str, env: ClientEnv):
    """Initializes the GeminiDataAnalyticsClient.

    Args:
        project: The project and location, e.g.,
          'projects/my-project/locations/us-central1'.
        env: The API environment to target.
    """
    try:
      _, project_id = google.auth.default()
      logging.debug(
          "[Auth] Successfully found credentials. Authenticated project: %s",
          project_id,
      )
    except auth_exceptions.DefaultCredentialsError as e:
      logging.error("[Auth] Failed to find default credentials: %s", e)

    self.project = project
    self.env = env
    options = None

    match env:
      case ClientEnv.STAGING:
        endpoint = "staging-geminidataanalytics.sandbox.googleapis.com"
        options = client_options.ClientOptions(api_endpoint=endpoint)
      case ClientEnv.AUTOPUSH:
        endpoint = "autopush-geminidataanalytics.sandbox.googleapis.com"
        options = client_options.ClientOptions(api_endpoint=endpoint)
      case ClientEnv.PROD:
        pass

    self.chat_client = geminidataanalytics.DataChatServiceClient(
        client_options=options
    )
    self.agent_client = geminidataanalytics.DataAgentServiceClient(
        client_options=options
    )

  def _pb_to_agent_base(self, agent_pb: Any) -> AgentBase | None:
    """Converts a DataAgent protobuf to an AgentBase schema."""
    if not agent_pb:
      return None

    # Parse resource name: projects/{p}/locations/{l}/dataAgents/{r}
    # Pattern: projects/([^/]+)/locations/([^/]+)/dataAgents/([^/]+)
    match = re.match(
        r"projects/([^/]+)/locations/([^/]+)/dataAgents/([^/]+)", agent_pb.name
    )
    if not match:
      logging.warning("Failed to parse agent resource name: %s", agent_pb.name)
      return None

    project_id, location, agent_resource_id = match.groups()

    # Determine Env (Best effort mapping)
    if self.env == ClientEnv.PROD:
      agent_env = AgentEnv.PROD
    else:
      agent_env = AgentEnv.STAGING

    # Parse Datasource
    datasource = None
    system_instruction = None

    # We prefer published_context
    da_agent = getattr(agent_pb, "data_analytics_agent", None)
    if da_agent:
      context = getattr(da_agent, "published_context", None)
      if context:
        system_instruction = context.system_instruction
        refs = getattr(context, "datasource_references", None)
        if refs:
          # BigQuery
          if refs.bq and refs.bq.table_references:
            tables = []
            for t in refs.bq.table_references:
              tables.append(f"{t.project_id}.{t.dataset_id}.{t.table_id}")
            datasource = BigQueryConfig(tables=tables)
          # Looker
          elif refs.looker and refs.looker.explore_references:
            explores = []
            instance_uri = ""
            for e in refs.looker.explore_references:
              explores.append(f"{e.lookml_model}.{e.explore}")
              if not instance_uri:
                instance_uri = e.looker_instance_uri

            if instance_uri:
              datasource = LookerConfig(
                  instance_uri=instance_uri,
                  explores=explores,
              )

    config = AgentConfig(
        project_id=project_id,
        location=location,
        agent_resource_id=agent_resource_id,
        env=agent_env,
        datasource=datasource,
        system_instruction=system_instruction,
    )

    return AgentBase(name=agent_pb.display_name, config=config)

  def list_agents(self) -> list[AgentBase]:
    """Lists all data agents for the configured project.

    Returns:
        A list of AgentBase objects.
    """
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=self.project,
    )
    agents = []
    try:
      pager = self.agent_client.list_data_agents(request=request)
      for agent in pager:
        agent_obj = self._pb_to_agent_base(agent)
        if agent_obj:
          agents.append(agent_obj)
    except Exception as e:  # pylint: disable=broad-except
      logging.error("An error occurred while listing agents: %s", e)
    return agents

  def _get_datasource_references(
      self, config: AgentConfig
  ) -> geminidataanalytics.DatasourceReferences | None:
    """Converts AgentConfig.datasource to DatasourceReferences."""
    if isinstance(config.datasource, BigQueryConfig):
      table_refs = []
      for table_str in config.datasource.tables:
        # Expecting "project.dataset.table"
        parts = table_str.split(".")
        if len(parts) != 3:
          raise ValueError(
              f"Invalid BigQuery table format: '{table_str}'. "
              "Expected 'project.dataset.table'."
          )
        project_id, dataset_id, table_id = parts
        table_refs.append(
            geminidataanalytics.BigQueryTableReference(
                project_id=project_id,
                dataset_id=dataset_id,
                table_id=table_id,
            )
        )
      bq_references = geminidataanalytics.BigQueryTableReferences(
          table_references=table_refs
      )
      return geminidataanalytics.DatasourceReferences(bq=bq_references)

    elif isinstance(config.datasource, LookerConfig):
      explore_refs = []
      for explore_str in config.datasource.explores:
        model, explore = explore_str.split(".")
        explore_refs.append(
            geminidataanalytics.LookerExploreReference(
                looker_instance_uri=config.datasource.instance_uri,
                lookml_model=model,
                explore=explore,
            )
        )
      looker_references = geminidataanalytics.LookerExploreReferences(
          explore_references=explore_refs
      )
      return geminidataanalytics.DatasourceReferences(looker=looker_references)

    return None

  def create_agent(
      self,
      display_name: str,
      config: AgentConfig,
      data_agent_id: str | None = None,
  ) -> AgentBase:
    """Creates a new data agent.

    Args:
        display_name: The display name of the data agent.
        config: Agent configuration including datasource.
        data_agent_id: Optional. The ID of the data agent to create.

    Returns:
        The created AgentBase.
    """
    datasource_references = self._get_datasource_references(config)

    context = geminidataanalytics.Context(
        system_instruction=config.system_instruction or "",
        datasource_references=datasource_references,
    )
    data_analytics_agent = geminidataanalytics.DataAnalyticsAgent(
        published_context=context
    )
    data_agent = geminidataanalytics.DataAgent(
        display_name=display_name,
        data_analytics_agent=data_analytics_agent,
    )
    request = geminidataanalytics.CreateDataAgentRequest(
        parent=self.project,
        data_agent_id=data_agent_id,
        data_agent=data_agent,
    )
    try:
      operation = self.agent_client.create_data_agent(request=request)
      created_agent = operation.result()
      return self._pb_to_agent_base(created_agent)
    except Exception as e:
      logging.error("An error occurred: %s", e)
      raise e

  def get_agent(self, agent_name: str) -> AgentBase | None:
    """Retrieves a single data agent by its full resource name."""
    request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
    try:
      agent = self.agent_client.get_data_agent(request=request)
      return self._pb_to_agent_base(agent)
    except Exception as e:
      logging.error("An error occurred: %s", e)
      raise e

  def delete_agent(self, agent_name: str):
    """Deletes a data agent by its full resource name."""
    request = geminidataanalytics.DeleteDataAgentRequest(name=agent_name)
    try:
      self.agent_client.delete_data_agent(request=request)
    except Exception as e:  # pylint: disable=broad-except
      logging.error("An error occurred: %s", e)

  def get_agent_context(
      self, agent_name: str, context_target: str
  ) -> dict[str, Any] | None:
    """Fetches the full agent definition and extracts context."""
    request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
    try:
      agent = self.agent_client.get_data_agent(request=request)
      da_agent = getattr(agent, "data_analytics_agent", None)
      if da_agent:
        context = None
        if context_target == "published":
          context = da_agent.published_context
        elif context_target == "staging":
          context = da_agent.staging_context

        if context:
          return json_format.MessageToDict(
              context._pb,
              preserving_proto_field_name=True,  # pylint: disable=protected-access
          )
      return None
    except Exception as e:  # pylint: disable=broad-except
      logging.error("An error occurred: %s", e)
      return None

  def update_agent(
      self,
      agent_name: str,
      system_instruction: str | None = None,
      config: AgentConfig | None = None,
  ) -> AgentBase | None:
    """Updates an existing data agent's system instruction or configuration."""
    if system_instruction is not None or config is not None:
      datasource_references = (
          self._get_datasource_references(config) if config else None
      )

      # If we are only updating system_instruction via the old way,
      # we still need to preserve datasource if possible.
      # But we now prefer passing the full config.

      # We need a field mask to only update what's changed.
      # However, GDA API often requires the full context to be replaced.
      # Let's check what's easier.

      request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
      try:
        existing_agent_proto = self.agent_client.get_data_agent(request=request)
      except Exception as e:
        logging.error("Failed to fetch agent for update: %s", e)
        raise e

      old_context = existing_agent_proto.data_analytics_agent.published_context

      # Merge changes
      final_instruction = (
          system_instruction
          if system_instruction is not None
          else (
              config.system_instruction
              if config
              else old_context.system_instruction
          )
      )
      final_datasource = (
          datasource_references
          if datasource_references is not None
          else old_context.datasource_references
      )

      new_context = geminidataanalytics.Context(
          system_instruction=final_instruction or "",
          datasource_references=final_datasource,
      )

      agent_update = geminidataanalytics.DataAgent(
          name=agent_name,
          data_analytics_agent=geminidataanalytics.DataAnalyticsAgent(
              published_context=new_context
          ),
      )

      update_mask = field_mask_pb2.FieldMask(
          paths=["data_analytics_agent.published_context"]
      )

      request = geminidataanalytics.UpdateDataAgentRequest(
          data_agent=agent_update,
          update_mask=update_mask,
      )

      try:
        operation = self.agent_client.update_data_agent(request=request)
        updated_agent = operation.result()
        return self._pb_to_agent_base(updated_agent)
      except Exception as e:
        logging.error("An error occurred during update: %s", e)
        raise e

    return self.get_agent(agent_name)

  def ask_question(
      self,
      agent_id: str,
      question: str,
      client_id: str | None = None,
      client_secret: str | None = None,
  ) -> AskQuestionResponse:
    """Runs a chat interaction and returns response and duration."""
    messages = [geminidataanalytics.Message(user_message={"text": question})]

    credentials_obj = None
    if client_id and client_secret:
      credentials_obj = geminidataanalytics.Credentials(
          oauth=geminidataanalytics.OAuthCredentials(
              secret=geminidataanalytics.OAuthCredentials.SecretBased(
                  client_id=client_id, client_secret=client_secret
              )
          )
      )

    data_agent_context = geminidataanalytics.DataAgentContext(
        data_agent=agent_id, credentials=credentials_obj
    )
    request = geminidataanalytics.ChatRequest(
        parent=self.project,
        messages=messages,
        data_agent_context=data_agent_context,
    )
    logging.debug("GeminiDataAnalyticsClient Request: %s", request)

    response_items = []
    error_message = None
    start_time = time.time()
    first_chunk_time = None

    try:
      stream = self.chat_client.chat(request=request, timeout=300)
      for response in stream:
        if first_chunk_time is None:
          first_chunk_time = time.time()

        response_items.append(
            json_format.MessageToDict(
                response._pb,  # pylint: disable=protected-access
                preserving_proto_field_name=True,
            )
        )

    except Exception as e:  # pylint: disable=broad-except
      logging.error(
          "GeminiDataAnalyticsClient caught SDK exception: %s", e, exc_info=True
      )
      error_message = f"SDK Request Failed: {str(e)}"

    finally:
      end_time = time.time()
      time_to_first = (
          int((first_chunk_time - start_time) * 1000)
          if first_chunk_time
          else None
      )
      if first_chunk_time is None:
        # If we trace an error without any chunks, set TTFR to total duration.
        # Reference implementation:
        # if first_chunk_time else int((end_time - start_time) * 1000)
        time_to_first = (
            int((first_chunk_time - start_time) * 1000)
            if first_chunk_time
            else int((end_time - start_time) * 1000)
        )

      total_duration = int((end_time - start_time) * 1000)
      duration = DurationMetrics(
          time_to_first_response=time_to_first,
          total_duration=total_duration,
      )
      logging.debug(
          "GeminiDataAnalyticsClient Final Response: %s", response_items
      )

    return AskQuestionResponse(
        response=response_items, duration=duration, error_message=error_message
    )
