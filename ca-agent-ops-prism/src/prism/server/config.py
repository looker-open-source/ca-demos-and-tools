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

import logging
import os
import dotenv
import pydantic

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Load local environment variables from .env if it exists
dotenv.load_dotenv()

# Base directory of the project (root)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))


class Settings(pydantic.BaseModel):
  """Global application settings."""

  app_name: str = "Prism Core"
  debug: bool = os.getenv("PRISM_DEBUG", "false").lower() == "true"

  # 1. DATABASE_URL (Standard URI)
  # 2. INSTANCE_CONNECTION_NAME (Cloud SQL Connector)
  # 3. Local Postgres fallback (localhost)
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
  # Single project for Gen AI
  gcp_genai_project: str | None = os.getenv("PRISM_GENAI_CLIENT_PROJECT")

  @property
  def gcp_gda_projects(self) -> list[str]:
    """Returns a list of configured GDA projects."""
    if not self.gcp_gda_projects_raw:
      return []
    return [
        p.strip() for p in self.gcp_gda_projects_raw.split(",") if p.strip()
    ]

  @property
  def final_database_url(self) -> str:
    """Returns the effective database URL or PostgreSQL path."""
    if self.instance_connection_name:
      return "postgresql+pg8000://"
    if self.database_url:
      return self.database_url
    return "postgresql://localhost/prism"


settings = Settings()
logger.info("Settings: %s", settings)
