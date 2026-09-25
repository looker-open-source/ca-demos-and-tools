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

import logging
import re
import threading
import time
from typing import Any

from google.api_core import client_options
from google.api_core import exceptions as api_exceptions
import google.auth
from google.auth import exceptions as auth_exceptions
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.protobuf import field_mask_pb2
from google.protobuf import json_format
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.agent import LookerFilter
from prism.common.schemas.agent import LookerGoldenQuery
from prism.common.schemas.agent import LookerQuery
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.clients import recording

logger = logging.getLogger(__name__)


def get_gda_endpoint(location: str | None) -> str | None:
  """Returns the GDA API endpoint for a given location, or None for global."""
  if not location:
    return None
  loc = location.strip().lower()
  if not loc or loc == "global":
    return None
  # One form for every non-global location, multi-region and region alike. The
  # locations documentation gives geminidataanalytics.us.rep.googleapis.com and
  # lists us-east4 alongside us and eu, so regions take the same shape. The
  # earlier geminidataanalytics-<region>.googleapis.com form this replaces is
  # the Vertex convention, not this service's.
  return f"geminidataanalytics.{loc}.rep.googleapis.com"


# What the service returns when a Looker agent is asked a question without
# credentials. It names the request field, not the agent that needs editing.
_MISSING_LOOKER_CREDENTIALS = (
    "looker.credentials.kind: invalid value: KIND_NOT_SET"
)

# How long to wait on the create-agent operation. Without one, a stuck
# operation hangs the request thread that started it for as long as the
# process lives.
_CREATE_AGENT_TIMEOUT_S = 300

# The same, for the update-agent operation.
_UPDATE_AGENT_TIMEOUT_S = 300

# How long one chat stream may take. A run gives each trial this long before
# the request thread is released.
_ASK_QUESTION_TIMEOUT_S = 300


def _readable_api_error(e: Exception) -> str:
  """The status and message of an API error, without the server's detail blob.

  str() on one of these appends the service's internal detail, which runs to
  several hundred characters of Java class names around the one sentence that
  says what went wrong. A bad Looker credential is the common case, and the
  trial row showed the blob, not "Login failed".

  Anything that is not an API error was raised inside the client stack rather
  than by the service, and str() on those is where the credentials are. An
  auth refresh failure prints the service account email and a channel error
  prints the endpoint. The result of this goes on the trial row and onto the
  run detail page, so those get the type name and nothing else.
  """
  if isinstance(e, api_exceptions.GoogleAPICallError):
    if _MISSING_LOOKER_CREDENTIALS in e.message:
      # _validate_agent_can_run catches most of these before the run. This is
      # what is left when the datasource read it makes fails.
      return (
          f"{e.code} This agent needs Looker credentials. Edit the agent to add"
          " a Looker client ID and secret."
      )
    return f"{e.code} {e.message}"
  return f"{type(e).__name__} raised inside the Data Analytics client."


class GeminiDataAnalyticsClient:
  """A client for interacting with the Google Gemini Data Analytics API."""

  # Class-level defaults, so the properties below still answer on an instance
  # whose __init__ was skipped. The UI dispatch tests build one that way to get
  # a client with no transport.
  _chat = None
  _agent = None
  _by_location: dict[tuple[str, str], Any] | None = None

  # Guards _by_location. Dash is served by gunicorn with --threads 8, so two
  # request threads can miss the same key at once, and the second transport
  # then overwrote the first in the dict with nothing left holding it open.
  # That is the leak the cache was added to stop. Class level, because the
  # attributes above are too: a client whose __init__ was skipped still gets
  # here.
  _cache_lock = threading.Lock()

  def __init__(self, project: str):
    """Initializes the GeminiDataAnalyticsClient.

    Transports are opened on first use, not here, and the caller is expected
    to close them. Both channels used to be opened in the constructor, so a
    client that only listed agents still opened a chat channel it never spoke
    on. discover_gcp_agents builds one client per configured location on every
    Discover click and closed none of them, so the channels and their thread
    pools and sockets piled up in the long-lived gunicorn worker until Cloud
    Run killed the container. Use close(), or the client as a context manager.

    Args:
      project: The project and location, e.g.,
        'projects/my-project/locations/us-central1'.
    """
    self.project = project
    # Above the offline return, because a replaying client still gets asked for
    # its location.
    self.location = self._extract_location(project)

    if recording.offline():
      # Replaying cassettes. Every method short-circuits before it touches a
      # transport, so building credentialed clients would only fail.
      return

    try:
      _, project_id = google.auth.default()
      logger.debug(
          "[Auth] Successfully found credentials. Authenticated project: %s",
          project_id,
      )
    except auth_exceptions.DefaultCredentialsError as e:
      logger.error("[Auth] Failed to find default credentials: %s", e)

  @property
  def chat_client(self) -> geminidataanalytics.DataChatServiceClient | None:
    """The chat transport for self.location, opened on first read."""
    if self._chat is None and not recording.offline():
      self._chat = self._create_chat_client(self.location)
    return self._chat

  @chat_client.setter
  def chat_client(self, value: Any) -> None:
    self._chat = value

  @property
  def agent_client(self) -> geminidataanalytics.DataAgentServiceClient | None:
    """The agent transport for self.location, opened on first read."""
    if self._agent is None and not recording.offline():
      self._agent = self._create_agent_client(self.location)
    return self._agent

  @agent_client.setter
  def agent_client(self, value: Any) -> None:
    self._agent = value

  def close(self) -> None:
    """Closes every transport this client opened.

    Nothing released them before. A client is cheap to rebuild and a channel
    is not, and reading a property after this opens a fresh one, so calling
    this twice or calling it early is safe.
    """
    with self._cache_lock:
      transports = [self._chat, self._agent]
      transports.extend((self._by_location or {}).values())
      self._chat = None
      self._agent = None
      self._by_location = None

    for transport in transports:
      if transport is None:
        continue
      try:
        transport.close()
      except Exception:  # pylint: disable=broad-exception-caught
        # One transport refusing to close should not keep the rest open.
        logger.warning("Failed to close a GDA transport", exc_info=True)

  def __enter__(self) -> "GeminiDataAnalyticsClient":
    return self

  def __exit__(self, exc_type, exc_value, traceback) -> None:
    del exc_type, exc_value, traceback
    self.close()

  def _transport_for_location(self, kind: str, location: str) -> Any:
    """Returns the cached transport of kind for a location, opening it once.

    Only for resources outside self.location. These were built fresh on every
    call and dropped, which left a channel behind each time.
    """
    with self._cache_lock:
      if self._by_location is None:
        self._by_location = {}

      key = (kind, location)
      if key not in self._by_location:
        self._by_location[key] = (
            self._create_chat_client(location)
            if kind == "chat"
            else self._create_agent_client(location)
        )
      return self._by_location[key]

  @classmethod
  def _extract_location(cls, resource_path: str | None) -> str:
    """Extracts location string from a GCP resource path or returns 'global'."""
    if not resource_path:
      return "global"
    match = re.search(r"/locations/([^/]+)", resource_path)
    if match:
      return match.group(1).strip().lower()
    return "global"

  @classmethod
  def _create_chat_client(
      cls, location: str | None
  ) -> geminidataanalytics.DataChatServiceClient:
    endpoint = get_gda_endpoint(location)
    options = (
        client_options.ClientOptions(api_endpoint=endpoint)
        if endpoint
        else None
    )
    return geminidataanalytics.DataChatServiceClient(client_options=options)

  @classmethod
  def _create_agent_client(
      cls, location: str | None
  ) -> geminidataanalytics.DataAgentServiceClient:
    endpoint = get_gda_endpoint(location)
    options = (
        client_options.ClientOptions(api_endpoint=endpoint)
        if endpoint
        else None
    )
    return geminidataanalytics.DataAgentServiceClient(client_options=options)

  def _get_agent_client_for_resource(
      self, resource_name: str | None
  ) -> geminidataanalytics.DataAgentServiceClient:
    loc = (
        self._extract_location(resource_name)
        if resource_name
        else self.location
    )
    if loc == self.location:
      return self.agent_client
    return self._transport_for_location("agent", loc)

  def _get_chat_client_for_resource(
      self, resource_name: str | None
  ) -> geminidataanalytics.DataChatServiceClient:
    loc = (
        self._extract_location(resource_name)
        if resource_name
        else self.location
    )
    if loc == self.location:
      return self.chat_client
    return self._transport_for_location("chat", loc)

  def _cassette_identity(self) -> dict[str, Any]:
    """Fields identifying this client in a cassette key."""
    return {"project": self.project}

  def _pb_to_agent_base(self, agent_pb: Any) -> AgentBase | None:
    """Converts a DataAgent protobuf to an AgentBase schema."""
    if not agent_pb:
      return None

    # Parse resource name: projects/{p}/locations/{l}/dataAgents/{r}
    match = re.match(
        r"projects/([^/]+)/locations/([^/]+)/dataAgents/([^/]+)", agent_pb.name
    )
    if not match:
      logger.warning("Failed to parse agent resource name: %s", agent_pb.name)
      return None

    project_id, location, agent_resource_id = match.groups()

    datasource = None
    system_instruction = None
    context = None

    # Only published_context. A staging context is not what a run should see.
    da_agent = getattr(agent_pb, "data_analytics_agent", None)
    if da_agent:
      context = getattr(da_agent, "published_context", None)
      if context:
        system_instruction = context.system_instruction
        refs = getattr(context, "datasource_references", None)
        if refs:
          if refs.bq and refs.bq.table_references:
            tables = []
            for t in refs.bq.table_references:
              tables.append(f"{t.project_id}.{t.dataset_id}.{t.table_id}")
            datasource = BigQueryConfig(tables=tables)
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

    golden_queries = []
    if context:
      proto_gqs = getattr(context, "looker_golden_queries", [])
      golden_queries = self._pb_to_looker_golden_queries(list(proto_gqs))

    config = AgentConfig(
        project_id=project_id,
        location=location,
        agent_resource_id=agent_resource_id,
        datasource=datasource,
        system_instruction=system_instruction,
        golden_queries=golden_queries if golden_queries else None,
    )

    return AgentBase(name=agent_pb.display_name, config=config)

  @recording.cassette(recording.ModelListCodec(AgentBase))
  def list_agents(self) -> list[AgentBase]:
    """Lists all data agents for the configured project.

    Raises whatever the API raises. A denied project and an empty one are
    different answers, and swallowing the first returned the second.

    Returns:
      A list of AgentBase objects.
    """
    request = geminidataanalytics.ListDataAgentsRequest(
        parent=self.project,
    )
    agents = []
    pager = self.agent_client.list_data_agents(request=request)
    for agent in pager:
      # Per agent, because one the converter cannot read used to abandon the
      # page. A project with 58 agents listed 7, and nothing said so.
      try:
        agent_obj = self._pb_to_agent_base(agent)
      except Exception as e:  # pylint: disable=broad-except
        logger.warning("Skipping agent %s: %s", agent.name, e)
        continue
      if agent_obj:
        agents.append(agent_obj)
    return agents

  def _get_datasource_references(
      self, config: AgentConfig
  ) -> geminidataanalytics.DatasourceReferences | None:
    """Converts AgentConfig.datasource to DatasourceReferences."""
    if isinstance(config.datasource, BigQueryConfig):
      table_refs = []
      for table_str in config.datasource.tables:
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
        # Checked the way the BigQuery branch above checks its tables.
        # Unpacking a malformed string raised a bare unpacking error.
        parts = explore_str.split(".")
        if len(parts) != 2:
          raise ValueError(
              f"Invalid Looker explore format: '{explore_str}'. "
              "Expected 'model.explore'."
          )
        model, explore = parts
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

  def _get_looker_golden_queries(
      self, app_golden_queries: list[LookerGoldenQuery] | None
  ) -> list[geminidataanalytics.LookerGoldenQuery]:
    """Converts app schema Golden Queries to Proto Golden Queries."""
    if not app_golden_queries:
      return []

    proto_golden_queries = []
    for gq in app_golden_queries:
      lq = gq.looker_query
      filters = []
      if lq.filters:
        for f in lq.filters:
          filters.append(
              geminidataanalytics.LookerQuery.Filter(
                  field=f.field, value=f.value or ""
              )
          )

      proto_lq = geminidataanalytics.LookerQuery(
          model=lq.model or "",
          explore=lq.explore or "",
          fields=lq.fields or [],
          filters=filters,
          sorts=lq.sorts or [],
          limit=lq.limit or "",
      )

      proto_golden_queries.append(
          geminidataanalytics.LookerGoldenQuery(
              natural_language_questions=gq.natural_language_questions,
              looker_query=proto_lq,
          )
      )
    return proto_golden_queries

  def _pb_to_looker_golden_queries(
      self, proto_golden_queries: list[Any]
  ) -> list[LookerGoldenQuery]:
    """Converts Proto Golden Queries to app schema Golden Queries."""
    if not proto_golden_queries:
      return []

    app_golden_queries = []
    for pgq in proto_golden_queries:
      plq = getattr(pgq, "looker_query", None)
      if plq:
        filters = []
        p_filters = getattr(plq, "filters", [])
        for pf in p_filters:
          filters.append(
              LookerFilter(
                  field=getattr(pf, "field", ""), value=getattr(pf, "value", "")
              )
          )

        lq = LookerQuery(
            model=getattr(plq, "model", None),
            explore=getattr(plq, "explore", None),
            fields=list(getattr(plq, "fields", [])),
            filters=filters,
            sorts=list(getattr(plq, "sorts", [])),
            limit=getattr(plq, "limit", None),
        )
        app_golden_queries.append(
            LookerGoldenQuery(
                natural_language_questions=list(
                    getattr(pgq, "natural_language_questions", [])
                ),
                looker_query=lq,
            )
        )
    return app_golden_queries

  @recording.cassette(recording.ModelCodec(AgentBase))
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
    looker_golden_queries = self._get_looker_golden_queries(
        config.golden_queries
    )

    context = geminidataanalytics.Context(
        system_instruction=config.system_instruction or "",
        datasource_references=datasource_references,
        looker_golden_queries=looker_golden_queries,
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
      created_agent = operation.result(timeout=_CREATE_AGENT_TIMEOUT_S)
      return self._pb_to_agent_base(created_agent)
    except Exception as e:
      logger.error("An error occurred: %s", e)
      raise e

  @recording.cassette(recording.ModelCodec(AgentBase))
  def get_agent(self, agent_name: str) -> AgentBase | None:
    """Retrieves a single data agent by its full resource name."""
    agent_client = self._get_agent_client_for_resource(agent_name)
    request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
    try:
      agent = agent_client.get_data_agent(request=request)
      return self._pb_to_agent_base(agent)
    except Exception as e:
      logger.error("An error occurred: %s", e)
      raise e

  @recording.cassette()
  def get_agent_context(
      self, agent_name: str, context_target: str
  ) -> dict[str, Any] | None:
    """Fetches the full agent definition and extracts context."""
    agent_client = self._get_agent_client_for_resource(agent_name)
    request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
    try:
      agent = agent_client.get_data_agent(request=request)
      da_agent = getattr(agent, "data_analytics_agent", None)
      if da_agent:
        context = None
        if context_target == "published":
          context = da_agent.published_context
        elif context_target == "staging":
          context = da_agent.staging_context

        if context:
          context = self._without_looker_credentials(context)
          return json_format.MessageToDict(
              context._pb,  # pylint: disable=protected-access
              preserving_proto_field_name=True,
          )
      return None
    except Exception as e:  # pylint: disable=broad-except
      logger.error("An error occurred: %s", e)
      return None

  @recording.cassette()
  def get_datasource_kind(self, agent_name: str) -> str | None:
    """The datasource kind the service resolves for this agent.

    Reads the published context first, then the staging one. An agent that was
    saved and never published still answers questions, so an empty published
    context does not mean the agent cannot run.

    Returns the name of the reference field that is set, "looker" or "bq" or
    one of the kinds prism does not parse. Returns None when neither context
    names a datasource. The get call is unguarded so the caller can tell a
    failed read from an agent with no datasource.
    """
    agent_client = self._get_agent_client_for_resource(agent_name)
    request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
    da_agent = agent_client.get_data_agent(request=request).data_analytics_agent

    for context in (da_agent.published_context, da_agent.staging_context):
      context_pb = context._pb  # pylint: disable=protected-access
      # WhichOneof, so a kind prism does not parse still counts as one.
      kind = context_pb.datasource_references.WhichOneof("references")
      if kind:
        return kind
    return None

  def _without_looker_credentials(
      self, context: geminidataanalytics.Context
  ) -> geminidataanalytics.Context:
    """Drops the OAuth credentials a Looker agent's context is published with.

    Every run stores this context on its row. From there it is rendered on the
    run page, diffed on the comparison page and exported to BigQuery, so the
    client secret cannot be in it. Returns the context unchanged when there is
    nothing to drop, which keeps the copy off the BigQuery path.
    """
    # Read presence off the raw message. Reaching through the proto-plus
    # wrapper to delete the field creates the parents it passes on the way.
    refs = context._pb.datasource_references  # pylint: disable=protected-access
    if not refs.looker.HasField("credentials"):
      return context

    redacted = geminidataanalytics.Context(context)
    del redacted.datasource_references.looker.credentials
    return redacted

  def _with_old_looker_credentials(
      self,
      new_references: geminidataanalytics.DatasourceReferences,
      old_references: geminidataanalytics.DatasourceReferences,
  ) -> geminidataanalytics.DatasourceReferences:
    """Carries the agent's stored Looker credentials onto new references.

    _get_datasource_references builds the Looker references from the explores
    alone. AgentConfig has nowhere to put the OAuth credentials, and
    get_agent_context strips them on the way out, so prism never holds them.
    The update below replaces the whole published context, so editing only the
    system instruction wiped the credentials off the agent and every question
    after that failed with KIND_NOT_SET.
    """
    new_pb = new_references._pb  # pylint: disable=protected-access
    old_pb = old_references._pb  # pylint: disable=protected-access
    if new_pb.WhichOneof("references") != "looker":
      return new_references
    # An edit that carries its own credentials means them, so it wins.
    if new_pb.looker.HasField("credentials"):
      return new_references
    if not old_pb.looker.HasField("credentials"):
      return new_references

    merged = geminidataanalytics.DatasourceReferences(new_references)
    merged._pb.looker.credentials.CopyFrom(  # pylint: disable=protected-access
        old_pb.looker.credentials
    )
    return merged

  @recording.cassette(recording.ModelCodec(AgentBase))
  def update_agent(
      self,
      agent_name: str,
      system_instruction: str | None = None,
      config: AgentConfig | None = None,
  ) -> AgentBase | None:
    """Updates an existing data agent's system instruction or configuration."""
    agent_client = self._get_agent_client_for_resource(agent_name)
    if system_instruction is not None or config is not None:
      datasource_references = (
          self._get_datasource_references(config) if config else None
      )

      # The update replaces the whole published context, so start from the
      # old one and merge the changes into it.

      request = geminidataanalytics.GetDataAgentRequest(name=agent_name)
      try:
        existing_agent_proto = agent_client.get_data_agent(request=request)
      except Exception as e:
        logger.error("Failed to fetch agent for update: %s", e)
        raise e

      old_context = existing_agent_proto.data_analytics_agent.published_context

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
      if datasource_references is not None:
        final_datasource = self._with_old_looker_credentials(
            final_datasource, old_context.datasource_references
        )

      new_golden_queries = None
      if config and config.golden_queries is not None:
        new_golden_queries = self._get_looker_golden_queries(
            config.golden_queries
        )

      final_golden_queries = (
          new_golden_queries
          if new_golden_queries is not None
          else getattr(old_context, "looker_golden_queries", [])
      )

      new_context = geminidataanalytics.Context(
          system_instruction=final_instruction or "",
          datasource_references=final_datasource,
          looker_golden_queries=final_golden_queries,
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
        operation = agent_client.update_data_agent(request=request)
        try:
          updated_agent = operation.result(timeout=_UPDATE_AGENT_TIMEOUT_S)
        except Exception as e:
          logger.error(
              "Failed to get result from agent update operation: %s", e
          )
          # A timeout on the operation is not proof the write missed, so the
          # agent is read back. The agent always exists, so the read on its
          # own says nothing: what counts is the context that comes back. It
          # used to be returned whatever it held, so a rejected edit reported
          # as saved and the local row was then written with an instruction
          # the live agent did not have. Credentials are dropped from both
          # sides: the context sent carries the Looker secret merged in from
          # the old one, and the service does not have to give it back.
          try:
            refetched = agent_client.get_data_agent(
                request=geminidataanalytics.GetDataAgentRequest(name=agent_name)
            )
          except Exception as fetch_error:
            logger.error("Read back after the failed update: %s", fetch_error)
            raise e from fetch_error

          live_context = refetched.data_analytics_agent.published_context
          if self._without_looker_credentials(
              live_context
          ) != self._without_looker_credentials(new_context):
            logger.error("The agent did not take the update. Reporting it.")
            raise e
          updated_agent = refetched

        return self._pb_to_agent_base(updated_agent)
      except Exception as e:
        logger.error("An error occurred during update: %s", e)
        raise e

    return self.get_agent(agent_name)

  @recording.cassette(
      recording.ModelCodec(AskQuestionResponse),
      ignore=("client_id", "client_secret"),
  )
  def ask_question(
      self,
      agent_id: str,
      question: str,
      client_id: str | None = None,
      client_secret: str | None = None,
  ) -> AskQuestionResponse:
    """Runs a chat interaction and returns response and duration."""
    req_parent = self.project
    chat_client = self.chat_client
    if agent_id:
      match = re.match(
          r"(projects/[^/]+/locations/[^/]+)/dataAgents/[^/]+", agent_id
      )
      if match:
        req_parent = match.group(1)
        chat_client = self._get_chat_client_for_resource(agent_id)

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
        parent=req_parent,
        messages=messages,
        data_agent_context=data_agent_context,
    )
    # Logging the request logs the Looker client secret with it, and the agent
    # and the question are the two things worth having here anyway.
    logger.debug("GeminiDataAnalyticsClient asking %s: %s", agent_id, question)

    response_items = []
    error_message = None
    start_time = time.time()
    first_chunk_time = None

    try:
      stream = chat_client.chat(
          request=request, timeout=_ASK_QUESTION_TIMEOUT_S
      )

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
      logger.error(
          "GeminiDataAnalyticsClient caught SDK exception: %s", e, exc_info=True
      )
      error_message = f"SDK Request Failed: {_readable_api_error(e)}"

    finally:
      end_time = time.time()
      time_to_first = (
          int((first_chunk_time - start_time) * 1000)
          if first_chunk_time
          else None
      )
      if first_chunk_time is None:
        # An error with no chunks. Charge the whole run to the first response.
        time_to_first = int((end_time - start_time) * 1000)

      total_duration = int((end_time - start_time) * 1000)
      duration = DurationMetrics(
          time_to_first_response=time_to_first,
          total_duration=total_duration,
      )
      # The count, not the bodies. Same reason the request is not logged
      # above: the reply carries the rows the query returned.
      logger.debug(
          "GeminiDataAnalyticsClient got %d response items from %s",
          len(response_items),
          agent_id,
      )

    return AskQuestionResponse(
        response=response_items, duration=duration, error_message=error_message
    )
