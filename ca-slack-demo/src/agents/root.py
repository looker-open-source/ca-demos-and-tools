"""ADK agent graph — generated from AGENT_CONFIGS.

To add a new dataset:
  1. Add an AgentConfig block to src/config.py
  2. Set the corresponding CA_AGENT_* env var
  3. Restart — no code changes needed here.
"""

from __future__ import annotations

from google.adk.agents import Agent

from src.config import AGENT_CONFIGS, AGENT_MODEL, ROUTER_MODEL
from src.tools.ca_tools import TOOLS

_AGENT_INSTRUCTION = (
    "You answer data questions about {display_name}. "
    "Use the {tool_name} tool to run queries.\n\n"
    "When presenting results:\n"
    "- Lead with a clear, direct answer to the question\n"
    "- If a chart was generated, mention that a chart is available\n"
    "- Show the SQL query used in a code block for transparency\n"
    "- If there's an error, explain it simply and suggest rephrasing\n"
    "- If the user explicitly asks to export the results of a query to Google Sheets, use the `export_to_google_sheets` tool with a descriptive title and the data in JSON format.\n"
    "- If the user explicitly asks to export the results of a query to Google Slides, use the `export_to_google_slides` tool. To create multiple slides or include charts, pass a JSON array of dicts: `[{{\"title\": \"Slide Title\", \"data\": [...], \"bullets\": [...], \"chart_spec\": {{...}}}}]`. Always include the full data table in `data` and a Vega-Lite spec in `chart_spec` if a chart is requested or appropriate!\n\n"
    "Do NOT make up data. Only report what the tool returns."
)

from src.tools.ca_tools import export_to_google_sheets, export_to_google_slides

# Build one sub-agent per configured dataset (skip any with no agent_id)
sub_agents: list[Agent] = []
for name, cfg in AGENT_CONFIGS.items():
    if not cfg.agent_id:
        continue
    tool = TOOLS[name]
    sub_agents.append(Agent(
        name=name,
        model=AGENT_MODEL,
        description=cfg.description,
        instruction=_AGENT_INSTRUCTION.format(
            display_name=cfg.display_name,
            tool_name=tool.__name__,
        ),
        tools=[tool, export_to_google_sheets, export_to_google_slides],
    ))

_agent_list = ", ".join(cfg.display_name for cfg in AGENT_CONFIGS.values() if cfg.agent_id)

root_agent = Agent(
    name="data_router",
    model=ROUTER_MODEL,
    description="Routes data analytics questions to the right specialist agent.",
    instruction=(
        "You are a data analytics assistant. Route each question to the most "
        "appropriate specialist agent based on the data domain.\n\n"
        "Available agents: %s.\n\n"
        "ROUTING RULES:\n"
        "- Independently evaluate EVERY message in the conversation history to determine "
        "the most appropriate agent(s), rather than defaulting to the previous agent.\n"
        "- Pay close attention to time horizons and data domains: if a follow-up shifts "
        "from real-time transactional metrics to historical aggregates, reviews, or benchmarks, "
        "route to the correct specialist agent regardless of who started the thread.\n"
        "- If a single question spans multiple data domains or timeframes, call EACH relevant "
        "agent and synthesize their answers into a single coherent response.\n"
        "- When comparing recent transactions (e.g., 'last 7 days') with the same period last year, "
        "you MUST call the AlloyDB Agent for the recent data AND the Looker Agent for the historical data, "
        "then synthesize the results into a direct comparison.\n"
        "- Route all product review questions exclusively to the BigQuery Agent (use BigQuery, not Looker).\n"
        "- If the message starts with [Route to <agent>], always honor that.\n"
        "- If no agent fits, say so and list available agents.\n"
        "- ALWAYS delegate — never answer data questions yourself."
    ) % _agent_list,
    sub_agents=sub_agents,
)
