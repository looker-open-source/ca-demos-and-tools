<!--
Copyright 2026 Google LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

     http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# Prism

**This is not an officially supported Google product. This project is not
eligible for the
[Google Open Source Software Vulnerability Rewards Program](https://bughunters.google.com/open-source-security).**

This directory holds all of Prism, a platform for monitoring and evaluating AI
agents: the database and services, the Dash UI, and the background worker pool
that executes evaluations.

## Project Overview

Prism runs test suites against Conversational Analytics agents, captures the
execution trace of each question, and scores the answers with assertions. It is
a standalone Python package: PostgreSQL for state, a Dash UI, and a worker pool
that runs one evaluation at a time. Completed runs also stream into
day-partitioned BigQuery tables, which is where long-term analysis happens.

## Quick Start

### 1. Prerequisites

-   **uv** (Required: https://astral.sh/uv)
-   Python 3.13 or newer, which **uv** will fetch for you
-   Docker (Recommended for local database)
-   PostgreSQL (Optional, if not using Docker)
-   Google Cloud SDK, for Application Default Credentials
-   A Google Cloud project with the Gemini Data Analytics API
    (`geminidataanalytics.googleapis.com`) and the Vertex AI API
    (`aiplatform.googleapis.com`) enabled. Add the BigQuery API
    (`bigquery.googleapis.com`) if your agents read BigQuery tables.

Prism works on Conversational Analytics (Gemini Data Analytics) agents. There
are two ways in: `/agents/onboard/new` creates a new agent in your project, and
`/agents/onboard/existing` discovers agents that are already there and onboards
them. Both need a project to work in, which is what `PRISM_GDA_PROJECTS` names
below. Neither page offers anything until you set it.

### 2. Setup

uv synchronizes the environment on every run, so there is no manual installation
step for the Python environment.

> [!IMPORTANT]
>
> This project requires **uv** to be installed on your system. If you don't have
> it, install it first: https://astral.sh/uv

#### a. Configuration file

Start here, before the database script. `.env.example` is the annotated
reference for every variable Prism reads:

```bash
cp .env.example .env
```

Fill in `PRISM_GDA_PROJECTS` and `PRISM_GENAI_CLIENT_PROJECT`. The database
script below rewrites `DATABASE_URL` and `TEST_DATABASE_URL` in place and leaves
the rest of the file alone, so anything you put here survives it.

> [!WARNING]
>
> If `PRISM_GDA_PROJECTS` is unset or empty, `settings.gcp_gda_projects` is an
> empty list. The GCP Project dropdown on `/agents/onboard/new` and
> `/agents/onboard/existing` then renders with no options, no error and no hint,
> and you cannot add an agent. The app otherwise starts and looks healthy. This
> is the setting newcomers get stuck on.

#### b. Credentials

Prism authenticates to Google Cloud with Application Default Credentials:

```bash
gcloud auth application-default login
```

#### c. Database

```bash
./scripts/setup_postgres.sh
```

That spins up a Dockerized PostgreSQL container (`postgres_local`) bound to
`127.0.0.1`, creates the `prism` and `prism_test` databases, writes the two
database URLs into `.env` (backing the old file up to `.env.bak`), and runs
migrations. `DB_PORT` moves the host-side port, which defaults to `5432`.

The data lives in a named volume, `postgres_local_data`, not in the container. A
few conditions make the script remove and recreate `postgres_local`, a changed
`DB_PORT` among them, and the volume is what carries the databases across. A
container created before the volume existed does not have one, so the script
says what it is about to lose and asks before it removes that.

> [!IMPORTANT]
>
> On the Docker path, with no `DB_PASS` in the environment the script falls back
> to `CHANGEME-local-only`. That is a placeholder, not a password, and it is the
> same in every checkout. It is tolerable only because the container is bound to
> loopback. Set `DB_PASS` to a value of your own before you run the script, and
> never carry the placeholder into anything a network can reach.
>
> Under `--no-docker` there is no fallback. `DB_PASS` defaults to empty, the
> script skips the `ALTER ROLE ... WITH PASSWORD`, and the role is created with
> no password at all. The URLs it writes into `.env` carry an empty password and
> work only because a local PostgreSQL normally trusts local connections. Set
> `DB_PASS` on that path too if you want the role to have one.

The flags:

-   `--no-docker` uses a PostgreSQL installed on the host instead. On Linux that
    path runs its superuser SQL as `sudo -u postgres psql`, so it needs a
    `postgres` system user and the right to sudo to it. On macOS it connects as
    you, over the `/tmp` socket.
-   `--sudo` runs the docker commands under `sudo`, for a daemon your user
    cannot reach.
-   `--nuke` drops the `prism` and `prism_test` databases first. It asks before
    it does, and there is no flag to skip the question.

### 3. Running the Application

#### Development Mode

The built-in Flask development server is the one to use for active development.
Use the convenience script or `uv run` directly:

```bash
./scripts/run_app.sh
```

Or:

```bash
uv run python src/prism/ui/app.py
```

It binds `127.0.0.1:8080`. `PRISM_HOST` and `PORT` change that.
`PRISM_DEBUG=true` turns on the Werkzeug debugger and the reloader. The debugger
runs arbitrary Python for anyone who can reach the port, so leave it off
anywhere but your own machine.

#### Production Mode (Gunicorn)

```bash
./scripts/run_prod.sh
```

Gunicorn, one worker, eight threads, bound to `0.0.0.0:${PORT:-8080}` with
`--timeout ${TIMEOUT:-3600}`. One worker, because importing `prism.prod` starts
a background worker pool and a second gunicorn worker would mean a second pool
on the same run queue.

The `Dockerfile` runs the same command, out of the virtualenv it built rather
than through `uv`, and with the timeout fixed at 3600 instead of read from
`TIMEOUT`:

```bash
exec /app/.venv/bin/gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 8 --timeout 3600 prism.prod:app
```

It goes through `/bin/sh -c` so `$PORT` expands, because Cloud Run injects the
port and only defaults it to 8080. `exec` keeps gunicorn as PID 1, so it still
receives the SIGTERM.

#### The run queue

The worker pool runs one evaluation at a time, for the whole application. It
takes the oldest `PENDING` run, marks it `RUNNING`, and starts up to that run's
`concurrency` trials in parallel. Every other run waits. Nothing is promoted
while a run is `RUNNING` or `PAUSED`, so pausing a run holds the slot rather
than handing it on, and the runs behind it stay `PENDING` until it is resumed or
cancelled. The UI shows no queue position, so a run that is third in line looks
the same as one that is about to start.

## Configuration

Prism reads its configuration from environment variables, and loads a `.env`
file from the project root if there is one. **`.env.example` is the reference
for what goes in `.env`.** It lists each variable with a note on what reads it,
including Application Default Credentials, `DB_IP_TYPE`, `E2E_DATABASE_URL` and
`PRISM_CASSETTE_DIR`.

`./scripts/setup_postgres.sh` is the exception. It never reads `.env`, so
`DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASS` and `DB_NAME` have to be in the shell
environment to reach it. It writes `DATABASE_URL` and `TEST_DATABASE_URL` back
into `.env` when it is done.

### Database Configuration

`final_database_url` takes the first of these it can:
`INSTANCE_CONNECTION_NAME`, then `DATABASE_URL`, then a local fallback.

-   `INSTANCE_CONNECTION_NAME`: a Cloud SQL instance, as
    `project:region:instance`. When it is set the Cloud SQL Python Connector
    dials the instance itself and `DATABASE_URL` is ignored.
-   `DATABASE_URL`: the primary database connection URI. Defaults to
    `postgresql://localhost/prism`.
-   `DB_USER` (default `postgres`), `DB_PASS` (default empty) and `DB_NAME`
    (default `prism`): the credentials the connector dials with. Only read on
    the `INSTANCE_CONNECTION_NAME` path; a `DATABASE_URL` carries its own. The
    `DB_USER` default is the Cloud SQL superuser, so set it to a user created
    for Prism instead of taking the default.
-   `DB_USER` has two different defaults in this project, and they do not agree.
    The application defaults it to `postgres`, in `src/prism/server/config.py`.
    `./scripts/setup_postgres.sh` defaults the same variable to your login name,
    `$(whoami)`, and creates a role with that name. Export `DB_USER` before you
    run the script if you want one value everywhere.
-   `DB_IP_TYPE`: `PUBLIC` (default) or `PRIVATE`, passed to the connector as
    `ip_type`. Use `PRIVATE` for an instance with no public IP.
-   `TEST_DATABASE_URL`: the database the tests run against.
    `./scripts/run_tests.sh` requires it and points `DATABASE_URL` at it, so a
    test run cannot reach the database above. A bare `pytest` falls back to
    `postgresql:///prism_test?host=/var/run/postgresql`.
-   `E2E_DATABASE_URL`: names the browser tier's database yourself. Only
    `./scripts/run_e2e.sh` reads it, and without it that script derives a
    `<name>_e2e` database from `TEST_DATABASE_URL`. The name has to end in
    `e2e`, optionally after a `_` or a `-`, or `tests/db_guard.py` refuses to
    run.
-   `DB_HOST` and `DB_PORT` (default `5432`): the host and host-side port
    `./scripts/setup_postgres.sh` publishes the container on. That script is
    their only reader, and it takes them from the shell, not from `.env`.

### Server Configuration

-   `PRISM_HOST` (default `127.0.0.1`) and `PORT` (default `8080`): where the
    development server binds, read in `src/prism/ui/app.py`.
    `./scripts/run_prod.sh` reads `PORT` too, and binds gunicorn to
    `0.0.0.0:$PORT`.
-   `TIMEOUT` (default `3600`): gunicorn's `--timeout`, in seconds.
    `./scripts/run_prod.sh` is its only reader.

`./scripts/run_prod.sh` and `./scripts/run_app.sh` both read `.env` through
`scripts/dotenv.sh`, the same helper `./scripts/run_tests.sh` and
`./scripts/run_e2e.sh` use. It parses the file rather than sourcing it, so
nothing in a value is expanded, and a variable already exported wins over the
file. That last part matches what python-dotenv does for the application, so
`PORT=9000 ./scripts/run_prod.sh` behaves the way it reads.

-   `PRISM_DEBUG` (default `false`): the Werkzeug debugger and reloader in the
    development server. Not a setting on `Settings`, because `prism.ui` cannot
    import `prism.server`.

### GCP Project Configuration

Prism interacts with GCP services for agent execution and LLM-based evaluation:

-   `PRISM_GDA_PROJECTS`: comma-separated GCP projects containing GDA agents,
    for example `project-1,project-2`.
-   `PRISM_GDA_LOCATIONS`: comma-separated GCP locations to scan for agents.
    Defaults to `global,us,eu`.
-   `PRISM_GENAI_CLIENT_PROJECT`: the GCP project the Gen AI evaluation calls
    bill to, for example `my-genai-project`.
-   `PRISM_GENAI_CLIENT_LOCATION`: the GCP location for those calls. Defaults to
    `us-central1`.

`PRISM_GDA_PROJECTS` is the one with no default and no error. See the warning
under Quick Start.

### Agent locations

An agent's location is stored on its row, and it is what picks the endpoint for
every call to that agent. `global` uses the default endpoint. Every other
location, multi-region and region alike, uses
`geminidataanalytics.<location>.rep.googleapis.com`. Discovery queries all of
`PRISM_GDA_LOCATIONS` concurrently, which is why there is no region picker in
the UI. Chat, context snapshots, agent updates and the spawned evaluation
workers all read the location back off the row, so a worker subprocess reaches
the same endpoint the UI did.

### BigQuery Evaluation Export Configuration
Prism supports streaming completed evaluation results to BigQuery
(OLAP dual-store):

| Variable | Description | Default | Example |
| :--- | :--- | :--- | :--- |
| `BIGQUERY_EXPORT_ENABLED` | Enables asynchronous streaming of evaluation results to BigQuery. | `false` | `true` |
| `BIGQUERY_EXPORT_PROJECT` | Target GCP Project ID where BigQuery dataset is located. | `None` | `my-gcp-project` |
| `BIGQUERY_EXPORT_DATASET` | Target BigQuery Dataset ID. | `prism_evals` | `prism_evals` |
| `BIGQUERY_EXPORT_LOCATION` | Target BigQuery Location for dataset creation. | `US` | `US` |

## BigQuery Evaluation Persistence (OLAP Dual-Store)

PostgreSQL stays the operational store. It holds application state, worker
locks, trial state transitions and everything the UI reads. BigQuery is a sink
for completed runs, so you can query history in SQL or point a Looker dashboard
at it.

### How It Works

-   **Asynchronous streaming**: When the last trial in a run completes, the
    worker hands the run to a background thread
    (`BigQueryExporter.export_run_async()`) that streams the whole hierarchy
    into BigQuery.
-   **Partitioned tables**, day-partitioned by execution date:
    -   `prism_eval_runs`: run metadata, agent context snapshot, aggregate
        accuracy, duration and status.
    -   `prism_eval_trials`: questions, model responses, scores, duration, TTFR,
        retry counts and error messages.
    -   `prism_eval_assertion_results`: per-assertion outcomes, scores, weights
        and reasoning.
    -   `prism_eval_traces`: execution trace steps, tool timestamps and
        serialized JSON event payloads.
-   **Idempotency**: `is_run_exported(run_id)` checks BigQuery before exporting,
    and an in-flight lock keeps two threads from exporting the same run. Rows
    also carry deterministic ids (`run-{id}`, `trial-{id}`, `ar-{id}`,
    `trace-{id}-{step}`), so a retry inside BigQuery's streaming deduplication
    window collapses into the first insert.
-   **Partial failures**: `insert_rows_json` returns per-row errors instead of
    raising, and keeps the rows it accepted. The run row is written whatever the
    other three tables did, so the rows that landed can be joined to it, and the
    failure is recorded against the run. Withholding the run row was tried and
    orphaned the children: nothing else records the export state, so the retry
    button stayed live and every press appended another full copy. Deleting the
    old rows first is not an option, because rows in the streaming buffer cannot
    be removed by DML for some time after they land.
-   **Sync badge**: the evaluation detail page shows `BQ: Synced`, `BQ:
    Syncing`, `BQ: Pending`, `BQ: Failed`, `BQ: Not Synced`, `BQ: Disabled` or
    `BQ: Unknown`, and offers a Sync to BigQuery button whenever a completed
    evaluation is not in BigQuery yet.

`ensure_dataset_and_tables` creates missing tables with `exists_ok=True`, which
does not alter one that is already there. A dataset deployed before
`scored_trials` was added to `prism_eval_runs` rejects every run row with "no
such field" until you add the column once, by hand:

```sql
ALTER TABLE `<project>.<dataset>.prism_eval_runs` ADD COLUMN scored_trials INT64;
```

`scored_trials` is the population `accuracy` was averaged over. `total_trials`
counts every trial in the run, including the ones with no weighted assertion,
which score nothing and are left out of the average.

### CLI Backfill Utility
Export historical evaluation runs from the command line:

```bash
# Export a specific run:
uv run python scripts/export_to_bigquery.py --run-id 7 --project "my-gcp-project"

# Export all runs for a specific agent:
uv run python scripts/export_to_bigquery.py --agent-id 1 --project "my-gcp-project"

# Backfill all completed runs that are missing in BigQuery:
uv run python scripts/export_to_bigquery.py --all --project "my-gcp-project"

# Force re-export:
uv run python scripts/export_to_bigquery.py --all --project "my-gcp-project" --force
```

`--force` skips the already-exported check. It appends, it does not replace, so
re-exporting a run after BigQuery's streaming deduplication window has passed
leaves a second copy of every row.

`--dataset` and `--location` override the destination, and default to
`BIGQUERY_EXPORT_DATASET` (`prism_evals`) and `BIGQUERY_EXPORT_LOCATION` (`US`)
respectively. `--project` defaults to `BIGQUERY_EXPORT_PROJECT` the same way, so
all three can come from `.env` instead of the command line.

```bash
# Export one run into a dataset other than the configured default:
uv run python scripts/export_to_bigquery.py --run-id 7 \
  --project "my-gcp-project" --dataset prism_evals_archive --location EU
```

### Agent Authentication
Prism supports various agent types, each requiring specific authentication:

-   **Looker Agents**: Require a Looker Instance URI, Client ID, and Client
    Secret.
-   **BigQuery Agents**: Require the IAM roles under Deployment below.
    Additionally, the service account must have access to the specific datasets
    used by the agent.

## Deployment

> [!WARNING]
>
> **Prism has no authentication or authorization of its own.** Anyone who can
> reach the service can read every agent, suite and run, edit agent config, and
> start evaluations that spend real money against your Gemini Data Analytics and
> Vertex AI quota. Put an authenticating layer in front of it: on Cloud Run,
> deploy with `--no-allow-unauthenticated`, or use Identity-Aware Proxy.
>
> Looker client secrets are stored in the database in clear text, so restrict
> access to the database too. Nothing in Prism constrains what that credential
> can do, so give it a Looker API user scoped to read-only on the models it
> needs.

Importing `prism.prod` runs `alembic upgrade head`, but the migrations are not
packaged. `alembic/` sits outside `src/`, and `[tool.setuptools.packages.find]`
only looks under `src`, so neither the wheel nor the sdist carries `alembic.ini`
or `alembic/versions`. Deploy from a source checkout or from the container
image, both of which have the migration tree next to the code. An install from
the built wheel alone does not.

### 1. Docker

Prism includes a `Dockerfile` for containerized deployments. To build:

```bash
docker build -t prism-app .
```

Running it with `--env-file .env` and nothing else will not start. The `.env`
that `scripts/setup_postgres.sh` writes points `DATABASE_URL` at
`localhost:5432`, and inside the container `localhost` is the container.
`src/prism/prod.py` fails its connection canary and raises, so the container
exits before it serves anything. Put the two containers on a shared network and
address the database by container name:

```bash
docker network create prism-net
docker network connect prism-net postgres_local

docker run -p 8080:8080 \
  --network prism-net \
  --user "$(id -u)" \
  --env-file .env \
  -e DATABASE_URL="postgresql://$(whoami):YOUR_DB_PASS@postgres_local:5432/prism" \
  -v "$HOME/.config/gcloud/application_default_credentials.json:/adc.json:ro" \
  -e GOOGLE_APPLICATION_CREDENTIALS=/adc.json \
  prism-app
```

The user and password are the ones `setup_postgres.sh` used: your login name and
whatever you put in `DB_PASS`, or the `CHANGEME-local-only` placeholder if you
left it unset. Docker gives `-e` precedence over `--env-file`, so the
`DATABASE_URL` in the file is ignored. The mount is Application Default
Credentials: the container has no `gcloud`, so without it every call to Gemini
Data Analytics and Vertex AI fails. `GOOGLE_APPLICATION_CREDENTIALS` is the only
place that file is needed; locally and on Cloud Run, leave it unset.

`--user "$(id -u)"` is there because the image runs as a non-root user and your
ADC file is mode `600` and owned by you, so the container cannot read the mount
otherwise. The app writes nothing to disk in normal use, so running under a
different uid is safe. The exception is `PRISM_AGENT_BACKEND=record`, which
writes cassettes into `PRISM_CASSETTE_DIR`; that uid has to be able to write
there. Drop the flag if you are not mounting credentials in.

### 2. Cloud Run & Cloud SQL

For production deployments on Google Cloud, use **Cloud Run** connected to
**Cloud SQL (PostgreSQL)**.

#### IAM Roles

Two identities are involved here, and they need different things. Keep them
apart.

The Cloud Run **runtime** service account is the one the running app calls
Google Cloud with. Give it only:

-   `Cloud SQL Client`
-   `Vertex AI User`, for the Gen AI evaluation calls
-   `Gemini Data Analytics Data Agent Owner` and `Gemini Data Analytics Data
    Agent Creator`, which the two onboarding pages need. `Data Agent User` is
    enough if you only ever evaluate agents somebody else manages.
-   `Secret Manager Secret Accessor`, granted on the individual secrets it reads
    rather than on the project
-   `BigQuery User` and `BigQuery Data Viewer` if your agents read BigQuery,
    granted on the datasets they read

The identity that **builds and deploys** the image is separate, and it is the
one that needs `Cloud Build Service Account`. That is the Cloud Build service
account if you build with `gcloud builds submit` or `gcloud run deploy
--source`. Do not grant it to the runtime account: it carries permission to
start builds, write to Artifact Registry and act as other service accounts, none
of which the running service does.

> [!WARNING]
>
> **Cloud Run CPU throttling and memory.** Prism uses Python `multiprocessing`
> for asynchronous evaluations inside of a background `WorkerProcessManager`.
> Because of this, it is required to deploy your Cloud Run service with
> **`--no-cpu-throttling`** (so your background evaluators don't crash when HTTP
> requests finish) and at least **`--memory=1024Mi`** (to handle the duplicated
> memory footprint of subprocesses).

#### Deployment Checklist:

1.  **Build and Push**: Push your image to Artifact Registry.
2.  **Database**: Create a Cloud SQL instance, and a database user for Prism on
    it. Use that user, not the instance's `postgres` superuser: the app only
    ever reads and writes its own schema.
3.  **Secrets**: Store that user's password in Secret Manager.
4.  **Deploy**: Use `gcloud run deploy` with the following requirements:
    -   Include the `--no-allow-unauthenticated` flag, or put Identity-Aware
        Proxy in front of the service.
    -   Include the `--no-cpu-throttling` flag.
    -   Include `--max-instances=1`.
    -   Add the Cloud SQL instance connection.
    -   Set the **`DATABASE_URL`** or **`INSTANCE_CONNECTION_NAME`** environment
        variable. See Database Configuration above for
        `INSTANCE_CONNECTION_NAME`, `DB_NAME`, `DB_USER`, `DB_PASS` and
        `DB_IP_TYPE`.
    -   Set `PRISM_GDA_PROJECTS` and `PRISM_GENAI_CLIENT_PROJECT`, or the
        deployed app has no projects to offer.

Example deployment command:

```bash
gcloud run deploy prism-app \
  --image ARTIFACT_REGISTRY_IMAGE_URL \
  --region us-central1 \
  --no-allow-unauthenticated \
  --no-cpu-throttling \
  --memory=1024Mi \
  --max-instances=1 \
  --add-cloudsql-instances YOUR_INSTANCE_CONNECTION_NAME \
  --set-env-vars "INSTANCE_CONNECTION_NAME=YOUR_INSTANCE_CONNECTION_NAME,DB_NAME=prism,DB_USER=YOUR_DB_USER,PRISM_GDA_PROJECTS=YOUR_PROJECT,PRISM_GENAI_CLIENT_PROJECT=YOUR_PROJECT" \
  --set-secrets "DB_PASS=YOUR_SECRET_NAME:latest"
```

`--no-allow-unauthenticated` is the flag the warning at the top of this section
asks for. Prism has no authentication of its own, so leaving it off publishes
every agent, suite and run, and the ability to spend money, to the internet.

`--max-instances=1` is what makes `--workers 1` mean anything: the worker pool
starts on import, so each additional instance would bring up another pool on the
same run queue and the serial ordering would be gone.

If the deployed app cannot reach its database,
`scripts/check_cloud_sql_connection.py` opens one Cloud SQL connection with the
same variables the app uses and reports what happened, which tells a bad
instance name or password apart from a fault inside the app. Run it from a
checkout, with the deployment's environment:

```bash
INSTANCE_CONNECTION_NAME=... DB_USER=... DB_PASS=... DB_NAME=prism \
  uv run python scripts/check_cloud_sql_connection.py
```

It is not in the container image. `.dockerignore` is an allowlist and does not
include it.

## Testing
Run the test suite using the provided script:

```bash
./scripts/run_tests.sh
```

It loads `.env`, requires `TEST_DATABASE_URL`, exports `DATABASE_URL` with the
same value and runs pytest. Any extra arguments go straight through. The two
variables have to agree because trial execution happens in a spawned subprocess,
which re-reads `DATABASE_URL` at import and never sees the pytest fixtures.

`tests/db_guard.py` is what enforces that, from the import of
`tests/conftest.py`. It does not fail a bare `pytest`. It falls back to
`postgresql:///prism_test?host=/var/run/postgresql` when `TEST_DATABASE_URL` is
unset, and raises `UnsafeTestDatabaseError` in three cases: the database name
does not end in `test` or `e2e`, the host is not local, or an exported
`DATABASE_URL` disagrees with the test URL. Having passed, it rebinds the
process-global engine and sessionmaker onto the test database and rewrites
`DATABASE_URL` so spawned children inherit it.

The run covers everything under `tests/` except the `e2e` and `live` markers,
which `pyproject.toml` excludes in `addopts`:

-   `tests/services` and `tests/repositories`: the server layer against the test
    database.
-   `tests/clients`: the Gemini Data Analytics and Gen AI clients, with their
    transports mocked. No cassettes and no network.
-   `tests/ui`: Dash callback dispatch, driven over HTTP through a Flask test
    client in-process. No browser and no second server.
-   `tests/integration`: a run end to end through `ExecutionService`, with the
    agent clients mocked.
-   The migration and import-boundary tests described under Working on Prism.

### Recorded Agent Responses

Calls to the Gemini Data Analytics and Gen AI APIs go through a cassette layer
(`src/prism/server/clients/recording.py`), so tests can exercise real response
shapes without the network. `PRISM_AGENT_BACKEND` picks the mode:

-   `live` is the default. Calls go to the real API.
-   `record` calls the real API and writes each response to a cassette.
-   `replay` serves calls from cassettes. A miss raises, it does not fall back
    to the network, so a new code path can't pass by going live.

Cassettes live in `tests/cassettes`, or wherever `PRISM_CASSETTE_DIR` points.
They hold real API responses, so check what is in one before committing it. The
directory is in `.gitignore` by default.

### Browser End-to-End Suite

```bash
./scripts/run_e2e.sh
```

The specs live in `tests/e2e`, one file per area, and drive Chromium against a
real gunicorn server. The tier runs offline and free: the agent responses are
replayed from cassettes the fixtures build at run time out of
`tests/e2e/traces.py`, so nothing reaches Google Cloud and no credentials are
needed.

The suite needs its own database, because the unit suite drops every table
between tests while this one keeps a server running. The script derives a
`<name>_e2e` database from `TEST_DATABASE_URL` and creates it if it isn't there.

playwright and its pytest plugins are in the `e2e` dependency group, not in
`dev`, so `./scripts/run_tests.sh` never installs them. The first run of
`run_e2e.sh` downloads a Chromium build into `~/.cache/ms-playwright`.

## Working on Prism

### The layering rule

`prism.common.schemas` is the leaf. It holds the pydantic models and imports
nothing else from `prism`. `prism.server` owns the database, the external
clients and the services. `prism.client` is the in-process facade over those
services. `prism.ui` is the Dash application, and it may import only
`prism.client` and `prism.common.schemas`. **It must never import
`prism.server`.**

Three tests enforce this and all three run in the default suite:
`tests/test_ui_isolation.py`, `tests/test_client_isolation.py` and
`tests/test_common_isolation.py`. Each parses every file in its package with
`ast` and fails on a forbidden import. It is the first rule a new contributor
runs into. When the UI needs something only the server has, add a method to the
matching client under `src/prism/client/` and call that.

### Adding a UI callback

Callbacks go in `src/prism/ui/callbacks/<area>_callbacks.py`, and they are
registered by being imported in `src/prism/ui/callbacks/__init__.py`. The import
is the registration. `register_all_callbacks()` is a no-op that exists to make
the dependency visible, so a new file nothing imports there never runs.

Component ids are constants, not string literals. The shared ones are in
`src/prism/ui/ids.py`; page-specific ones sit next to the page, for example
`src/prism/ui/pages/agent_ids.py`. Wrap the callback in `typed_callback` from
`src/prism/ui/utils.py`, which accepts `(id, property)` tuples as well as Dash
dependency objects.

### Adding a migration

Migrations live in `alembic/versions`. To add one:

```bash
uv run alembic revision --autogenerate -m "what it does"
```

Autogenerate diffs the models against the database, so point it at one that is
already at head. `alembic/env.py` takes its URL from
`settings.final_database_url`, so `DATABASE_URL` selects the target. Read the
generated file before committing it: autogenerate misses some changes, and it
proposes dropping the table of any model that is not registered on `Base`.

`tests/test_migrations.py` runs in the default suite and holds the chain to
three things. The chain has exactly one head, every file in `alembic/versions/`
is reachable from it, and a database built by running the chain from empty
matches the models, server defaults included.

### Migrations that discard data

Seven revisions in the chain drop data rather than convert it. Running the chain
from empty is unaffected, but upgrading a database that already holds results is
not, so take a dump first. In chain order:

`0d306800fe55` drops `examples.asserts`, the JSON column assertions lived in
before they had a table. There is no data migration, and the downgrade re-adds
the column empty.

`7cdc4df909dc` moved assertions out of JSON columns and into their own tables.
It creates `assertions`, `assertion_snapshots`, `assertion_results` and
`suggested_assertions` empty, then drops `example_snapshots.asserts` and
`trials.assertion_results`, so nothing written before it carries across. Suites
come out with no assertions on their examples, and past runs keep their trials
with no results behind them.

`e8fe334fbbf5` drops `runs.passed_examples`, `runs.total_examples` and
`runs.failed_examples`. The counts are derived from the trials now. The
downgrade re-adds the three columns with a server default of `0`, so an old
database that goes back comes back with every count zeroed.

`827a40689071` drops the datasource columns from `test_suites` and
`test_suite_snapshots`, and `trials.score`. Trial scores are computed from the
assertion results now, so the column was redundant, but the stored values are
not recoverable.

`ed2ab69fa339` drops `trials.service_duration_ms`.

`8c6080c6545f` drops `agents.env`. The downgrade re-adds the column with every
agent set to `PROD`, which is where `499b6db4e31b` had already put the published
ones, so an agent that was anything else does not come back.

`87d5db0c5bc2` rewrites `agents.location` in place: an empty or NULL location
becomes `global`, and the rest are lowercased and trimmed. The downgrade drops
the server default and leaves the rewritten values, so an agent stored as
`US-Central1` comes back as `us-central1`. Nothing reads location
case-sensitively, so this matters only if you were relying on the stored casing.

## Contributing

See [`../CONTRIBUTING.md`](../CONTRIBUTING.md) at the root of the repository
this directory lives in. It covers the Contributor License Agreement and the
review process.

## License

Apache License 2.0. The full text is in the `LICENSE` file, and every source
file carries the header. Two sets of files do not. The three prompt templates
under `src/prism/server/services/prompts/` are plain text with no comment
syntax, and each one is read whole and sent to the model as the prompt, so a
header in them would be read as part of the instructions.
`src/prism/ui/assets/style.css` carries the SPDX short form,
`SPDX-License-Identifier: Apache-2.0`, in place of the full header.
