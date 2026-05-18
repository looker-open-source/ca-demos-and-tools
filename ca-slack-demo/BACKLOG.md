# Backlog

Items planned but not yet implemented, in rough priority order.

---

## 1. Cloud Run deployment + service account setup

The bot runs locally today. Before handing to PS teams it needs to run on Cloud Run with proper GCP auth.

**Work needed:**
- Create a GCP service account with the right IAM roles (see README)
- Store Slack tokens in Secret Manager (not plaintext env vars)
- Validate the Dockerfile build + deploy end-to-end
- Document the full deploy flow for PS

**Blocking:** nothing — next up.

---

## 2. Session persistence

`InMemorySessionService` loses all thread context on restart. A Cloud Run redeploy silently breaks multi-turn conversations — users get no error, the bot just forgets the thread.

**Fix:** Swap `InMemorySessionService` for a Firestore-backed session store. ADK supports custom session services.

**Why deferred:** Not a blocker for demo/pilot; becomes critical for any sustained deployment.

---

## 3. Microsoft Teams bot

A Teams version mirroring the Slack bot. Architecture is well understood — see notes below.

**Shared verbatim from this repo:** `ca_client.py`, `config.py`, `agents/root.py`, `tools/ca_tools.py`, `charts/renderer.py`

**Rewrite for Teams:** webhook handler (replaces Slack Bolt), Adaptive Cards (replaces Block Kit), activity-update progress tracker (replaces `progress.py`), `<at>` mention parser.

**Key harder things vs Slack:**
- **Live progress updates** — Teams rate-limits at ~1 req/s per conversation. Must send the full card on every update (vs Slack's simple text edit). Safe cadence: every 5–10s.
- **Chart images** — must be a publicly accessible HTTPS URL. Base64 breaks desktop/web Teams clients. Requires hosted storage (GCS signed URL or Azure Blob).
- **No Socket Mode** — needs a public inbound HTTPS endpoint (Cloud Run with `--allow-unauthenticated` on the bot path, or Azure Container Apps).
- **Multi-turn keying** — use `conversationId` as session key (≈ Slack `thread_ts`). `replyToId` is unreliable for threading.
- **Auth bridge** — bot runs on GCP/Azure but calls CA API (GCP). Options: service account key as env var secret (simple) or Workload Identity Federation (secure, more setup).

**SDK note:** `botbuilder-python` reached end-of-life January 2026. Use **Microsoft 365 Agents SDK** for new projects.

**First decisions before starting:**
1. Cloud Run vs Azure Container Apps (Cloud Run simpler for GCP auth)
2. Chart hosting: GCS signed URLs vs Azure Blob
3. M365 Agents SDK vs direct Bot Framework REST

---

## 4. Per-user auth (domain-wide delegation)

For deployments where different users should see different data — row-level security, column-level access — the bot can call the CA API as each Slack user's own GCP identity. CA agent IAM and BigQuery RBAC then apply per-user rather than per-bot.

**What's needed:**
- Enable domain-wide delegation on the service account (Google Workspace admin required)
- Map Slack user → Google email (Slack profile API or directory lookup)
- Impersonate user identity on each CA call using `google.auth.impersonated_credentials`

**Constraint:** Slack users must have Google Workspace identities in the same org as the GCP project. Personal Gmail accounts won't work.

**Why deferred:** Shared mode is the right starting point and covers most demo/pilot use cases. Per-user mode adds meaningful complexity (Workspace admin, identity mapping) and is only needed when datasets have different access levels per person.

---

## 5. Documentation and code polish

The project was scaffolded quickly with AI assistance. Before handing to PS teams, do a pass to remove the most obvious tells:

- Remove or rephrase overly structured lists where prose flows better
- Audit inline comments for unnecessary narration ("This ensures that...", "Note that...")
- Verify docstrings say something non-obvious — delete ones that just restate the function name
- README: read it aloud — anything that sounds like a spec document rather than a technical guide should be rewritten

**Why:** PS and CE teams will share this with prospects. It should read as a polished reference implementation.

---

## 6. Observability / structured logging

No instrumentation today. PS teams fly blind in production.

**Minimum viable:** structured JSON logs to Cloud Logging with fields: `agent_name`, `latency_ms`, `question_length`, `had_chart`, `error_code`. One log line per request.

**Nice to have:** Cloud Monitoring dashboard — requests/min, p50/p95 latency by agent, error rate.

---

## 7. User feedback (👍 / 👎)

Add reaction-based quality signal. When the bot posts an answer, it adds a 👍 and 👎 reaction to its own message. Users click to signal quality. Bot logs the reaction + agent + question.

Builds trust with business users and gives the team signal on what's working.

---

## 8. Suggested follow-up questions

CA already streams `text_type=0` events with suggested next questions. Currently ignored.

Planned as a CA product feature — skip for now, revisit when CA exposes this via a stable API surface.
