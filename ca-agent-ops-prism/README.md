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

This directory contains the Core Backend for the Prism application, a platform for monitoring and evaluating AI Agents.

## Project Overview

Prism provides a structured way to run test suites, capture traces, and evaluate AI agent performance using assertions. It is designed as a standalone Python package with a Dash-based UI.

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
- Google Cloud SDK (for Vertex AI features)

### 2. Setup
Run the setup script to create a virtual environment, install dependencies,
and initialize the database:
```bash
./scripts/setup.sh
```

### 3. Local PostgreSQL Setup
If you are running locally, use the provided script to set up your database
and generate a `.env` file:
```bash
./scripts/setup_postgres.sh
```

For detailed setup instructions, including Docker and Cloud SQL configuration,
see [LOCAL_SETUP.md](LOCAL_SETUP.md).

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
| `PRISM_VERTEX_PROJECT` | The GCP project used for Vertex AI (evaluation). | `my-vertex-project` |
| `PRISM_VERTEX_LOCATION` | The GCP location for Vertex AI services. | `us-central1` |

## Testing
Run the test suite using the provided script:
```bash
./scripts/run_tests.sh
```

---

For architectural guidelines and internal patterns, see [GEMINI.md](GEMINI.md).
