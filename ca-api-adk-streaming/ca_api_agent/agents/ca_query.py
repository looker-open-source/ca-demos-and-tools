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

"""Conversational Analytics query agent and CA API streaming bridge."""

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.api_core import exceptions as api_exceptions
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.genai import types
from google.protobuf import json_format
from typing_extensions import override

load_dotenv()
logger = logging.getLogger(__name__)

DATA_RESULT_STATE_KEY = "temp:data_result"
SUMMARY_STATE_KEY = "temp:summary_data"
DATA_MESSAGE_DISPLAY_MAX_ROWS = 5
DATA_TABLE_DISPLAY_MAX_ROWS = 50


def _message_to_dict(message: Any) -> dict[str, Any]:
    proto_message = getattr(message, "_pb", message)
    return json_format.MessageToDict(
        proto_message,
        preserving_proto_field_name=True,
    )


def _to_plain_rows(rows: list[Any]) -> list[dict[str, Any]]:
    plain_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            plain_rows.append(row)
            continue
        if hasattr(row, "items"):
            try:
                item_dict = dict(row.items())
                if item_dict:
                    plain_rows.append(item_dict)
                    continue
            except Exception:
                pass
        try:
            row_dict = _message_to_dict(row)
        except Exception:
            row_dict = {}
        if isinstance(row_dict, dict):
            if set(row_dict.keys()) == {"fields"} and isinstance(
                row_dict["fields"], dict
            ):
                row_dict = row_dict["fields"]
            if row_dict:
                plain_rows.append(row_dict)
                continue
        plain_rows.append({"value": str(row)})
    return plain_rows


def _truncate_data_message_for_display(data_message: dict[str, Any]) -> dict[str, Any]:
    result = data_message.get("result")
    if not isinstance(result, dict):
        return data_message

    display_data_message = dict(data_message)
    display_result = dict(result)
    trimmed_row_counts: dict[str, int] = {}

    for field_name in ("data", "formatted_data"):
        rows = result.get(field_name)
        if not isinstance(rows, list):
            continue
        if len(rows) <= DATA_MESSAGE_DISPLAY_MAX_ROWS:
            continue
        display_result[field_name] = rows[:DATA_MESSAGE_DISPLAY_MAX_ROWS]
        trimmed_row_counts[field_name] = len(rows) - DATA_MESSAGE_DISPLAY_MAX_ROWS

    if not trimmed_row_counts:
        return data_message

    display_result["display_trimmed_row_counts"] = trimmed_row_counts
    display_data_message["result"] = display_result
    return display_data_message


def _build_data_message_trim_notice(display_data_message: dict[str, Any]) -> str | None:
    result = display_data_message.get("result")
    if not isinstance(result, dict):
        return None

    trimmed_row_counts = result.get("display_trimmed_row_counts")
    if not isinstance(trimmed_row_counts, dict) or not trimmed_row_counts:
        return None

    trimmed_fields = ", ".join(
        f"{field}: {count} row(s) omitted"
        for field, count in trimmed_row_counts.items()
    )
    return (
        f"_DataMessage JSON was trimmed to {DATA_MESSAGE_DISPLAY_MAX_ROWS} rows per field "
        f"({trimmed_fields})._\n"
    )


def _format_code_block_json(payload: dict[str, Any]) -> str:
    return f"```json\n{json.dumps(payload, indent=2)}\n```\n"


def _stringify_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _format_simple_markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "_No rows returned._\n"

    headers: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in headers:
                headers.append(key)

    if not headers:
        return "_No tabular columns returned._\n"

    header_line = "| " + " | ".join(headers) + " |"
    separator_line = "| " + " | ".join(["---"] * len(headers)) + " |"

    body_lines: list[str] = []
    for row in rows:
        cells = [
            _escape_markdown_cell(_stringify_cell(row.get(header)))
            for header in headers
        ]
        body_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join([header_line, separator_line, *body_lines]) + "\n"



def _clear_response_shape_state(ctx: InvocationContext) -> None:
    """Clears routing-related state to avoid stale data across turns."""
    keys_to_clear = (
        DATA_RESULT_STATE_KEY,
        SUMMARY_STATE_KEY,
    )
    for key in keys_to_clear:
        ctx.session.state.pop(key, None)


def _build_inline_context() -> geminidataanalytics.Context:
    return geminidataanalytics.Context(
        system_instruction=(
            "Answer user questions to the best of your ability. "
            "Do not return charts."
        ),
        datasource_references=geminidataanalytics.DatasourceReferences(
            looker=geminidataanalytics.LookerExploreReferences(
                explore_references=[
                    geminidataanalytics.LookerExploreReference(
                        looker_instance_uri=os.getenv("LOOKERSDK_BASE_URL"),
                        lookml_model=os.getenv("LOOKML_MODEL"),
                        explore=os.getenv("LOOKML_EXPLORE"),
                    )
                ],
                credentials=geminidataanalytics.Credentials(
                    oauth=geminidataanalytics.OAuthCredentials(
                        secret=geminidataanalytics.OAuthCredentials.SecretBased(
                            client_id=os.getenv("LOOKERSDK_CLIENT_ID"),
                            client_secret=os.getenv("LOOKERSDK_CLIENT_SECRET"),
                        )
                    )
                ),
            )
        ),
    )


async def stream_nlq(question: str, ctx: InvocationContext) -> AsyncGenerator[str, None]:
    """Streams CA API responses and persists structured result data to session state."""
    logger.info({"request": question})
    _clear_response_shape_state(ctx)

    project = (
        f"projects/{os.getenv('GOOGLE_CLOUD_PROJECT')}"
        f"/locations/{os.getenv('GOOGLE_CLOUD_LOCATION')}"
    )

    user_message = geminidataanalytics.Message(
        user_message=geminidataanalytics.UserMessage(text=question)
    )
    request_messages = [user_message]

    chat_request = geminidataanalytics.ChatRequest(
        parent=project,
        messages=request_messages,
        inline_context=_build_inline_context(),
    )

    try:
        client = geminidataanalytics.DataChatServiceAsyncClient()
        stream = await client.chat(request=chat_request)

        async for response in stream:
            if not response.system_message:
                continue

            system_message = response.system_message
            if system_message.data:
                data_node = system_message.data
                data_message = _message_to_dict(data_node)
                display_data_message = _truncate_data_message_for_display(data_message)
                yield _format_code_block_json(display_data_message)
                trim_notice = _build_data_message_trim_notice(display_data_message)
                if trim_notice:
                    yield trim_notice
                await asyncio.sleep(0)

                query_payload = data_message.get("query")
                result_payload = data_message.get("result")
                query_question = (
                    query_payload.get("question")
                    if isinstance(query_payload, dict)
                    else None
                )

                if isinstance(query_question, str) and query_question:
                    yield f"Analyzing your question: {query_question}\n"
                    await asyncio.sleep(0)
                elif isinstance(result_payload, dict):
                    payload_rows = result_payload.get("data")
                    plain_rows = (
                        _to_plain_rows(payload_rows)
                        if isinstance(payload_rows, list)
                        else []
                    )
                    if not plain_rows:
                        result = getattr(data_node, "result", None)
                        raw_rows = list(result.data) if result and result.data else []
                        plain_rows = _to_plain_rows(raw_rows)
                    ctx.session.state[DATA_RESULT_STATE_KEY] = plain_rows
                    yield f"The query returned {len(plain_rows)} row(s)\n"
                    yield _format_simple_markdown_table(
                        plain_rows[:DATA_TABLE_DISPLAY_MAX_ROWS]
                    )
                    if len(plain_rows) > DATA_TABLE_DISPLAY_MAX_ROWS:
                        yield (
                            f"_Showing first {DATA_TABLE_DISPLAY_MAX_ROWS} rows out of "
                            f"{len(plain_rows)}._\n"
                        )
                    await asyncio.sleep(0)

            # chart rendering is handled by visualization sub-agent
            if system_message.chart:
                await asyncio.sleep(0)

            if system_message.text and system_message.text.parts:
                summary_part = system_message.text.parts[0]
                summary_text = getattr(summary_part, "text", None) or ""
                if summary_text:
                    ctx.session.state[SUMMARY_STATE_KEY] = summary_text
                    yield summary_text + "\n"
                    await asyncio.sleep(0)
    except api_exceptions.GoogleAPICallError as err:
        code_fn = getattr(err, "code", None)
        code = code_fn() if callable(code_fn) else None
        error_code = str(getattr(code, "name", "UNKNOWN"))
        error_message = str(getattr(err, "message", str(err)))
        logger.error("Error from CA API: %s - %s", error_code, error_message)
        yield json.dumps({"error": error_message, "code": error_code})
    except Exception as err:  # pragma: no cover - defensive catch for service errors
        logger.exception("Unexpected error from CA API")
        yield json.dumps({"error": str(err)})


def _extract_user_question(ctx: InvocationContext) -> str | None:
    """Extracts plain-text question from the invocation's user content."""
    user_content = ctx.user_content
    if not user_content or not user_content.parts:
        return None

    text_parts: list[str] = []
    for part in user_content.parts:
        text = getattr(part, "text", None)
        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())

    if not text_parts:
        return None
    return "\n".join(text_parts)


class ConversationalAnalyticsQueryAgent(BaseAgent):
    """Runs NLQ requests against CA API and streams results back into the chat."""

    name: str
    description: str = ""

    def __init__(
        self,
        name: str,
        description: str = "",
    ) -> None:
        init_data: dict[str, Any] = {
            "name": name,
            "description": description,
        }
        super().__init__(**init_data)

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        question = _extract_user_question(ctx)
        if not question:
            error_content = types.Content(
                role="model",
                parts=[
                    types.Part(
                        text=(
                            "I couldn't read your question. "
                            "Please send a text prompt."
                        )
                    )
                ],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=True,
                invocation_id=ctx.invocation_id,
                content=error_content,
            )
            return

        status_message = types.Content(
            role="model",
            parts=[types.Part(text="Invoking the Conversational Analytics API...")],
        )
        yield Event(
            author=self.name,
            partial=False,
            turn_complete=False,
            invocation_id=ctx.invocation_id,
            content=status_message,
        )

        async for data_chunk in stream_nlq(question, ctx):
            chunk_content = types.Content(
                role="model",
                parts=[types.Part(text=data_chunk)],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=False,
                invocation_id=ctx.invocation_id,
                content=chunk_content,
            )

        yield Event(
            author=self.name,
            partial=False,
            turn_complete=True,
            invocation_id=ctx.invocation_id,
        )


def build_conversational_analytics_query_agent(
    name: str = "conversational_analytics_query_agent",
) -> ConversationalAnalyticsQueryAgent:
    """Factory for the CA query sub-agent."""
    return ConversationalAnalyticsQueryAgent(
        name=name,
        description="Always forwards each user request directly to the Conversational Analytics API.",
    )
