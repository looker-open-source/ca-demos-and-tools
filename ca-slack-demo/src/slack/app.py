"""Slack Bolt application — Socket Mode, async.

Uses Socket Mode so no public URL is needed (works locally and on Cloud Run).
Each Slack thread maps to an ADK session, giving free multi-turn memory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import Client, types
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

from src.agents.root import root_agent
from src.charts.renderer import render_chart
from src.config import AGENT_CONFIGS, SLACK_APP_TOKEN, SLACK_BOT_TOKEN
from src.slack.blocks import format_answer_blocks, help_blocks, thinking_blocks
from src.slack.mention import parse_agent_mention, strip_bot_mention
from src.slack.progress import ProgressTracker
from src.tools.ca_tools import clear_progress_callback, set_progress_callback
import uuid
from src.web_app import shared_reports

log = logging.getLogger(__name__)

APP_NAME = "slack-analytics-agents"

# --- ADK runner ---
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

# --- Slack app ---
app = AsyncApp(token=SLACK_BOT_TOKEN)
_bot_user_id: str = ""  # set on startup


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------

async def _run_agent(
    text: str,
    user_id: str,
    session_id: str,
    on_routing: Any = None,
) -> dict[str, Any]:
    """Run the ADK agent and return a structured result dict.

    Fires on_routing(agent_name) as soon as the root agent picks a sub-agent,
    well before the CA API call completes — used for live progress updates.
    """
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id,
    )
    if session is None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )

    content = types.Content(role="user", parts=[types.Part(text=text)])

    text_parts: list[str] = []
    agent_name = ""
    chart_spec = None
    sql = None
    planner_reasoning = None
    latency_ms = 0
    ca_error = None
    reported_agents = set()

    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=content,
    ):
        if event.author and event.author != "data_router" and event.author not in reported_agents:
            reported_agents.add(event.author)
            if on_routing:
                await on_routing(event.author)

        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    text_parts.append(part.text)
                if part.function_response:
                    resp = part.function_response.response
                    if isinstance(resp, dict):
                        chart_spec = chart_spec or resp.get("chart_spec")
                        sql = sql or resp.get("generated_sql")
                        planner_reasoning = planner_reasoning or resp.get("planner_reasoning")
                        latency_ms = latency_ms or resp.get("latency_ms", 0)
                        ca_error = ca_error or resp.get("error")

        if event.author and event.author != "data_router":
            agent_name = event.author

    return {
        "text": "\n".join(text_parts) or "No response from agent.",
        "sql": sql,
        "chart_spec": chart_spec,
        "planner_reasoning": planner_reasoning,
        "agent_name": agent_name,
        "latency_ms": latency_ms,
        "ca_error": ca_error,
    }


# ---------------------------------------------------------------------------
# Error messaging
# ---------------------------------------------------------------------------

_ERROR_MESSAGES: dict[str, str] = {
    "timeout": (
        ":hourglass: *Query timed out.* "
        "This question may require too much data — try narrowing the date range, "
        "limiting to a specific category, or asking for a summary instead."
    ),
    "permission_denied": (
        ":lock: *Access denied.* "
        "The service account doesn't have permission to access this dataset. "
        "Contact your admin to check `roles/geminidataanalytics.user` and BigQuery permissions."
    ),
    "not_found": (
        ":mag: *Agent not found.* "
        "The configured CA agent ID for this dataset may be incorrect or deleted. "
        "Check the `CA_AGENT_*` environment variables."
    ),
    "quota_exceeded": (
        ":warning: *Quota exceeded.* "
        "Too many requests to the analytics service — please wait a moment and try again."
    ),
    "unavailable": (
        ":satellite: *Service temporarily unavailable.* "
        "The Conversational Analytics API is unreachable — please try again in a moment."
    ),
}

_NO_ANSWER_MESSAGE = (
    ":thinking_face: *No answer returned.* "
    "The analytics service processed the query but didn't return a result. "
    "Try rephrasing or asking a more specific question."
)


def _error_text(error: str | None, text: str | None) -> str | None:
    """Return a user-friendly error string, or None if the result looks valid."""
    if error:
        for key, msg in _ERROR_MESSAGES.items():
            if error.startswith(key):
                return msg
        return ":warning: *Something went wrong.* %s" % error
    if not text or text.strip() == "No answer returned.":
        return _NO_ANSWER_MESSAGE
    return None


# ---------------------------------------------------------------------------
# Shared result poster
# ---------------------------------------------------------------------------

async def _post_result(
    result: dict[str, Any],
    channel: str,
    thread_ts: str,
    question: str,
    update_ts: str | None = None,
) -> None:
    """Post (or update) the answer, SQL, reasoning, and chart in the thread.

    If update_ts is given, the first message updates that existing message
    (used to replace the Thinking... placeholder). Otherwise it's a new post.
    """
    cfg = AGENT_CONFIGS.get(result["agent_name"])
    emoji = cfg.emoji if cfg else ":bar_chart:"
    display_name = cfg.display_name if cfg else result["agent_name"]

    # Check for CA errors or empty answers before posting normal blocks
    error_text = _error_text(result.get("ca_error"), result.get("text"))
    if error_text:
        error_blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": error_text}}]
        if update_ts:
            await app.client.chat_update(channel=channel, ts=update_ts,
                text=error_text, blocks=error_blocks)
        else:
            await app.client.chat_postMessage(channel=channel, thread_ts=thread_ts,
                text=error_text, blocks=error_blocks)
        return

    blocks = format_answer_blocks(
        text=result["text"],
        agent_emoji=emoji,
        agent_name=display_name,
        latency_ms=result.get("latency_ms", 0),
    )

    # Generate a share ID and store the result
    share_id = str(uuid.uuid4())
    shared_reports[share_id] = {
        "question": question,
        "answer": result["text"],
        "sql": result.get("sql"),
        "chart_spec": result.get("chart_spec")
    }

    blocks.append({
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🌐 Generate Shareable Link"},
                "action_id": "share_results",
                "value": share_id
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "🤖 Suggest Next Steps"},
                "action_id": "suggest_steps",
                "value": share_id
            }
        ]
    })

    # Answer — update placeholder or post fresh
    if update_ts:
        await app.client.chat_update(
            channel=channel, ts=update_ts,
            text=result["text"], blocks=blocks,
        )
    else:
        await app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=result["text"], blocks=blocks,
        )

    # Planner reasoning (de-emphasised)
    if result.get("planner_reasoning"):
        reasoning = result["planner_reasoning"][:2800]
        await app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text=reasoning,
            blocks=[
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": ":brain: *How I planned this query*"},
                ]},
                {"type": "section", "text": {"type": "mrkdwn", "text": reasoning}},
            ],
        )

    # SQL
    if result.get("sql"):
        await app.client.chat_postMessage(
            channel=channel, thread_ts=thread_ts,
            text="```%s```" % result["sql"],
            blocks=[
                {"type": "context", "elements": [
                    {"type": "mrkdwn", "text": ":database: *SQL*"},
                ]},
                {"type": "section", "text": {
                    "type": "mrkdwn", "text": "```%s```" % result["sql"],
                }},
            ],
        )

    # Chart PNG
    if result.get("chart_spec"):
        spec = result["chart_spec"]
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except Exception:
                log.warning("chart_spec is not valid JSON — skipping chart")
                spec = None
        if spec:
            png = render_chart(spec)
            if png:
                await app.client.files_upload_v2(
                    channel=channel, thread_ts=thread_ts,
                    file=png, filename="chart.png", title="Chart",
                )
            else:
                log.warning("render_chart returned None — chart spec may be malformed")


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

@app.event("app_mention")
async def handle_mention(event: dict, say: Any) -> None:
    """Handle @bot mentions. Posts Thinking..., streams progress, then the answer."""
    thread_ts = event.get("thread_ts", event["ts"])
    channel = event["channel"]
    # Use thread_ts as user_id so all participants in the same thread share
    # one ADK session and one CA conversation per agent.
    session_user = "thread"

    text = strip_bot_mention(event["text"], _bot_user_id)

    # Help shortcut — no agent run needed
    if text.strip().lower() in {"help", "/ca-help", "ca-help"}:
        await say(blocks=help_blocks(), text="Available agents", thread_ts=thread_ts)
        return

    explicit_agent, cleaned_text = parse_agent_mention(text)
    if explicit_agent:
        cleaned_text = "[Route to %s] %s" % (explicit_agent, cleaned_text)

    # Post Thinking... placeholder
    thinking = await say(text="Thinking...", blocks=thinking_blocks(), thread_ts=thread_ts)

    # Set up progress tracker
    progress = ProgressTracker(app, channel, thinking["ts"])

    async def on_routing(agent_name: str) -> None:
        cfg = AGENT_CONFIGS.get(agent_name)
        label = ("%s %s" % (cfg.emoji, cfg.display_name)) if cfg else agent_name
        await progress.add(":arrows_counterclockwise: Routing to %s" % label)

    # Ensure session exists
    if await session_service.get_session(app_name=APP_NAME, user_id=session_user, session_id=thread_ts) is None:
        await session_service.create_session(app_name=APP_NAME, user_id=session_user, session_id=thread_ts)

    # Register progress callback in module-level dict (ADK state copies can't hold callables)
    set_progress_callback(thread_ts, progress.set_working, progress.start_query_ticker)

    progress.start_ticker()
    try:
        result = await _run_agent(
            text=cleaned_text, user_id=session_user, session_id=thread_ts,
            on_routing=on_routing,
        )
    except Exception as exc:
        log.exception("Agent run failed: %s", exc)
        await app.client.chat_update(
            channel=channel, ts=thinking["ts"],
            text=":warning: Something went wrong — please try again.",
            blocks=[{"type": "section", "text": {"type": "mrkdwn",
                "text": ":warning: *Something went wrong.* Please try again or rephrase your question."}}],
        )
        return
    finally:
        progress.stop_ticker()
        clear_progress_callback(thread_ts)

    await _post_result(result, channel, thread_ts, question=cleaned_text, update_ts=thinking["ts"])


@app.event("message")
async def handle_message(event: dict, say: Any) -> None:
    """Respond to follow-up messages in threads the bot already participated in."""
    subtype = event.get("subtype")
    has_thread = "thread_ts" in event
    has_bot_id = bool(event.get("bot_id"))
    log.info("message event: subtype=%s has_thread=%s has_bot_id=%s", subtype, has_thread, has_bot_id)

    if not has_thread or has_bot_id or subtype:
        return

    text = event.get("text", "")
    if _bot_user_id and f"<@{_bot_user_id}>" in text:
        log.info("Message contains bot mention, ignoring in handle_message to avoid double response")
        return

    thread_ts = event["thread_ts"]
    channel = event["channel"]
    session_user = "thread"

    session = await session_service.get_session(
        app_name=APP_NAME, user_id=session_user, session_id=thread_ts,
    )
    log.info("message event: thread_ts=%s session_found=%s", thread_ts, session is not None)
    if session is None:
        return  # thread not started by this bot

    text = event.get("text", "")
    explicit_agent, cleaned_text = parse_agent_mention(text)
    if explicit_agent:
        cleaned_text = "[Route to %s] %s" % (explicit_agent, cleaned_text)

    # Post Thinking... placeholder
    thinking = await say(text="Thinking...", blocks=thinking_blocks(), thread_ts=thread_ts)
    progress = ProgressTracker(app, channel, thinking["ts"])

    async def on_routing(agent_name: str) -> None:
        cfg = AGENT_CONFIGS.get(agent_name)
        label = ("%s %s" % (cfg.emoji, cfg.display_name)) if cfg else agent_name
        await progress.add(":arrows_counterclockwise: Routing to %s" % label)

    set_progress_callback(thread_ts, progress.set_working, progress.start_query_ticker)

    progress.start_ticker()
    try:
        result = await _run_agent(
            text=cleaned_text, user_id=session_user, session_id=thread_ts,
            on_routing=on_routing,
        )
    except Exception as exc:
        log.exception("Agent run failed in thread follow-up: %s", exc)
        await app.client.chat_update(
            channel=channel, ts=thinking["ts"],
            text=":warning: Something went wrong — please try again.",
            blocks=[{"type": "section", "text": {"type": "mrkdwn",
                "text": ":warning: *Something went wrong.* Please try again or rephrase your question."}}],
        )
        return
    finally:
        progress.stop_ticker()
        clear_progress_callback(thread_ts)

    await _post_result(result, channel, thread_ts, question=cleaned_text, update_ts=thinking["ts"])


@app.action("share_results")
async def handle_share(ack: Any, body: dict, say: Any) -> None:
    """Handle the share button click."""
    await ack()
    share_id = body["actions"][0]["value"]
    
    app_url = os.environ.get("APP_URL", "http://localhost:8080")
    share_link = f"{app_url}/share/{share_id}"
    
    await say(
        text=f"Here is your shareable link: {share_link}",
        thread_ts=body["message"]["ts"],
        blocks=[
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":globe_with_meridians: *Shareable Link generated:* <{share_link}|View Report>"
                }
            }
        ]
    )


@app.action("suggest_steps")
async def handle_suggest_steps(ack: Any, body: dict, say: Any) -> None:
    """Handle the suggest steps button click."""
    await ack()
    share_id = body["actions"][0]["value"]
    
    report = shared_reports.get(share_id)
    if not report:
        await say(text="Sorry, I couldn't find the report data.", thread_ts=body["message"]["ts"])
        return
        
    thinking = await say(text="Generating suggestions...", thread_ts=body["message"]["ts"])
    
    try:
        client = Client()
        prompt = f"Based on this data analysis, suggest 3 immediate business actions:\n\nAnalysis:\n{report['answer']}"
        response = client.models.generate_content(
            model='gemini-3.1-flash-lite-preview',
            contents=prompt,
        )
        
        await app.client.chat_update(
            channel=body["channel"]["id"],
            ts=thinking["ts"],
            text=response.text,
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":robot_face: *AI Suggested Next Steps:*\n\n{response.text}"
                    }
                }
            ]
        )
    except Exception as e:
        log.exception("Failed to generate suggestions: %s", e)
        await app.client.chat_update(
            channel=body["channel"]["id"],
            ts=thinking["ts"],
            text=f":warning: Failed to generate suggestions: {str(e)}",
            blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f":warning: Failed to generate suggestions: {str(e)}"}}]
        )

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

async def start() -> None:
    """Start the Slack bot (Socket Mode) and custom web app."""
    global _bot_user_id

    # Validate agent config
    configured = [name for name, cfg in AGENT_CONFIGS.items() if cfg.agent_id]
    missing = [name for name, cfg in AGENT_CONFIGS.items() if not cfg.agent_id]
    if not configured:
        raise RuntimeError("No CA agents configured — set at least one CA_AGENT_* env var.")
    log.info("Active agents: %s", ", ".join(configured))
    if missing:
        log.warning("No agent ID configured for: %s", ", ".join(missing))

    auth = await app.client.auth_test()
    _bot_user_id = auth["user_id"]
    log.info("Bot user ID: %s", _bot_user_id)

    from src.web_app import app as fastapi_app
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    # Run FastAPI server and Slack handler concurrently
    await asyncio.gather(
        server.serve(),
        AsyncSocketModeHandler(app, SLACK_APP_TOKEN).start_async(),
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(start())
