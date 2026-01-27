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

# Local Setup Guide

This guide provides detailed instructions for setting up Prism for local development.

## Environment Setup

### 1. Requirements
Ensure you have the following installed on your system:
- **Python 3.10 or higher**
- **PostgreSQL 14 or higher**
- **Google Cloud SDK (gcloud)** (Optional, required for LLM-based assertions and suggestions)

### 2. Standard Setup
Run the `setup.sh` script to automate the basic environment creation:
```bash
./scripts/setup.sh
```
This script will:
1. Create a virtual environment at `~/prism_venv`.
2. Install all necessary Python dependencies from `requirements.txt`.
3. Install the `prism` package in editable mode.

## Database Setup (PostgreSQL)

Prism requires a PostgreSQL database to store test suites, runs, and results.

### Automated Setup (Recommended)
If you have `sudo` access and PostgreSQL installed locally, run:
```bash
./scripts/setup_postgres.sh
```
This script will:
1. Create a `prism` database and a `prism_test` database.
2. Create a database user.
3. Grant necessary permissions.
4. Generate a `.env` file with the correct `DATABASE_URL`.
5. Run initial database migrations via Alembic.

### Manual Setup
If you prefer to set up the database manually:
1. Create a database named `prism`.
2. Configure your connection string in a `.env` file:
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/prism
   ```
3. Run migrations:
   ```bash
   source ~/prism_venv/bin/activate
   alembic upgrade head
   ```

## Google Cloud Configuration

To use features like **LLM-based assertions** and **suggested assertions**, you must configure access to Vertex AI.

1. **Authenticate gcloud**:
   ```bash
   gcloud auth application-default login
   ```
2. **Configure Environment Variables**:
   Add the following to your `.env` file:
   ```env
   PRISM_VERTEX_PROJECT=your-gcp-project-id
   PRISM_VERTEX_LOCATION=us-central1
   ```

## Run Modes
Prism can be run in two modes: **Development** (for local debugging) and **Production** (for deployment).

### 1. Development Mode (Debug)
This mode uses the built-in Flask development server. It includes features like hot-reloading and an interactive debugger. Recommended for active development.
```bash
source ~/prism_venv/bin/activate
python src/prism/ui/app.py
```

### 2. Production Mode (Gunicorn)
For production deployments (like in the provided Dockerfile), we use **Gunicorn**. This provides better performance and concurrency. It also automatically handles database migrations on startup.
```bash
source ~/prism_venv/bin/activate
gunicorn --bind 0.0.0.0:8080 --workers 1 --threads 8 --timeout 0 "prism.prod:app"
```
*Note: Ensure you are in the project root so Gunicorn can find the `prism` package and `alembic.ini`.*

---

## Testing
Ensure your local PostgreSQL service is running and execute:
```bash
./scripts/run_tests.sh
```

## Docker (Optional)

If you prefer to run Prism in a container, you can use the provided Docker script:
```bash
./scripts/docker_run.sh
```
*Note: This requires a pre-built Docker image or local build configuration.*
