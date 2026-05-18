# CLAUDE.md — Codebase Guide for Claude Code

This file gives Claude Code the context needed to navigate and extend this project without asking obvious questions.

## What This Is

A multi-agent Slack bot that routes natural language data questions to specialist agents backed by Google's Conversational Analytics (CA) API. Built on Google ADK for routing, Slack Bolt for messaging, and vl-convert for chart rendering.

## Key Design Decisions

- **ADK sub-agents are generated from config, not hand-written.** `src/agents/root.py` builds all agents dynamically from `AGENT_CONFIGS` in `src/config.py`. Adding a dataset = one `AgentConfig` block + one env var. No other files change.
- **Socket Mode for Slack** — no public URL needed locally or on Cloud Run. Cloud Run health checks are satisfied by the `_health_server()` in `src/slack/app.py`.
- **CA conversations are per-agent, per-thread.** `_conv_<agent>` keys in ADK session state store CA `conversation_id` values so follow-up questions in the same Slack thread reuse the same CA conversation (but only within the same agent).
- **Progress updates edit one Slack message in-place.** `ProgressTracker` in `src/slack/progress.py` manages this. Routing fires from the async loop; CA milestones fire from a worker thread via `run_coroutine_threadsafe`.

## Repo Layout

```
src/
  agents/root.py          # ADK agent graph — auto-generated from AGENT_CONFIGS
  tools/ca_tools.py       # CA API tool factory — one tool per agent, generated
  slack/
    app.py                # Slack Bolt handlers + ADK runner + startup
    progress.py           # ProgressTracker (edits Thinking... message in-place)
    blocks.py             # Block Kit formatting, markdown→Slack conversion
    mention.py            # @mention parsing
  ca_client.py            # CA API gRPC client wrapper
  config.py               # AGENT_CONFIGS — single source of truth for all agents
  mcp_server.py           # FastMCP server for Google Workspace tools
  charts/renderer.py      # Vega-Lite → PNG via vl-convert
scripts/
  run_slack.py            # Entry point
  test_cli.py             # Interactive CLI test (no Slack needed)
  provision_agents.py     # Create/update CA agents via API
```

## Adding a New Dataset Agent

1. Add an `AgentConfig` block to `src/config.py` `AGENT_CONFIGS` dict
2. Add `CA_AGENT_<NAME>=<agent-id>` to `.env`
3. Restart — no other code changes needed

The agent, tool function, and root agent registration all generate automatically.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | Yes | `xoxb-...` Bot User OAuth Token |
| `SLACK_APP_TOKEN` | Yes | `xapp-...` App-Level Token (Socket Mode) |
| `GCP_PROJECT_ID` | Yes | GCP project for CA API |
| `GCP_LOCATION` | Yes | `global` (CA API) |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | `true` |
| `GOOGLE_CLOUD_PROJECT` | Yes | Same as GCP_PROJECT_ID |
| `GOOGLE_CLOUD_LOCATION` | Yes | `global` (Vertex AI model endpoint) |
| `ROUTER_MODEL` | Yes | Gemini model for routing (e.g. `gemini-3.1-flash-lite-preview`) |
| `AGENT_MODEL` | Yes | Gemini model for sub-agents |
| `CA_AGENT_THELOOK` | No | CA agent ID for TheLook dataset |
| `CA_AGENT_STACKOVERFLOW` | No | CA agent ID for Stack Overflow |
| `CA_AGENT_NCAA` | No | CA agent ID for NCAA Basketball |
| `CA_AGENT_CENSUS` | No | CA agent ID for US Census |
| `CA_AGENT_GA4` | No | CA agent ID for GA4 E-Commerce |
| `CA_AGENT_GA360` | No | CA agent ID for Google Analytics 360 |
| `SHARED_DRIVE_ID` | No | Optional: Shared Drive ID for Google Workspace exports |

## Slack Thread Flow

1. User `@mentions` bot → `handle_mention` fires
2. "Thinking..." placeholder posted
3. ADK routing decision (~2s) → placeholder updated to "Routing to X..."
4. CA API call (~30-90s) → progress milestones edit the same message
5. Answer posted (replaces placeholder) → reasoning → SQL → chart (separate thread messages)
6. Follow-up messages in same thread → `handle_message` → same ADK session → CA conversation reused

## GCP Auth

Uses Application Default Credentials. Locally: `gcloud auth application-default login`. On Cloud Run: attach a service account with all four required roles — `roles/geminidataanalytics.dataAgentUser`, `roles/cloudaicompanion.user`, `roles/aiplatform.user`, and `roles/bigquery.jobUser`.

`roles/bigquery.jobUser` is required because the CA API executes BigQuery queries using the caller's credentials — without it every CA query fails with a permission error even on public datasets.

## Cloud Run Lifecycle

```bash
# Deploy
gcloud builds submit --tag gcr.io/PROJECT/ca-demo
gcloud run deploy ca-demo --image gcr.io/PROJECT/ca-demo --region us-central1 \
  --min-instances 1 --no-cpu-throttling ...

# Tear down (stops billing)
gcloud run services delete ca-demo --region us-central1 --project PROJECT --quiet
```

`--min-instances 1` and `--no-cpu-throttling` are both required — Socket Mode is a persistent WebSocket and Cloud Run will drop it otherwise. `GRPC_DNS_RESOLVER=native` must be set in env vars or gRPC DNS resolution hangs silently.

## Running Locally

```bash
uv sync
uv run python scripts/run_slack.py       # Slack bot
uv run python scripts/test_cli.py        # CLI test (no Slack)
```

## Known Quirks

- CA API gRPC stream events are batched — progress milestones (Planning, SQL, etc.) may all arrive at once rather than individually, so the Slack progress message may jump from "Routing..." directly to "Formatting answer".
- `gemini-3.1-flash-lite-preview` requires `GOOGLE_CLOUD_LOCATION=global` (not `us-central1`).
- CA API chart specs are wrapped: `{"result": {"vega_config": {<actual Vega-Lite spec>}}}`. `ca_client.py` unwraps this before returning.
