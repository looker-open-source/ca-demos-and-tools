"""Conversational Analytics query agent and CA API streaming bridge."""

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.api_core import exceptions as api_exceptions
from google.cloud import geminidataanalytics_v1beta as geminidataanalytics
from google.genai import types
from google.genai.types import ThinkingConfig
from google.protobuf import json_format
from typing_extensions import override

load_dotenv()
logger = logging.getLogger(__name__)

DATA_RESULT_STATE_KEY = "temp:data_result"
SUMMARY_STATE_KEY = "temp:summary_data"
CHART_RESULT_VEGA_CONFIG_STATE_KEY = "temp:chart_result_vega_config"
CHART_RESULT_IMAGE_MIME_TYPE_STATE_KEY = "temp:chart_result_image_mime_type"
CHART_RESULT_IMAGE_PRESENT_STATE_KEY = "temp:chart_result_image_present"
DATA_MESSAGE_DISPLAY_MAX_ROWS = 5
DATA_TABLE_DISPLAY_MAX_ROWS = 50


async def tool_intercept(question: str) -> None:
    """Intercept tool used to trigger CA streaming execution."""
    del question
    return


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
        CHART_RESULT_VEGA_CONFIG_STATE_KEY,
        CHART_RESULT_IMAGE_MIME_TYPE_STATE_KEY,
        CHART_RESULT_IMAGE_PRESENT_STATE_KEY,
    )
    for key in keys_to_clear:
        ctx.session.state.pop(key, None)


def _build_inline_context() -> geminidataanalytics.Context:
    return geminidataanalytics.Context(
        system_instruction=(
            "Answer user questions to the best of your ability. "
            "Do not return charts or visualization output."
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

    chat_request = geminidataanalytics.ChatRequest(
        parent=project,
        messages=[
            geminidataanalytics.Message(
                user_message=geminidataanalytics.UserMessage(text=question)
            )
        ],
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

            if system_message.chart:
                chart_node = system_message.chart
                try:
                    chart_message = _message_to_dict(chart_node)
                except Exception:
                    chart_message = {}
                chart_result_payload = chart_message.get("result")

                vega_config_dict: dict[str, Any] = {}
                if isinstance(chart_result_payload, dict):
                    payload_vega_config = chart_result_payload.get("vega_config")
                    if isinstance(payload_vega_config, dict):
                        vega_config_dict = payload_vega_config

                if not vega_config_dict:
                    chart_result = getattr(chart_node, "result", None)
                    if chart_result:
                        vega_config = getattr(chart_result, "vega_config", None)
                        if vega_config is not None:
                            try:
                                parsed_vega_config = _message_to_dict(vega_config)
                            except Exception:
                                parsed_vega_config = {}
                            if isinstance(parsed_vega_config, dict):
                                vega_config_dict = parsed_vega_config

                if vega_config_dict:
                    ctx.session.state[CHART_RESULT_VEGA_CONFIG_STATE_KEY] = (
                        vega_config_dict
                    )
                else:
                    logger.warning(
                        "Chart message received but vega config could not be parsed."
                    )

                image_payload = (
                    chart_result_payload.get("image")
                    if isinstance(chart_result_payload, dict)
                    else None
                )
                image_data = (
                    image_payload.get("data")
                    if isinstance(image_payload, dict)
                    else None
                )
                image_mime_type = (
                    image_payload.get("mime_type")
                    if isinstance(image_payload, dict)
                    else None
                )

                if not image_data:
                    chart_result = getattr(chart_node, "result", None)
                    image_blob = getattr(chart_result, "image", None) if chart_result else None
                    image_data = getattr(image_blob, "data", b"") if image_blob else b""
                    image_mime_type = getattr(image_blob, "mime_type", "") if image_blob else ""

                if image_data:
                    ctx.session.state[CHART_RESULT_IMAGE_PRESENT_STATE_KEY] = True
                    ctx.session.state[CHART_RESULT_IMAGE_MIME_TYPE_STATE_KEY] = (
                        image_mime_type or ""
                    )

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


class ConversationalAnalyticsQueryAgent(BaseAgent):
    """Runs NLQ requests against CA API and streams results back into the chat."""

    name: str
    instruction: str
    model: str
    ca_llm_agent: LlmAgent | None = None

    def __init__(
        self,
        name: str,
        instruction: str,
        model: str = "gemini-2.5-flash-lite",
    ) -> None:
        init_data: dict[str, Any] = {
            "name": name,
            "instruction": instruction,
            "model": model,
        }
        super().__init__(**init_data)

        self.ca_llm_agent = LlmAgent(
            name=name,
            instruction=instruction,
            model=model,
            tools=[tool_intercept],
            planner=BuiltInPlanner(
                thinking_config=ThinkingConfig(include_thoughts=False, thinking_budget=0)
            ),
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        if self.ca_llm_agent is None:
            raise RuntimeError("ca_llm_agent is not initialized.")

        async for event in self.ca_llm_agent.run_async(ctx):
            logger.info(event.model_dump_json(indent=2, exclude_none=True))

            if not event.content or not event.content.parts:
                yield Event(
                    author=self.name,
                    partial=False,
                    turn_complete=True,
                    invocation_id=event.invocation_id,
                    content=event.content,
                )
                break

            first_part = event.content.parts[0]
            function_call = first_part.function_call
            if not function_call:
                yield Event(
                    author=self.name,
                    partial=False,
                    turn_complete=True,
                    invocation_id=event.invocation_id,
                    content=event.content,
                )
                break

            status_message = types.Content(
                role="model",
                parts=[
                    types.Part(text="I'll invoke the Looker Conversational Analytics API")
                ],
            )
            yield Event(
                author=self.name,
                partial=False,
                turn_complete=False,
                invocation_id=event.invocation_id,
                content=status_message,
            )

            args: Any = function_call.args
            question = args.get("question") if isinstance(args, dict) else None
            if not isinstance(question, str) or not question.strip():
                error_content = types.Content(
                    role="model",
                    parts=[
                        types.Part(
                            text=(
                                "I could not find a valid question argument for the "
                                "query tool."
                            )
                        )
                    ],
                )
                yield Event(
                    author=self.name,
                    partial=False,
                    turn_complete=True,
                    invocation_id=event.invocation_id,
                    content=error_content,
                )
                break

            async for data_chunk in stream_nlq(question, ctx):
                chunk_content = types.Content(
                    role="model",
                    parts=[types.Part(text=data_chunk)],
                )
                yield Event(
                    author=self.name,
                    partial=False,
                    turn_complete=False,
                    invocation_id=event.invocation_id,
                    content=chunk_content,
                )

            yield Event(
                author=self.name,
                partial=False,
                turn_complete=True,
                invocation_id=event.invocation_id,
            )
            break


def build_conversational_analytics_query_agent() -> ConversationalAnalyticsQueryAgent:
    """Factory for the CA query sub-agent."""
    return ConversationalAnalyticsQueryAgent(
        name="conversational_analytics_query_agent",
        model="gemini-2.5-flash-lite",
        instruction="""You are a specialized data analysis assistant. Your primary purpose is to answer user questions about business analytics by retrieving data using your available tools.

### Core Logic
1. Analyze the User's Request:
   - Analytics Question: Is the user asking for metrics, KPIs, statistics, trends, or information about the dataset?
   - General Conversation: Is the user making small talk?

2. Take Action:
   - If it IS an analytics question: you MUST use the query tool to find the answer.
   - If it is NOT an analytics question: respond directly as a helpful assistant and do NOT use tools.

### Handling Tool Results
- Base your answer exclusively on the tool result.
- Synthesize raw data into a clear, natural-language answer.
- Do not output raw JSON unless the user explicitly asks for it.""",
    )
