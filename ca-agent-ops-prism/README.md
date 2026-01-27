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

This directory contains the Core Backend for the Prism application,
a platform for monitoring and evaluating AI Agents.

## Project Overview

Prism provides a structured way to run test suites, capture traces, and
evaluate AI agent performance using assertions. It is designed as a standalone
Python package with a Dash-based UI.

## Key Features

- **Test Suite Management**: Organize and run complex evaluations.
- **Trace Capture**: Detailed visibility into agent execution steps.
- **Assertion Engine**: Automated validation of agent responses.
- **Modern UI**: High-density diagnostic tables and comparison dashboards built with Dash Mantine Components.

## Setup & Installation

### 1. Prerequisites
Ensure you have the following installed on your system:

- **Python 3.10 or higher**
- **PostgreSQL 14 or higher**
- **Google Cloud SDK (gcloud)** (Optional, required for LLM-based assertions and
  suggestions)

### 2. Standard Setup
Run the `setup.sh` script to automate virtual environment creation and
dependency installation:
```bash
./scripts/setup.sh
```
This script will:
1. Create a virtual environment at `~/prism_venv`.
2. Install all necessary Python dependencies from `requirements.txt`.
3. Install the `prism` package in editable mode.

To also set up a local PostgreSQL database automatically, use:
```bash
./scripts/setup.sh --db
```

### 3. Database Setup (PostgreSQL)

Prism requires a PostgreSQL database to store test suites, runs, and results.

#### Automated Setup (Recommended)
If you have `sudo` access and PostgreSQL installed locally,
you can run the standalone database script:
```bash
./scripts/setup_postgres.sh
```
This script will:
1. Create `prism` and `prism_test` databases.
2. Create a database user and grant permissions.
3. Generate a `.env` file with the correct `DATABASE_URL`.
4. Run initial database migrations via Alembic.

#### Manual Setup
If you prefer to set up the database manually:
1. Create a database named `prism`.
2. Configure your connection string in a `.env` file:
   ```text
   DATABASE_URL=postgresql://user:password@localhost:5432/prism
   ```
3. Run migrations:
   ```bash
   source ~/prism_venv/bin/activate
   alembic upgrade head
   ```

### 4. Google Cloud Configuration
To use features like **LLM-based assertions** and **suggested assertions**,
configure access to Vertex AI:
1. **Authenticate gcloud**:
   ```bash
   gcloud auth application-default login
   ```
2. **Configure Environment Variables**:
   Add the following to your `.env` file:
   ```text
   PRISM_VERTEX_PROJECT=your-gcp-project-id
   PRISM_VERTEX_LOCATION=us-central1
   ```

## Configuration

Prism uses environment variables for configuration.
These can be defined in a `.env` file in the root directory.

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
| `PRISM_VERTEX_PROJECT` | The GCP project used for Vertex AI (evaluation). | `my-vertex-project` |
| `PRISM_VERTEX_LOCATION` | The GCP location for Vertex AI services. | `us-central1` |

### Agent Authentication
Prism supports various agent types, each requiring specific authentication:

- **Looker Agents**: Require a Looker Instance URI, Client ID, and Client Secret.
- **BigQuery Agents**: Require the IAM roles listed above. Additionally, the
  service account must have access to the specific datasets used by the agent.

## Run Modes

### 1. Development Mode (Debug)
This mode uses the built-in Flask development server.
Recommended for active development.
```bash
source ~/prism_venv/bin/activate
python src/prism/ui/app.py
```

### 2. Production Mode (Gunicorn)
For production deployments, we use **Gunicorn**. This provides better
performance and concurrency. It also automatically handles database
migrations on startup.
```bash
source ~/prism_venv/bin/activate
gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 --timeout 0 "prism.prod:app"
```

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
- `Vertex AI User`

#### Deployment Checklist:
1.  **Build and Push**: Push your image to Artifact Registry.
2.  **Database**: Create a Cloud SQL instance.
3.  **Secrets**: Store your database password in Secret Manager.
4.  **Deploy**: Use `gcloud run deploy` with the following key configurations:
    - Add Cloud SQL instance connection.
    - Set `DATABASE_URL` or connection environment variables.
    - Mount necessary volumes (e.g., for persistent trace data if not using a database for everything).

Example deployment command (simplified):
```bash
gcloud run deploy prism-app \
  --image GCR_IMAGE_URL \
  --add-cloudsql-instances INSTANCE_CONNECTION_NAME \
  --set-env-vars "INSTANCE_CONNECTION_NAME=...,DB_NAME=prism,DB_USER=postgres" \
  --set-secrets "DB_PASS=YOUR_SECRET_NAME:latest"
```

For Google-internal developers, a comprehensive `deploy.sh` script is available
in the repository root to automate this process.

## Testing
Run the test suite using the provided script:
```bash
./scripts/run_tests.sh
```
