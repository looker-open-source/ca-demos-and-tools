"""ADK tool wrappers for CA API agents — generated from AGENT_CONFIGS.

To add a new dataset: add an AgentConfig entry to config.py and set the
corresponding CA_AGENT_* env var. No code changes needed here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from google.adk.tools import ToolContext

from src.ca_client import CAClient
from src.config import AGENT_CONFIGS, AgentConfig, GCP_LOCATION, GCP_PROJECT_ID

log = logging.getLogger(__name__)

# Module-level CA client singleton
_ca_client: CAClient | None = None

# Progress callbacks keyed by session_id — bypasses ADK session state which
# returns copies on get_session() and cannot hold non-serializable callables.
# Each entry: {"step": async (label) -> None, "query": async () -> None}
_progress_callbacks: dict[str, dict[str, Any]] = {}


def set_progress_callback(session_id: str, on_step: Any, on_query_start: Any) -> None:
    """Register async progress callbacks for a session."""
    _progress_callbacks[session_id] = {"step": on_step, "query": on_query_start}
    log.info("Progress callbacks registered for session %s", session_id)


def clear_progress_callback(session_id: str) -> None:
    """Remove progress callbacks for a session (call when done)."""
    _progress_callbacks.pop(session_id, None)
    log.info("Progress callbacks cleared for session %s", session_id)


def _get_client() -> CAClient:
    global _ca_client
    if _ca_client is None:
        _ca_client = CAClient(project_id=GCP_PROJECT_ID, location=GCP_LOCATION)
    return _ca_client



from src.mcp_server import create_and_export_sheet, create_and_export_slides

async def export_to_google_sheets(title: str, data_json: str, tool_context: ToolContext) -> str:
    """Export tabular data to a new Google Sheet.
    
    Args:
        title: Title for the new spreadsheet.
        data_json: A JSON string representing a list of lists (rows).
    """
    try:
        import json
        data_matrix = json.loads(data_json)
        result = create_and_export_sheet(title=title, data_matrix=data_matrix)
        return result
    except Exception as e:
        return f"Error exporting to Google Sheets: {e}"

async def export_to_google_slides(title: str = None, data_json: str = None, tool_context: ToolContext = None) -> str:
    """Export tabular data to a new Google Slides presentation.
    
    Args:
        title: Optional title for the new presentation. If not provided, one will be generated.
        data_json: A JSON string representing either a single table (list of lists) 
                   or multiple slides (list of dicts with 'title', 'data', 'bullets', 'chart_spec').
                   'chart_spec' is optional and should be a Vega-Lite JSON object or string if available.
    """
    try:
        if not data_json:
            return "Error: data_json is required."
            
        import json
        data = json.loads(data_json)
        
        if not title:
            title = "Automated Data Export"
            
        # Handle both single table and multi-slide formats
        if data and isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            slides = data
        else:
            slides = [{"title": "Data Summary", "data": data}]
            
        result = create_and_export_slides(presentation_title=title, slides=slides)
        return result
    except Exception as e:
        return f"Error exporting to Google Slides: {e}"

def make_ca_tool(agent_name: str, config: AgentConfig) -> Callable:
    """Create an ADK-compatible tool function for a CA agent.

    The function's __name__ and __doc__ drive the LLM tool schema,
    so each agent gets a distinct, descriptive tool.

    Session state keys used (per agent):
      _on_progress       — sync progress callback set by Slack handler
      _conv_<agent>      — CA conversation_id for multi-turn continuity
    """
    conv_key = "_conv_%s" % agent_name

    async def tool_fn(question: str, tool_context: ToolContext) -> dict[str, Any]:
        session_id = tool_context.session.id
        cbs = _progress_callbacks.get(session_id, {})
        on_progress = cbs.get("step")
        on_query_start = cbs.get("query")
        log.info("Tool %s starting (session=%s, has_progress=%s)", agent_name, session_id, on_progress is not None)
        conversation_id = tool_context.state.get(conv_key)

        config = AGENT_CONFIGS.get(agent_name)
        if not config or not config.agent_id:
            return {"error": "No CA_AGENT_%s env var configured." % agent_name.upper()}

        import os
        context_path = f"context/{agent_name}/context.json"
        context = None
        if os.path.exists(context_path):
            try:
                with open(context_path, "r") as f:
                    context = json.load(f)
            except Exception as e:
                log.error("Failed to load context from %s: %s", context_path, e)

        response = await _get_client().chat(
            agent_id=config.agent_id,
            question=question,
            conversation_id=conversation_id,
            on_progress=on_progress,
            on_query_start=on_query_start,
            context=context,
        )

        # Persist conversation_id so follow-ups in the same thread reuse it
        if response.conversation_id:
            tool_context.state[conv_key] = response.conversation_id

        result: dict[str, Any] = {
            "text_answer": response.text_answer or "No answer returned.",
            "generated_sql": response.generated_sql,
            "latency_ms": response.latency_ms,
        }
        if response.result_rows:
            result["result_rows"] = response.result_rows[:10]
        if response.chart_spec:
            result["chart_spec"] = json.dumps(response.chart_spec)
        if response.planner_reasoning:
            result["planner_reasoning"] = response.planner_reasoning
        if response.error:
            result["error"] = response.error

        return result

    tool_fn.__name__ = "query_%s" % agent_name
    tool_fn.__doc__ = (
        "Query the %s dataset.\n\n"
        "Args:\n"
        "    question: Natural language question about the data.\n\n"
        "Returns:\n"
        "    Dictionary with text_answer, generated_sql, result_rows, and chart info."
    ) % config.display_name

    return tool_fn


# Pre-built tool registry — used by agent factory and importable for testing
TOOLS: dict[str, Callable] = {
    name: make_ca_tool(name, cfg)
    for name, cfg in AGENT_CONFIGS.items()
}
