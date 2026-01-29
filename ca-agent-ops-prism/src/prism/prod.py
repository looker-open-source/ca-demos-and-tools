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

"""Production server entry point for Prism."""

import logging
import os
import sys

import alembic.command
import alembic.config
from prism.client.prism_client import PrismClient
from prism.server.db import engine
import prism.ui.app
import sqlalchemy

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

logger.info("Initializing Prism Production Server")


def check_db_connection():
  """Quick canary test to see if we can connect to the DB."""
  print("Running canary DB connection test...")
  sys.stdout.flush()

  try:
    print("Canary: Calling engine.connect()...")
    sys.stdout.flush()
    with engine.connect() as conn:
      print("Canary: engine.connect() successful, executing SELECT 1...")
      sys.stdout.flush()
      result = conn.execute(sqlalchemy.text("SELECT 1")).scalar()
      print(f"Canary connection test successful! Result: {result}")
      sys.stdout.flush()
      return True
  except Exception as e:  # pylint: disable=broad-except
    print(f"Canary connection test FAILED: {e}")
    sys.stdout.flush()
    logger.exception("Canary connection test FAILED: %s", e)
    return False


def run_migrations():
  """Run database migrations."""
  try:
    # alembic.ini is in the project root
    # When running via gunicorn prism.prod:app, the CWD should be the root
    config_path = "alembic.ini"
    print(f"Checking for alembic.ini at: {config_path}")
    sys.stdout.flush()
    if not os.path.exists(config_path):
      # Try to find it relative to this file
      config_path = os.path.abspath(
          os.path.join(os.path.dirname(__file__), "../../../alembic.ini")
      )
      print(f"Relative alembic.ini not found, trying: {config_path}")
      sys.stdout.flush()

    logger.info("Running migrations using config: %s", config_path)
    print(f"Initializing Alembic config with: {config_path}")
    sys.stdout.flush()
    alembic_cfg = alembic.config.Config(config_path)
    print("Calling alembic.command.upgrade(head)...")
    sys.stdout.flush()
    alembic.command.upgrade(alembic_cfg, "head")
    print("Alembic upgrade finished.")
    sys.stdout.flush()
    logger.info("Migrations completed successfully.")
  except Exception as e:
    print(f"Migrations FAILED: {e}")
    sys.stdout.flush()
    logger.exception("Failed to run migrations: %s", e)


# Run migrations on module load
print("Starting database migration flow...")
sys.stdout.flush()
logger.info("Starting database migrations...")
if check_db_connection():
  run_migrations()
else:
  print("Skipping migrations due to connection failure.")
  sys.stdout.flush()
  logger.error("Skipping migrations due to connection failure.")
logger.info("Database migrations finished.")
print("Database migration flow finished.")
sys.stdout.flush()

logger.info("Exporting Dash server instance...")
app = prism.ui.app.server

logger.info("Starting background worker pool...")
PrismClient().system.start_worker_pool(num_workers=2)

logger.info("Prism App ready.")
