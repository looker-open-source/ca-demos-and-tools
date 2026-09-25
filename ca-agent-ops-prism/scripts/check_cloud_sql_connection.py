#!/usr/bin/env python3
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

"""Opens one Cloud SQL connection and reports whether it worked.

Run by hand when the deployed app cannot reach its database, to tell a bad
instance name or password apart from a problem inside the app. Reads
INSTANCE_CONNECTION_NAME, DB_USER, DB_PASS, DB_NAME and DB_IP_TYPE from the
environment, with the same defaults prism.server.config uses, and exits
non-zero on failure so it can be used in a shell chain.

The last two used to be hardcoded to "prism" and PUBLIC. A deployment that
sets either one had this script probing a different database over a different
network path from the app, so it could pass while the app could not connect,
which is the one answer it exists to give.

An unset DB_PASS used to be a hard failure here. config.py defaults it to the
empty string, so a deployment that authenticates some other way got a refusal
from this script instead of the connection result it was run for. It now
defaults the same way and lets the connector answer.
"""

import logging
import os
import sys

from google.cloud.sql.connector import Connector
import sqlalchemy

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_connection() -> bool:
  """Returns True if a query against the configured database succeeded."""
  instance_connection_name = os.getenv("INSTANCE_CONNECTION_NAME")
  db_user = os.getenv("DB_USER", "postgres")
  db_pass = os.getenv("DB_PASS", "")
  db_name = os.getenv("DB_NAME", "prism")
  db_ip_type = os.getenv("DB_IP_TYPE", "PUBLIC")

  if not instance_connection_name:
    logger.error("INSTANCE_CONNECTION_NAME is not set.")
    return False
  if not db_pass:
    logger.info("DB_PASS is empty. Connecting without one, as the app would.")

  connector = Connector()

  def getconn():
    return connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_pass,
        db=db_name,
        ip_type=db_ip_type,
    )

  logger.info(
      "Connecting to %s (database: %s, ip_type: %s)...",
      instance_connection_name,
      db_name,
      db_ip_type,
  )
  try:
    pool = sqlalchemy.create_engine(
        "postgresql+pg8000://",
        creator=getconn,
    )
    with pool.connect() as db_conn:
      result = db_conn.execute(sqlalchemy.text("SELECT NOW()")).fetchone()
      logger.info("Connected. Database time is %s.", result[0])
      return True
  except Exception as e:  # pylint: disable=broad-except
    logger.error("Failed to connect to '%s': %s", db_name, e)
    return False
  finally:
    connector.close()


if __name__ == "__main__":
  sys.exit(0 if check_connection() else 1)
