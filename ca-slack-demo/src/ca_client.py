"""CA API client — standalone copy adapted from ca-eval.

Wraps google-cloud-geminidataanalytics for agent chat and management.
Uses the async gRPC client so progress callbacks fire while the stream is open.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from google.api_core import exceptions as gapi_exceptions
from google.cloud import geminidataanalytics_v1beta as gda
from google.protobuf import field_mask_pb2
import google.api_core.exceptions

original_format_http_response_error = google.api_core.exceptions.format_http_response_error

def patched_format_http_response_error(payload, *args, **kwargs):
    if isinstance(payload, list) and len(payload) > 0:
        payload = payload[0]
    return original_format_http_response_error(payload, *args, **kwargs)

google.api_core.exceptions.format_http_response_error = patched_format_http_response_error

log = logging.getLogger(__name__)


@dataclass
class CAResponse:
    """Structured response from a CA API chat call."""

    question: str
    conversation_id: Optional[str] = None   # reuse across turns in same thread
    generated_sql: Optional[str] = None
    text_answer: Optional[str] = None
    result_rows: Optional[list[dict]] = None
    result_scalar: Optional[Any] = None
    chart_spec: Optional[dict] = None
    latency_ms: int = 0
    error: Optional[str] = None
    planner_reasoning: Optional[str] = None
    resolved_tables: Optional[list[str]] = None


class CAClient:
    """Wraps the Gemini Data Analytics API for chat."""

    def __init__(
        self,
        project_id: str | None = None,
        location: str | None = None,
    ) -> None:
        self.project_id = project_id or os.environ["GCP_PROJECT_ID"]
        self.location = location or os.environ.get("GCP_LOCATION", "global")
        self._agent_client: gda.DataAgentServiceAsyncClient | None = None
        self._chat_client: gda.DataChatServiceAsyncClient | None = None
        self._chat_client_rest: gda.DataChatServiceAsyncClient | None = None
        # Cache: agent_id → conversation resource name
        self._conversations: dict[str, str] = {}

    def _get_chat_client(self) -> gda.DataChatServiceAsyncClient:
        if self._chat_client is None:
            self._chat_client = gda.DataChatServiceAsyncClient()
        return self._chat_client

    def _get_chat_client_rest(self) -> gda.DataChatServiceAsyncClient:
        if self._chat_client_rest is None:
            self._chat_client_rest = gda.DataChatServiceAsyncClient(transport="rest")
        return self._chat_client_rest

    async def _handle_chat_message(
        self,
        msg: gda.Message | dict,
        t0: float,
        raw_messages: list[gda.Message | dict],
        query_started: bool,
        on_progress: Optional[Callable[[str], Coroutine[Any, Any, None]]],
        on_query_start: Optional[Callable[[], Coroutine[Any, Any, None]]],
    ) -> bool:
        elapsed = time.monotonic() - t0
        log.info("Received message type: %s, content: %r", type(msg), msg)
        try:
            raw_messages.append(msg)
            
            if isinstance(msg, dict):
                sm = msg.get("systemMessage")
                if sm:
                    text = sm.get("text")
                    if on_progress and text and (text.get("textType") == "THOUGHT" or text.get("textType") == 2):
                        parts = text.get("parts", [])
                        if parts and len(parts) > 0:
                            label = parts[0]
                            if label:
                                log.info("CA progress [+%.1fs]: %s", elapsed, label)
                                await on_progress(":arrows_counterclockwise: %s" % label)
                    data = sm.get("data")
                    if on_query_start and not query_started and data and data.get("generatedSql"):
                        log.info("CA SQL generated [+%.1fs] — starting query ticker", elapsed)
                        if on_query_start:
                            await on_query_start()
                        return True
            else:
                sm = msg.system_message
                if sm:
                    if on_progress and sm.text and sm.text.text_type == 2:
                        parts = getattr(sm.text, "parts", [])
                        if parts and len(parts) > 0:
                            label = parts[0]
                            if label:
                                log.info("CA progress [+%.1fs]: %s", elapsed, label)
                                await on_progress(":arrows_counterclockwise: %s" % label)
                    if on_query_start and not query_started and sm.data and sm.data.generated_sql:
                        log.info("CA SQL generated [+%.1fs] — starting query ticker", elapsed)
                        if on_query_start:
                            await on_query_start()
                        return True
        except Exception as e:
            log.error("Error in _handle_chat_message: %s", e)
            
        return query_started

    def _agent_resource_name(self, agent_id: str) -> str:
        return (
            f"projects/{self.project_id}/locations/{self.location}"
            f"/dataAgents/{agent_id}"
        )

    def _get_chat_client(self) -> gda.DataChatServiceAsyncClient:
        if self._chat_client is None:
            self._chat_client = gda.DataChatServiceAsyncClient()
        return self._chat_client

    def _get_agent_client(self) -> gda.DataAgentServiceAsyncClient:
        if self._agent_client is None:
            self._agent_client = gda.DataAgentServiceAsyncClient()
        return self._agent_client

    def _build_datasource_references(self, context: dict, include_credentials: bool = True) -> gda.DatasourceReferences:
        datasource_refs = {}
        if "bq" in context:
            datasource_refs["bq"] = gda.BigQueryTableReferences(
                table_references=[
                    gda.BigQueryTableReference(
                        project_id=ref.get("projectId"),
                        dataset_id=ref.get("datasetId"),
                        table_id=ref.get("tableId"),
                    )
                    for ref in context["bq"]["tableReferences"]
                ]
            )
        elif "alloydb" in context:
            ref = context["alloydb"]["database_reference"]
            datasource_refs["alloydb"] = gda.AlloyDbReference(
                database_reference=gda.AlloyDbDatabaseReference(
                    project_id=ref.get("project_id"),
                    region=ref.get("region"),
                    cluster_id=ref.get("cluster_id"),
                    instance_id=ref.get("instance_id"),
                    database_id=ref.get("database_id"),
                    table_ids=ref.get("table_ids", [])
                )
            )
        elif "looker" in context:
            refs = context["looker"]["explore_references"]
            explore_refs = []
            for r in refs:
                explore_refs.append(gda.LookerExploreReference(
                    looker_instance_uri=r.get("looker_instance_uri"),
                    lookml_model=r.get("lookml_model"),
                    explore=r.get("explore")
                ))
            
            cred = None
            if "credentials" in context["looker"]:
                c = context["looker"]["credentials"]
                if "oauth" in c:
                    oauth = c["oauth"]
                    cred = gda.Credentials()
                    if "secret" in oauth:
                        cred.oauth.secret.client_id = oauth["secret"].get("client_id")
                        cred.oauth.secret.client_secret = oauth["secret"].get("client_secret")
                    elif "token" in oauth:
                        cred.oauth.token.access_token = oauth["token"].get("access_token")
            
            if include_credentials and cred:
                datasource_refs["looker"] = gda.LookerExploreReferences(
                    explore_references=explore_refs,
                    credentials=cred
                )
            else:
                datasource_refs["looker"] = gda.LookerExploreReferences(
                    explore_references=explore_refs
                )
            
        return gda.DatasourceReferences(**datasource_refs)

    async def create_agent(self, agent_id: str, context: dict) -> str:
        """Create a new DataAgent."""
        parent = f"projects/{self.project_id}/locations/{self.location}"
        agent = gda.DataAgent(
            display_name=agent_id,
            data_analytics_agent=gda.DataAnalyticsAgent(
                published_context=gda.Context(
                    datasource_references=self._build_datasource_references(context, include_credentials=False)
                )
            )
        )
        request = gda.CreateDataAgentRequest(
            parent=parent,
            data_agent=agent,
            data_agent_id=agent_id,
        )
        operation = await self._get_agent_client().create_data_agent(request=request)
        response = await operation.result()
        return response.name

    async def update_agent_published(self, agent_id: str, context: dict) -> str:
        """Update the published context of a DataAgent."""
        agent_name = self._agent_resource_name(agent_id)
        agent = gda.DataAgent(
            name=agent_name,
            data_analytics_agent=gda.DataAnalyticsAgent(
                published_context=gda.Context(
                    datasource_references=self._build_datasource_references(context, include_credentials=False)
                )
            )
        )
        request = gda.UpdateDataAgentRequest(
            data_agent=agent,
            update_mask=field_mask_pb2.FieldMask(paths=["data_analytics_agent.published_context"]),
        )
        operation = await self._get_agent_client().update_data_agent(request=request)
        response = await operation.result()
        return response.name

    async def create_conversation(self, agent_id: str) -> str:
        """Create a new stateful conversation. Returns resource name."""
        parent = f"projects/{self.project_id}/locations/{self.location}"
        agent_name = self._agent_resource_name(agent_id)
        request = gda.CreateConversationRequest(
            parent=parent,
            conversation=gda.Conversation(agents=[agent_name]),
        )
        response = await self._get_chat_client().create_conversation(request=request)
        return response.name

    async def chat(
        self,
        agent_id: str,
        question: str,
        conversation_id: Optional[str] = None,
        on_progress: Optional[Callable[..., Coroutine]] = None,
        on_query_start: Optional[Callable[[], Coroutine]] = None,
        context: Optional[dict] = None,
    ) -> CAResponse:
        """Send a chat message and return a structured CAResponse.

        on_progress is an async callable (coroutine function) invoked at each
        meaningful milestone. Because the gRPC stream is consumed asynchronously,
        await asyncio.sleep(0) after each event lets Slack edits actually fire
        rather than batching behind the tool call.
        """
        if conversation_id is None:
            conversation_id = await self.create_conversation(agent_id)

        agent_name = self._agent_resource_name(agent_id)
        
        cred = None
        if context and "looker" in context and "credentials" in context["looker"]:
            c = context["looker"]["credentials"]
            if "oauth" in c:
                oauth = c["oauth"]
                cred = gda.Credentials()
                if "secret" in oauth:
                    cred.oauth.secret.client_id = oauth["secret"].get("client_id")
                    cred.oauth.secret.client_secret = oauth["secret"].get("client_secret")
                elif "token" in oauth:
                    cred.oauth.token.access_token = oauth["token"].get("access_token")

        request = gda.ChatRequest(
            parent=f"projects/{self.project_id}/locations/{self.location}",
            conversation_reference=gda.ConversationReference(
                conversation=conversation_id,
                data_agent_context=gda.DataAgentContext(
                    data_agent=agent_name,
                    context_version=gda.DataAgentContext.ContextVersion.PUBLISHED,
                    credentials=cred,
                ),
            ),
            messages=[
                gda.Message(user_message=gda.UserMessage(text=question))
            ],
        )

        t0 = time.monotonic()
        raw_messages: list[gda.Message] = []
        error: Optional[str] = None
        timeout_s = float(os.environ.get("CA_CHAT_TIMEOUT_S", "90"))
        _query_started = False
        try:
            if agent_id == "cymbal_gadgets_looker":
                from google.auth import default
                from google.auth.transport.requests import Request
                from google.protobuf.json_format import ParseDict, MessageToDict
                import json
                import httpx
                
                credentials, _ = default()
                credentials.refresh(Request())
                headers = {"Authorization": f"Bearer {credentials.token}"}
                
                if not context or "looker" not in context:
                    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
                    context_path = os.path.join(base_dir, "context", "cymbal_gadgets_looker", "context.json")
                    if os.path.exists(context_path):
                        import json
                        with open(context_path, "r") as f:
                            context = json.load(f)
                            log.info("Loaded Looker context from file: %s", context_path)
                    else:
                        raise Exception(f"Looker context not provided and not found at {context_path}")
                
                url = f"https://geminidataanalytics.googleapis.com/v1beta/projects/{self.project_id}/locations/{self.location}:chat"
                
                oauth = context["looker"]["credentials"]["oauth"]
                secret = oauth["secret"]
                
                body = {
                    "parent": f"projects/{self.project_id}/locations/{self.location}",
                    "conversation_reference": {
                        "conversation": conversation_id,
                        "data_agent_context": {
                            "data_agent": agent_name,
                            "context_version": "PUBLISHED",
                            "credentials": {
                                "oauth": {
                                    "secret": {
                                        "client_id": secret.get("client_id"),
                                        "client_secret": secret.get("client_secret")
                                    }
                                }
                            }
                        }
                    },
                    "messages": [
                        {
                            "user_message": {
                                "text": question
                            }
                        }
                    ]
                }
                
                async with httpx.AsyncClient() as httpx_client:
                    async with httpx_client.stream("POST", url, json=body, headers=headers, timeout=timeout_s) as resp:
                        if resp.status_code >= 400:
                            error_text = await resp.aread()
                            raise Exception(f"Looker chat failed: {resp.status_code} - {error_text}")
                        
                        acc = ''
                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            decoded_line = line.strip()
                            if decoded_line == '[{':
                                acc = '{'
                            elif decoded_line == '}]':
                                acc += '}'
                            elif decoded_line == ',':
                                continue
                            else:
                                acc += decoded_line
                            
                            try:
                                data = json.loads(acc)
                                acc = '' # Reset if valid JSON
                                
                                if isinstance(data, list):
                                    for item in data:
                                        _query_started = await self._handle_chat_message(
                                            item, t0, raw_messages, _query_started, on_progress, on_query_start
                                        )
                                else:
                                    _query_started = await self._handle_chat_message(
                                        data, t0, raw_messages, _query_started, on_progress, on_query_start
                                    )
                                await asyncio.sleep(0)
                            except ValueError:
                                continue
                            except Exception as e:
                                log.warning("Failed to parse message: %s", e)
                                continue
            else:
                # Use gRPC for other agents
                async for msg in await self._get_chat_client().chat(request=request, timeout=timeout_s):
                    _query_started = await self._handle_chat_message(
                        msg, t0, raw_messages, _query_started, on_progress, on_query_start
                    )
                    await asyncio.sleep(0)
        except gapi_exceptions.DeadlineExceeded:
            error = "timeout"
            log.error("CA API timeout after %.0fs for %r", timeout_s, question)
        except gapi_exceptions.PermissionDenied as exc:
            error = "permission_denied"
            log.error("CA API permission denied for agent %r: %s", agent_id, exc)
        except gapi_exceptions.NotFound as exc:
            error = "not_found"
            log.error("CA API agent not found %r: %s", agent_id, exc)
        except gapi_exceptions.ResourceExhausted as exc:
            error = "quota_exceeded"
            log.error("CA API quota exceeded: %s", exc)
        except gapi_exceptions.ServiceUnavailable as exc:
            error = "unavailable"
            log.error("CA API unavailable: %s", exc)
        except Exception as exc:
            error = "unknown:%s" % exc
            log.error("CA API chat error for %r: %s", question, exc)

        parsed = self._parse_messages(raw_messages)
        latency_ms = int((time.monotonic() - t0) * 1000)

        return CAResponse(
            question=question,
            conversation_id=conversation_id,
            generated_sql=parsed["generated_sql"],
            text_answer=parsed["text_answer"],
            result_rows=parsed["result_rows"],
            result_scalar=parsed["result_scalar"],
            chart_spec=parsed["chart_spec"],
            latency_ms=latency_ms,
            error=error,
            planner_reasoning=parsed["planner_reasoning"],
            resolved_tables=parsed["resolved_tables"],
        )

    @staticmethod
    def _parse_messages(messages: list[gda.Message | dict]) -> dict:
        """Extract structured fields from response messages."""
        generated_sql: Optional[str] = None
        text_parts: list[str] = []
        result_rows: Optional[list[dict]] = None
        result_scalar: Optional[Any] = None
        chart_spec: Optional[dict] = None
        planner_reasoning: Optional[str] = None
        resolved_tables: list[str] = []

        for msg in messages:
            try:
                if isinstance(msg, dict):
                    sm = msg.get("systemMessage")
                    if not sm:
                        continue
        
                    text = sm.get("text")
                    if text and (text.get("textType") == "FINAL_RESPONSE" or text.get("textType") == 1):
                        parts = text.get("parts", [])
                        text_parts.extend(parts)
        
                    data = sm.get("data")
                    if data and isinstance(data, dict) and data.get("generatedSql"):
                        generated_sql = data.get("generatedSql")
                    elif data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                        first_item = data[0]
                        if "model" in first_item and "view" in first_item:
                            generated_sql = f"-- Looker Query\nModel: {first_item.get('model')}\nExplore: {first_item.get('view')}"
                            if "fields" in first_item:
                                generated_sql += f"\nFields: {', '.join(first_item['fields'])}"
                            if "filters" in first_item:
                                import json
                                generated_sql += f"\nFilters: {json.dumps(first_item['filters'])}"
                    elif data and isinstance(data, dict) and ("lookml_model" in data or "explore" in data or "model" in data):
                        model = data.get("lookml_model") or data.get("model")
                        explore = data.get("explore")
                        generated_sql = f"-- Looker Query\nModel: {model}\nExplore: {explore}"
                        if "dimensions" in data:
                            generated_sql += f"\nDimensions: {data['dimensions']}"
                        if "measures" in data:
                            generated_sql += f"\nMeasures: {data['measures']}"
        
                    if data and data.get("result"):
                        raw = data.get("result")
                        if isinstance(raw, list):
                            rows = raw
                        elif isinstance(raw, dict):
                            rows = raw.get("data", [])
                        else:
                            rows = []
                            
                        if rows:
                            result_rows = rows
                            if len(rows) == 1:
                                first_row = rows[0]
                                if isinstance(first_row, dict) and len(first_row) == 1:
                                    result_scalar = next(iter(first_row.values()))
                                    
                    chart = sm.get("chart")
                    if chart:
                        result = chart.get("result", {})
                        chart_spec = result.get("vegaConfig") or result.get("vega_config") or chart
                        
                    schema = sm.get("schema")
                    if schema and schema.get("result"):
                        datasources = schema.get("result").get("datasources", [])
                        for ds in datasources:
                            bq = ds.get("bigqueryTableReference")
                            if bq and bq.get("tableId"):
                                fqn = f"{bq.get('projectId')}.{bq.get('datasetId')}.{bq.get('tableId')}"
                                if fqn not in resolved_tables:
                                    resolved_tables.append(fqn)
                                    
                    analysis = sm.get("analysis")
                    if analysis and analysis.get("progressEvent"):
                        pe = analysis.get("progressEvent")
                        if pe.get("plannerReasoning"):
                            planner_reasoning = pe.get("plannerReasoning")
                else:
                    sm = msg.system_message
                    if not sm:
                        continue
        
                    if sm.text and (sm.text.text_type == 1 or sm.text.text_type == "FINAL_RESPONSE"):
                        text_parts.extend(sm.text.parts)
        
                    if sm.data and sm.data.generated_sql:
                        generated_sql = sm.data.generated_sql
                    elif sm.data:
                        try:
                            raw_data = type(sm.data).to_dict(sm.data)
                            if "lookml_model" in raw_data or "explore" in raw_data or "model" in raw_data:
                                model = raw_data.get("lookml_model") or raw_data.get("model")
                                explore = raw_data.get("explore")
                                generated_sql = f"-- Looker Query\nModel: {model}\nExplore: {explore}"
                                if "dimensions" in raw_data:
                                    generated_sql += f"\nDimensions: {raw_data['dimensions']}"
                                if "measures" in raw_data:
                                    generated_sql += f"\nMeasures: {raw_data['measures']}"
                        except Exception as e:
                            log.warning("Failed to parse sm.data as dict: %s", e)
        
                    if sm.data and sm.data.result:
                        raw = type(sm.data.result).to_dict(sm.data.result)
                        if isinstance(raw, list):
                            rows = raw
                        elif isinstance(raw, dict):
                            rows = raw.get("data", [])
                        else:
                            rows = []
                            
                        if rows:
                            result_rows = rows
                            if len(rows) == 1:
                                first_row = rows[0]
                                if isinstance(first_row, dict) and len(first_row) == 1:
                                    result_scalar = next(iter(first_row.values()))
        
                    if sm.chart:
                        raw_chart = type(sm.chart).to_dict(sm.chart)
                        result = raw_chart.get("result", {})
                        chart_spec = result.get("vegaConfig") or result.get("vega_config") or raw_chart
        
                    if sm.schema and sm.schema.result:
                        for ds in sm.schema.result.datasources:
                            bq = ds.bigquery_table_reference
                            if bq and bq.table_id:
                                fqn = f"{bq.project_id}.{bq.dataset_id}.{bq.table_id}"
                                if fqn not in resolved_tables:
                                    resolved_tables.append(fqn)
        
                    if sm.analysis and sm.analysis.progress_event:
                        pe = sm.analysis.progress_event
                        if pe.planner_reasoning:
                            planner_reasoning = pe.planner_reasoning
            except Exception as e:
                log.error("Failed to parse message %r: %s", msg, e)
                continue

        return {
            "generated_sql": generated_sql,
            "text_answer": "\n\n".join(text_parts) if text_parts else None,
            "result_rows": result_rows,
            "result_scalar": result_scalar,
            "chart_spec": chart_spec,
            "planner_reasoning": planner_reasoning,
            "resolved_tables": resolved_tables or None,
        }
