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

"""Database configuration and session management."""

import logging

import google.cloud.sql.connector
from prism.server.config import settings
import sqlalchemy
import sqlalchemy.orm

logger = logging.getLogger(__name__)

_connector = None


def get_conn():
  """Connects through the Cloud SQL Connector, or returns None if unconfigured.

  make_engine only installs this as the creator when an instance is
  configured, so the None is never handed back to SQLAlchemy.
  """
  global _connector
  logger.debug(
      "get_conn called: instance=%s", settings.instance_connection_name
  )
  if settings.instance_connection_name:
    if _connector is None:
      # Initialize Connector with a higher timeout for cold starts
      _connector = google.cloud.sql.connector.Connector(timeout=60)

    # DEBUG, not INFO. pool_pre_ping and pool_recycle mean this runs on every
    # reconnect, and the line carries the instance connection name and the
    # database user into the log each time.
    logger.debug(
        "Attempting Cloud SQL connection: instance=%s, db=%s, user=%s,"
        " ip_type=%s",
        settings.instance_connection_name,
        settings.db_name,
        settings.db_user,
        settings.db_ip_type,
    )
    return _connector.connect(
        settings.instance_connection_name,
        "pg8000",
        user=settings.db_user,
        password=settings.db_pass.replace("\n", "").strip()
        if settings.db_pass
        else "",
        db=settings.db_name,
        ip_type=settings.db_ip_type,
    )

  return None


def make_engine(url: str) -> sqlalchemy.Engine:
  """Builds an engine with the pooling the deployment needs.

  Cloud Run scales to zero and Cloud SQL closes connections it considers idle,
  so a pooled connection is often already dead by the time the next request
  picks it up. pool_pre_ping pays a round trip to find out. pool_recycle
  retires the connection before the server gets the chance.

  tests/db_guard.py rebinds ``engine`` onto the test database and comes back
  through here, so the tests run on the same pool settings production does.
  """
  options = {}
  if settings.instance_connection_name and url == settings.final_database_url:
    # The connector dials the instance itself, so the URL carries no host.
    # Only for the configured url: a creator makes SQLAlchemy ignore the url
    # altogether, so attaching one to any other url would quietly open the
    # Cloud SQL database instead. db_guard rebinds onto a test url through
    # here, and it checks that url on the understanding that it is the one
    # that gets opened.
    options["creator"] = get_conn

  return sqlalchemy.create_engine(
      url,
      pool_pre_ping=True,
      pool_recycle=1800,
      **options,
  )


engine = make_engine(settings.final_database_url)

SessionLocal = sqlalchemy.orm.sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)

Base = sqlalchemy.orm.declarative_base()
