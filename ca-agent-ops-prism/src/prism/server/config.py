# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Application configuration."""

import os
import dotenv
import pydantic

# Anchored on this file rather than left to find_dotenv, which starts from the
# working directory under a REPL or python -c. A prism started from outside the
# checkout found no .env and fell through to the postgresql://localhost/prism
# fallback below, against a database that was usually empty.
_CHECKOUT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
dotenv.load_dotenv(os.path.join(_CHECKOUT_ROOT, ".env"))


class Settings(pydantic.BaseModel):
  """Global application settings."""

  # final_database_url takes the first of these it can: INSTANCE_CONNECTION_NAME
  # (Cloud SQL Connector), then DATABASE_URL (a standard URI), then a local
  # Postgres fallback.
  database_url: str | None = os.getenv("DATABASE_URL")
  instance_connection_name: str | None = os.getenv("INSTANCE_CONNECTION_NAME")
  db_user: str = os.getenv("DB_USER", "postgres")
  db_pass: str = os.getenv("DB_PASS", "")
  db_name: str = os.getenv("DB_NAME", "prism")
  db_ip_type: str = os.getenv("DB_IP_TYPE", "PUBLIC")
  gcp_genai_location: str = os.getenv(
      "PRISM_GENAI_CLIENT_LOCATION", "us-central1"
  )

  # GCP Projects
  # Comma-separated list for GDA API (e.g., "proj-1,proj-2")
  gcp_gda_projects_raw: str = os.getenv("PRISM_GDA_PROJECTS", "")
  # Comma-separated list of GCP locations to scan for GDA agents
  gcp_gda_locations_raw: str = os.getenv("PRISM_GDA_LOCATIONS", "global,us,eu")
  # Single project for Gen AI
  gcp_genai_project: str | None = os.getenv("PRISM_GENAI_CLIENT_PROJECT")

  # BigQuery Evaluation Exporter Settings
  bigquery_export_enabled: bool = (
      os.getenv("BIGQUERY_EXPORT_ENABLED", "false").lower() == "true"
  )
  bigquery_export_project: str | None = os.getenv("BIGQUERY_EXPORT_PROJECT")
  bigquery_export_dataset: str = os.getenv(
      "BIGQUERY_EXPORT_DATASET", "prism_evals"
  )
  bigquery_export_location: str = os.getenv("BIGQUERY_EXPORT_LOCATION", "US")

  # PRISM_DEBUG is not a setting. Its only reader is the dev server in
  # prism/ui/app.py, and prism.ui can't import prism.server
  # (tests/test_ui_isolation.py).
  #
  # PRISM_AGENT_BACKEND ("live" / "record" / "replay") isn't a setting either.
  # Settings are read once at import, but cassette replay also has to work
  # inside spawned trial workers. recording.current_backend() reads the
  # environment on each call and validates the value.

  @property
  def gcp_gda_projects(self) -> list[str]:
    """Splits PRISM_GDA_PROJECTS. Empty when the variable is unset."""
    if not self.gcp_gda_projects_raw:
      return []
    return [
        p.strip() for p in self.gcp_gda_projects_raw.split(",") if p.strip()
    ]

  @property
  def gcp_gda_locations(self) -> list[str]:
    """Splits PRISM_GDA_LOCATIONS, defaulting to global, us and eu."""
    if not self.gcp_gda_locations_raw:
      return ["global", "us", "eu"]
    return [
        loc.strip().lower()
        for loc in self.gcp_gda_locations_raw.split(",")
        if loc.strip()
    ]

  @property
  def final_database_url(self) -> str:
    """Returns the first database URL the settings above can supply."""
    if self.instance_connection_name:
      return "postgresql+pg8000://"
    if self.database_url:
      return self.database_url
    return "postgresql://localhost/prism"


settings = Settings()

# Don't log `settings`. Formatting it prints db_pass in clear text, and
# database_url holds the same password again. There used to be a
# logger.info("Settings: %s", settings) here; it printed nothing only because
# fileConfig() disabled this logger first. It no longer does, so a line like
# that would now print.
