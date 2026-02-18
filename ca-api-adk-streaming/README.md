# Conversational Analytics API Agent

This project uses the Gemini Conversational Analytics API as the primary data interface, with a root orchestration agent that can optionally run additional specialized sub-agents.

## Architecture

The runtime entrypoint is `root_agent` in `ca_api_agent/agent.py`.
The same `root_agent` is defined in `ca_api_agent/root_agent.py`.

Execution flow:

1. Root agent always runs the CA query agent first.
2. Query/chart results are stored in session state (`temp:data_result`, `temp:summary_data`, `temp:chart_result_vega_config`).
3. Optional sub-agents run only when deterministic response-shape rules match.

## Folder Structure

- `ca_api_agent/agent.py`
  - Canonical ADK entrypoint (`root_agent`).
- `ca_api_agent/root_agent.py`
  - Defines `RootAgent` and the optional sub-agent registry.
  - Exposes `root_agent`.
- `ca_api_agent/agents/ca_query.py`
  - Defines `ConversationalAnalyticsQueryAgent` and CA API streaming bridge.
- `ca_api_agent/agents/visualization.py`
  - Defines factory for visualization sub-agent.
- `deployment/deploy.py`
  - Deployment script for Agent Engine.

## How Optional Routing Works

Optional sub-agents are configured in `optional_sub_agents` in `ca_api_agent/root_agent.py`.

Each entry includes:

- `key`: stable id for logs/routing
- `description`: human-readable step name
- `agent`: sub-agent instance
- `run_when`: callable predicate receiving `InvocationContext`

Current built-in rules:

- Visualization agent runs when CA API returned `system_message.chart.result.vega_config`, persisted as `temp:chart_result_vega_config`.

## Add a New Sub-Agent

1. Add a new agent factory module under `ca_api_agent/agents/` (for example `my_new_agent.py`).
2. Import and instantiate it in `ca_api_agent/root_agent.py`.
3. Append an `OptionalSubAgentSpec` entry to `optional_sub_agents`.

Example:

```python
from ca_api_agent.agents.my_new_agent import build_my_new_agent

my_new_agent = build_my_new_agent()

optional_sub_agents = [
    # existing entries...
    OptionalSubAgentSpec(
        key="my_new_step",
        description="custom post-processing",
        agent=my_new_agent,
        run_when=lambda ctx: bool(ctx.session.state.get("temp:data_result")),
    ),
]
```

## Running Locally

1. Install dependencies:

```bash
uv sync --frozen
```

2. Activate virtualenv:

```bash
source .venv/bin/activate
```

3. Create `.env` in this folder with:

```bash
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GOOGLE_CLOUD_LOCATION=<your-gcp-location>
GOOGLE_GENAI_USE_VERTEXAI=1
LOOKERSDK_CLIENT_ID=<your-looker-client-id>
LOOKERSDK_CLIENT_SECRET=<your-looker-client-secret>
LOOKERSDK_BASE_URL=<your-looker-base-url>
LOOKML_MODEL=<your-lookml-model>
LOOKML_EXPLORE=<your-lookml-explore>
```

4. Start ADK web:

```bash
adk web
```

## Deploying to Agent Engine

1. Ensure `.env` values are set.
2. Run:

```bash
./deploy.sh
```

The script builds the wheel and runs `deployment/deploy.py`.
