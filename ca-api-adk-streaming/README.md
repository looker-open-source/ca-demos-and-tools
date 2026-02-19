# Conversational Analytics API Agent

This project uses the Conversational Analytics API as the primary data interface with optional post-processing sub-agents.

## Architecture

The runtime entrypoint is `root_agent` in `ca_api_agent/agent.py`.
The same `root_agent` is defined in `ca_api_agent/root_agent.py`.

## Execution Flow

1. `root_agent` always runs the CA query agent first.
2. Query outputs are streamed back and normalized into session state (`temp:data_result`, `temp:summary_data`).
3. Optional sub-agents are selected deterministically from `run_when` predicates and run sequentially.
4. Optional-step failures emit warnings and the response flow continues with available results.

## Folder Structure

- `ca_api_agent/agent.py`
  - Canonical ADK entrypoint (`root_agent`).
- `ca_api_agent/root_agent.py`
  - Defines deterministic CA-first orchestration (`RootAgent`) and optional sub-agent routing.
  - Exposes `root_agent`.
- `ca_api_agent/agents/ca_query.py`
  - Defines `ConversationalAnalyticsQueryAgent` and the CA API streaming bridge.
- `ca_api_agent/agents/visualization.py`
  - Visualization sub-agent factory used by the built-in optional visualization step.
- `deployment/deploy.py`
  - Deployment script for Agent Engine.

## Running Locally

1. Install dependencies:

```bash
uv sync --frozen
```

2. Activate virtualenv:

```bash
source .venv/bin/activate
```

3. Create `.env` in this folder (you can copy from `.env.example`) with:

```bash
GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
GOOGLE_CLOUD_LOCATION=<your-gcp-location>
GOOGLE_CLOUD_STORAGE_BUCKET=<your-gcs-bucket-name> # Optional for deployment only. If omitted, deploy defaults to <GOOGLE_CLOUD_PROJECT>-adk-staging.
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

## Optional Sub-Agents (Example)

Default behavior is deterministic CA-first with optional sub-agent routing.
You can extend the workflow by adding more entries in `optional_sub_agents` in
`ca_api_agent/root_agent.py`.

Example routing spec pattern:

```python
from dataclasses import dataclass
from typing import Callable

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext

from ca_api_agent.agents.ca_query import build_conversational_analytics_query_agent
from ca_api_agent.agents.my_new_agent import build_my_new_agent


@dataclass(frozen=True)
class OptionalSubAgentSpec:
    key: str
    description: str
    agent: BaseAgent
    run_when: Callable[[InvocationContext], bool]


query_agent = build_conversational_analytics_query_agent(name="query_agent")
my_new_agent = build_my_new_agent()

optional_sub_agents = [
    OptionalSubAgentSpec(
        key="my_new_step",
        description="custom post-processing",
        agent=my_new_agent,
        run_when=lambda ctx: bool(ctx.session.state.get("temp:data_result")),
    ),
]
```

Suggested orchestration sequence when you enable this:

1. Always run the CA query agent first.
2. Check each `run_when` predicate against `ctx.session.state`.
3. Run only matching optional sub-agents.
4. Stream each step's output back to the user.

Current built-in optional step:

- `visualization` runs when `temp:data_result` is non-empty.
- Visualization output is sanitized in root orchestration for ADK web:
  - inline image bytes are converted to markdown `data:` image URIs.
  - fenced code blocks are stripped from text parts.
- If an optional step fails, root emits a warning and continues.

## Deploying to Agent Engine

1. Ensure `.env` values are set.
   `GOOGLE_CLOUD_STORAGE_BUCKET` is optional and only used for deployment
   staging. If not set, `deployment/deploy.py` uses
   `<GOOGLE_CLOUD_PROJECT>-adk-staging`.
2. Run:

```bash
./deploy.sh
```

The script builds the wheel and runs `deployment/deploy.py`.
