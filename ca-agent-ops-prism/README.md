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

# Prism (Core Backend)

This directory contains the Core Backend for the Prism application, a platform
for monitoring and evaluating AI Agents.

## Project Overview

Prism provides a structured way to run test suites, capture traces, and
evaluate AI agent performance using assertions. It is designed as a
standalone Python package with a Dash-based UI.

## Key Features

- **Test Suite Management**: Organize and run complex evaluations.
- **Trace Capture**: Detailed visibility into agent execution steps.
- **Assertion Engine**: Automated validation of agent responses.
- **Modern UI**: High-density diagnostic tables and comparison dashboards
  built with Dash Mantine Components.

## Quick Start

### 1. Prerequisites

- Python 3.10+
- PostgreSQL (Local or Cloud SQL)
- Google Cloud SDK (for Gen AI features)

### 2. Setup (Automated)
The easiest way to get started is using the provided setup script, which
automates dependency installation via `uv`:
```bash
./scripts/setup.sh
```
To also set up a local PostgreSQL database automatically (requires `sudo` and
PostgreSQL installed), use:
```bash
./scripts/setup.sh --db
```
The script will:
1. Ensure `uv` is installed.
2. Synchronize all dependencies and create/update the virtual environment in
   `.venv`.
3. (If `--db` is used) Create the `prism` and `prism_test` databases and run
   migrations.

### 3. Running the Application

#### Development Mode (Debug)
The built-in Flask development server is recommended for active development.
You can use the convenience script or `uv run` directly:
```bash
./scripts/run_app.sh
```
Or:
```bash
uv run python src/prism/ui/app.py
```

#### Production Mode (Gunicorn)
For production deployments, we use **Gunicorn** for better performance and
concurrency.
```bash
uv run gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 --timeout 0 "prism.prod:app"
```

## Configuration

Prism uses environment variables for configuration. These can be defined in
a `.env` file in the root directory.

### Database Configuration
| Variable | Description | Default |
| :--- | :--- | :--- |
| `DATABASE_URL` | Standard SQLAlchemy connection URI. | `postgresql://localhost/prism` |
| `DB_USER` | Database username. | `postgres` |
| `DB_PASS` | Database password. | `""` |
| `DB_NAME` | Database name. | `prism` |

### GCP Project Configuration
Prism interacts with GCP services for agent execution and LLM-based evaluation:

| Variable | Description | Example |
| :--- | :--- | :--- |
| `PRISM_GDA_PROJECTS` | Comma-separated list of GCP projects containing GDA agents. | `project-1,project-2` |
| `PRISM_GENAI_CLIENT_PROJECT` | The GCP project used for Gen AI (evaluation). | `my-genai-project` |
| `PRISM_GENAI_CLIENT_LOCATION` | The GCP location for Gen AI services. | `us-central1` |

### Agent Authentication
Prism supports various agent types, each requiring specific authentication:

- **Looker Agents**: Require a Looker Instance URI, Client ID, and Client Secret.
- **BigQuery Agents**: Require the IAM roles listed above. Additionally, the
  service account must have access to the specific datasets used by the agent.

## Deployment

### 1. Docker
Prism includes a `Dockerfile` for containerized deployments.
To build and run locally:
```bash
docker build -t prism-app .
docker run -p 8080:8080 --env-file .env prism-app
```

### 2. Cloud Run & Cloud SQL
For production deployments on Google Cloud, we recommend **Cloud Run**
connected to **Cloud SQL (PostgreSQL)**.

#### IAM Roles
The Cloud Run service account may require the following IAM roles:

- `BigQuery User`
- `Cloud Build Service Account`
- `Cloud SQL Client`
- `Gemini Data Analytics Data Agent Owner (Beta)`
- `Gemini for Google Cloud User`
- `Secret Manager Secret Accessor`
- `Vertex AI User` (for Gen AI evaluation)

#### Deployment Checklist:
1.  **Build and Push**: Push your image to Artifact Registry.
2.  **Database**: Create a Cloud SQL instance.
3.  **Secrets**: Store your database password in Secret Manager.
4.  **Deploy**: Use `gcloud run deploy` with the following key configurations:
    - Add Cloud SQL instance connection.
    - Set `DATABASE_URL` or connection environment variables.

Example deployment command (simplified):
```bash
gcloud run deploy prism-app \
  --image GCR_IMAGE_URL \
  --add-cloudsql-instances INSTANCE_CONNECTION_NAME \
  --set-env-vars "INSTANCE_CONNECTION_NAME=...,DB_NAME=prism,DB_USER=postgres" \
  --set-secrets "DB_PASS=YOUR_SECRET_NAME:latest"
```

## Testing
Run the test suite using the provided script:
```bash
./scripts/run_tests.sh
```
