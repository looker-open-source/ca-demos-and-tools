# CA Demo — Slack Analytics Bot

A Slack bot that answers natural language questions about your data using Google's Conversational Analytics API. Ask about e-commerce, Stack Overflow, NCAA basketball, US Census, or Google Analytics — the bot routes to the right dataset, runs the query, and returns an answer with SQL and a chart.

Built on Google ADK, Slack Bolt (Socket Mode), and vl-convert.

---

## How It Works

Mention the bot in any channel:

```
@ca-bot-demo what were the top products by revenue last month?
```

The bot posts a progress message that updates as it works — routing decision, CA reasoning steps, BigQuery execution time — then replies in the thread with the answer, planner reasoning, SQL, and a chart when one is available.

Follow-up questions in the same thread reuse the CA conversation automatically:

```
You:         what were the top 10 products by revenue last month?
ca-bot-demo: [answer + chart]
You:         break that down by category
ca-bot-demo: [follow-up using the same conversation]
```

Type `@ca-bot-demo help` to see available datasets and tips.

---

## Datasets

| Agent | Data | BigQuery source |
|---|---|---|
| TheLook | E-commerce orders, products, revenue | `bigquery-public-data.thelook_ecommerce` |
| Stack Overflow | Developer Q&A, tags, trends | `bigquery-public-data.stackoverflow` |
| NCAA | Men's basketball, March Madness | `bigquery-public-data.ncaa_basketball` |
| US Census | Demographics, income, housing | `bigquery-public-data.census_bureau_acs` |
| GA4 | Google Analytics 4 events & purchases | `bigquery-public-data.ga4_obfuscated_sample_ecommerce` |
| GA360 | Google Analytics 360 web traffic | `bigquery-public-data.google_analytics_sample` |

---

## Prerequisites (both paths)

These steps are required whether you're running locally or deploying to Cloud Run.

- Python 3.10+ and [uv](https://docs.astral.sh/uv/)
- GCP project with **Vertex AI** and **Conversational Analytics API** enabled
- CA agents created — one per dataset. Copy each agent's resource ID from the [CA console](https://cloud.google.com/conversational-analytics).

### Create a Slack App

1. [api.slack.com/apps](https://api.slack.com/apps) → **Create New App → From scratch**
2. **OAuth & Permissions → Bot Token Scopes**: add `app_mentions:read`, `chat:write`, `files:write`, `channels:history`, `groups:history`, `im:history`, `channels:read`
3. **Event Subscriptions → Subscribe to bot events**: add `app_mention` and `message.channels`
4. **Socket Mode**: enable → **App-Level Tokens** → generate a token with `connections:write` scope → copy the `xapp-...` token
5. **Install App to Workspace** → copy the Bot User OAuth Token (`xoxb-...`)
6. In Slack: `/invite @ca-bot-demo` in your channel

---

## Running Locally

This is the fastest way to get started. The bot runs on your machine using your personal GCP credentials — no service account or Docker required.

### 1. Authenticate with GCP

```bash
gcloud auth application-default login
```

Your personal Google account needs three IAM roles on the GCP project:

| Role | Why |
|---|---|
| `roles/geminidataanalytics.dataAgentUser` | Call the CA API |
| `roles/cloudaicompanion.user` | Create CA conversations (`cloudaicompanion.topics.create`) |
| `roles/aiplatform.user` | Call Vertex AI for the Gemini routing model |

For the public BigQuery datasets in this demo, personal Google accounts typically have read access already. If you get a BigQuery permission error, add `roles/bigquery.jobUser` to your account as well (required for service accounts — see Cloud Run section).

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in your values:

```bash
# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...

# GCP
GCP_PROJECT_ID=your-project
GCP_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
GOOGLE_CLOUD_PROJECT=your-project
GOOGLE_CLOUD_LOCATION=global

# Workspace (Optional)
SHARED_DRIVE_ID=your-shared-drive-id

# Models
ROUTER_MODEL=gemini-3.1-flash-lite-preview
AGENT_MODEL=gemini-3.1-flash-lite-preview

# CA agent IDs — leave blank to skip an agent
CA_AGENT_THELOOK=your-agent-id
CA_AGENT_STACKOVERFLOW=your-agent-id
CA_AGENT_NCAA=your-agent-id
CA_AGENT_CENSUS=your-agent-id
CA_AGENT_GA4=your-agent-id
CA_AGENT_GA360=your-agent-id
```

### 3. Provision Agents (Optional)

If you don't have Conversational Analytics agents created yet, you can use the provisioning script to create them. This script reads the `context.json` files in the `context/` directory and creates agents in your GCP project.

```bash
uv run python scripts/provision_agents.py
```

To update existing agents instead of creating new ones:

```bash
uv run python scripts/provision_agents.py --update
```

The script will print the agent IDs. Add these to your `.env` file.

### 4. Run

```bash
uv sync
uv run python scripts/run_slack.py
```

To test routing and CA queries without Slack:

```bash
uv run python scripts/test_cli.py
```

---

## Deploying to Cloud Run

Socket Mode connects outbound to Slack — no public inbound URL or load balancer is needed. A minimal health check server in the app handles Cloud Run's port requirement. The bot runs as a dedicated service account rather than your personal credentials.

### 1. Create a service account

```bash
gcloud iam service-accounts create ca-bot \
  --display-name="CA Slack Bot" \
  --project=YOUR_PROJECT

gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member="serviceAccount:ca-bot@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/geminidataanalytics.dataAgentUser"

gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member="serviceAccount:ca-bot@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/cloudaicompanion.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member="serviceAccount:ca-bot@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding YOUR_PROJECT \
  --member="serviceAccount:ca-bot@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"
```

### 2. Build the container

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT/ca-demo
```

### 3. Deploy

```bash
gcloud run deploy ca-demo \
  --image gcr.io/YOUR_PROJECT/ca-demo \
  --region us-central1 \
  --no-allow-unauthenticated \
  --min-instances 1 \
  --no-cpu-throttling \
  --service-account ca-bot@YOUR_PROJECT.iam.gserviceaccount.com \
  --set-env-vars "\
SLACK_BOT_TOKEN=xoxb-...,\
SLACK_APP_TOKEN=xapp-...,\
GCP_PROJECT_ID=YOUR_PROJECT,\
GCP_LOCATION=global,\
GOOGLE_GENAI_USE_VERTEXAI=true,\
GOOGLE_CLOUD_PROJECT=YOUR_PROJECT,\
GOOGLE_CLOUD_LOCATION=global,\
ROUTER_MODEL=gemini-3.1-flash-lite-preview,\
AGENT_MODEL=gemini-3.1-flash-lite-preview,\
GRPC_DNS_RESOLVER=native,\
CA_AGENT_THELOOK=your-agent-id,\
CA_AGENT_STACKOVERFLOW=your-agent-id,\
CA_AGENT_NCAA=your-agent-id,\
CA_AGENT_CENSUS=your-agent-id,\
CA_AGENT_GA4=your-agent-id,\
CA_AGENT_GA360=your-agent-id"
```

### 4. Verify

Check the Cloud Run logs — you should see the health server start and the Socket Mode connection to Slack establish within a few seconds of deploy completing:

```
Health check server listening on :8080
Bot user ID: U...
Active agents: thelook, stackoverflow, ncaa, ...
```

> **Note:** The service does not need `--allow-unauthenticated`. The bot connects outbound to Slack over Socket Mode — Cloud Run only needs to respond to the internal health check on `$PORT`.

### 5. Tear down

To stop the service and avoid charges:

```bash
gcloud run services delete ca-demo --region us-central1 --project YOUR_PROJECT --quiet
```

Redeploy anytime by repeating steps 2–3. The service account and its IAM bindings persist, so you only need to recreate them once.

---

## Authentication

The bot uses Application Default Credentials. The identity depends on where it runs:

| Environment | Identity |
|---|---|
| Local dev | Your personal Google account (via `gcloud auth application-default login`) |
| Cloud Run | The service account attached to the Cloud Run service |

Both need `roles/geminidataanalytics.dataAgentUser`, `roles/cloudaicompanion.user`, `roles/aiplatform.user`, and `roles/bigquery.jobUser`.

**Per-user mode** (enterprise): for deployments where different users should see different data, the bot can call the CA API as each Slack user's own GCP identity using domain-wide delegation. This requires a Google Workspace admin and all Slack users to have Google identities in the same org. See [BACKLOG.md](BACKLOG.md) for implementation notes — shared mode is the right starting point.

---

## Adding a Dataset

Two steps, no code changes:

**1.** Add an `AgentConfig` to `src/config.py`:

```python
"my_dataset": AgentConfig(
    name="my_dataset",
    display_name="My Dataset",
    agent_id=os.environ.get("CA_AGENT_MY_DATASET", ""),
    description="Answers questions about ...",
    emoji=":bar_chart:",
),
```

**2.** Add to `.env` (local) or `--set-env-vars` (Cloud Run):

```bash
CA_AGENT_MY_DATASET=your-ca-agent-id
```

Restart the bot. The sub-agent, tool, and root agent registration all generate automatically from the config.

---

## Expanding the Framework (ADK & MCP)

This project is built on the **Google Agentic Development Kit (ADK)** and uses the **Model Context Protocol (MCP)** to expose tools like Google Sheets and Slides.

### Using ADK (Agentic Development Kit)

The ADK is used to define the agent graph and handle multi-turn conversations.

*   **Router Agent**: `src/agents/root.py` defines a central router agent that delegates user requests to specialist sub-agents.
*   **Dynamic Sub-Agents**: Sub-agents are generated automatically from the `AGENT_CONFIGS` in `src/config.py`.

#### Adding a Custom ADK Tool

If you want to add a custom tool (e.g., a direct API call to BigQuery or an external service) that bypasses the Conversational Analytics API, you can define a Python function and add it to an agent's tools list.

Example:

```python
from google.adk.tools import ToolContext

async def get_weather(location: str, tool_context: ToolContext) -> str:
    """Get the current weather for a location.
    
    Args:
        location: The city and state, e.g. San Francisco, CA
    """
    # Call weather API here
    return f"The weather in {location} is sunny."
```

Then add it to the `tools` list of an agent in `src/agents/root.py`:

```python
sub_agents.append(Agent(
    name=name,
    model=AGENT_MODEL,
    description=cfg.description,
    instruction=...,
    tools=[tool, export_to_google_sheets, export_to_google_slides, get_weather], # Add here
))
```

### Using MCP (Model Context Protocol)

This project uses FastMCP to expose Google Workspace tools.

*   **MCP Server**: `src/mcp_server.py` runs a FastMCP server with tools to create Sheets and Slides.
*   **Tool Binding**: In `src/tools/ca_tools.py`, these MCP tools are imported and wrapped as ADK tools so the agents can use them.

#### Adding a New MCP Tool

1.  Add a new tool function in `src/mcp_server.py` using the `@mcp.tool()` decorator.
2.  Import it in `src/tools/ca_tools.py` and add it to the list of tools provided to the sub-agents in `src/agents/root.py`.

---

## Tips

- `@ca-bot-demo help` — shows available datasets and usage tips
- `@ca-bot-demo @ncaa ...` — forces routing to a specific dataset
- Follow-up questions in the same thread don't need `@ca-bot-demo` (requires `message.channels` event subscription)
- Questions can span multiple turns — ask broadly, then drill down

---

## AI-Assisted Development

This project includes context files to support development with AI assistants:
- `CLAUDE.md`: For use with Claude Code.
- `GEMINI.md`: For use with Gemini CLI.

These files provide the AI with the necessary context about the project structure, design decisions, and environment variables to help you navigate and extend the codebase more effectively.

---

## Project Structure

```
src/
  agents/root.py       # ADK agent graph, generated from AGENT_CONFIGS
  tools/ca_tools.py    # CA tool factory, one tool per configured agent
  slack/
    app.py             # Slack Bolt handlers, ADK runner, health server
    progress.py        # In-place progress message tracker
    blocks.py          # Block Kit formatting
    mention.py         # @mention parsing
  ca_client.py         # Async CA API gRPC client (v1beta)
  config.py            # AGENT_CONFIGS — single source of truth
  mcp_server.py        # FastMCP server for Google Workspace tools
  charts/renderer.py   # Vega-Lite → PNG
scripts/
  run_slack.py         # Entry point
  test_cli.py          # CLI test, no Slack needed
```
