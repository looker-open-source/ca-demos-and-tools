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


def configure_logging() -> None:
  """Points application logging at stdout at INFO.

  force=True because this has to win. Three modules call basicConfig, and
  ``alembic upgrade`` rewrites the root logger wholesale from the [loggers]
  section of alembic.ini (WARN level, stderr, alembic's own format). Whoever
  runs last owns the configuration, so this is called again after migrations.
  """
  logging.basicConfig(
      stream=sys.stdout,
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
      force=True,
  )


configure_logging()

logger = logging.getLogger(__name__)

logger.info("Initializing Prism production server")


def check_db_connection() -> bool:
  """Opens one connection and runs SELECT 1. False if that fails."""
  try:
    with engine.connect() as conn:
      conn.execute(sqlalchemy.text("SELECT 1"))
      return True
  except Exception:  # pylint: disable=broad-except
    logger.exception("Canary connection test failed")
    return False


def run_migrations() -> None:
  """Upgrades the database to head."""
  # Under gunicorn the working directory is the project root, so the relative
  # path is the normal case. The fallback covers importing prism.prod from
  # anywhere else. This file is src/prism/prod.py, so the project root is two
  # levels up. It used to be three, which landed on the parent of the checkout
  # and raised at import from any cwd that was not the root.
  config_path = "alembic.ini"
  if not os.path.exists(config_path):
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../alembic.ini")
    )

  logger.info("Running migrations using config: %s", config_path)
  alembic.command.upgrade(alembic.config.Config(config_path), "head")


# Fail closed. Serving on a database that is unreachable or behind the schema
# gives an error on every page, and Cloud Run keeps the revision in rotation
# because the port is open. Raising here makes the deploy fail instead, and the
# previous revision keeps serving.
if not check_db_connection():
  raise RuntimeError("Database canary failed, refusing to start.")

run_migrations()

# Migrations reconfigure logging out from under us, so take it back before the
# app starts serving.
configure_logging()

app = prism.ui.app.server

PrismClient().system.start_worker_pool()

logger.info("Prism app ready.")
