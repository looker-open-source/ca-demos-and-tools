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

"""Guards against tests writing to a non-test database.

Trial execution runs in a ``spawn``ed subprocess (``worker.execute_trial``)
that re-imports everything and opens ``db.SessionLocal()``, the process-global
sessionmaker bound to whatever ``DATABASE_URL`` said at import time. That path
skips the pytest fixtures, so bare ``pytest`` with a developer ``.env`` on
disk will happily run trials against the development database and destroy
data.

This module resolves the test database URL, refuses to run if it looks like a
real database, and rebinds the process-global session factory onto the test
database. It also rewrites ``DATABASE_URL`` so spawned children inherit it,
and empties ``INSTANCE_CONNECTION_NAME``, which those children would otherwise
read first and use to dial Cloud SQL instead.
"""

import os
import re

import sqlalchemy

# Used when TEST_DATABASE_URL is absent. Matches scripts/setup_postgres.sh.
DEFAULT_TEST_DATABASE_URL = "postgresql:///prism_test?host=/var/run/postgresql"

# Only a name matching this is safe to drop or truncate. It has to be a
# trailing marker on a word boundary, not a substring: "contest" and "latest"
# both end in "test" and neither is a test database.
_SAFE_NAME_RE = re.compile(r"(?:^|[_-])(?:test|e2e)$")

# The host has to be local too. A database called prism_test on a production
# server is still on a production server, and the name can't tell you that.
# Cloud SQL sockets live under /cloudsql/ and are left out on purpose.
_LOCAL_HOSTS = ("", "localhost", "127.0.0.1", "::1", "/var/run/postgresql")


class UnsafeTestDatabaseError(RuntimeError):
  """Raised when the configured database is not safe for testing."""


def _url(url: str) -> sqlalchemy.engine.URL | None:
  try:
    return sqlalchemy.engine.make_url(url)
  except Exception:  # pylint: disable=broad-except
    return None


def database_name(url: str) -> str:
  """Extracts the database name from a SQLAlchemy URL."""
  parsed = _url(url)
  return (parsed.database if parsed else "") or ""


def database_host(url: str) -> str:
  """Extracts the host, including a unix socket directory if one is given."""
  parsed = _url(url)
  if parsed is None:
    return ""
  # psycopg takes the socket directory as a ``host`` query parameter instead
  # of in the netloc, which is what scripts/setup_postgres.sh writes.
  return (parsed.host or parsed.query.get("host") or "") or ""


def is_local_host(url: str) -> bool:
  """Returns True if the URL points at this machine."""
  return database_host(url).lower() in _LOCAL_HOSTS


def is_safe_test_database(url: str) -> bool:
  """Returns True if the URL points at something named like a test database."""
  return bool(_SAFE_NAME_RE.search(database_name(url).lower()))


def resolve_test_database_url(env_var: str = "TEST_DATABASE_URL") -> str:
  """Returns the test database URL, or raises if it is unsafe."""
  url = os.getenv(env_var) or DEFAULT_TEST_DATABASE_URL

  if not is_safe_test_database(url):
    raise UnsafeTestDatabaseError(
        f"Refusing to run tests against {database_name(url)!r} "
        f"(from {env_var}={url!r}).\n"
        "The test database name must end in 'test' or 'e2e'. Tests drop and "
        "truncate every table, and trial execution writes through a spawned "
        "subprocess that ignores the pytest fixtures."
    )

  if not is_local_host(url):
    raise UnsafeTestDatabaseError(
        f"Refusing to run tests against host {database_host(url)!r} "
        f"(from {env_var}={url!r}).\n"
        "The name looks like a test database, but a test database on a remote "
        "server is still a remote server, and the tests truncate every table. "
        "Point the tests at local Postgres (see scripts/setup_postgres.sh)."
    )

  configured = os.getenv("DATABASE_URL")
  if configured and configured != url:
    raise UnsafeTestDatabaseError(
        "DATABASE_URL and the test database disagree, so a spawned trial "
        "subprocess would write to the wrong database.\n"
        f"  DATABASE_URL      = {configured}\n"
        f"  {env_var:<17} = {url}\n"
        "Run tests via ./scripts/run_tests.sh (or ./scripts/run_e2e.sh), "
        "which exports DATABASE_URL for you."
    )

  return url


def enforce(env_var: str = "TEST_DATABASE_URL") -> str:
  """Validates the test database and rebinds all global DB state onto it.

  Also takes the Cloud SQL connector out of the environment, so a spawned
  child cannot route around the URL this sets.

  Returns:
    The resolved test database URL.

  Raises:
    UnsafeTestDatabaseError: if the configuration could touch a real database.
  """
  url = resolve_test_database_url(env_var)

  # Children spawned by the worker read this at import time; without it they
  # would fall back to the .env value or settings' localhost/prism default.
  os.environ["DATABASE_URL"] = url

  # DATABASE_URL is not the first thing settings looks at. A spawned child
  # re-imports prism.server.config, whose final_database_url takes
  # INSTANCE_CONNECTION_NAME ahead of it, and db.make_engine then hands the
  # engine the Cloud SQL connector as its creator. With one of these in the
  # environment, every trial the suite executes writes to the deployed
  # database while this guard reports success. Anything that deploys the app
  # sets it, and run_tests.sh sources .env, so it reaches pytest by an
  # ordinary route.
  #
  # Emptied, not deleted: config.py calls load_dotenv, which leaves a variable
  # that is already present alone but sets one that is absent. Deleting it
  # would let the developer's .env put it straight back.
  os.environ["INSTANCE_CONNECTION_NAME"] = ""

  # Rebind the already-constructed globals. Imported here so the environment
  # is settled before prism.server.config runs.
  from prism.server import config  # pylint: disable=import-outside-toplevel
  from prism.server import db  # pylint: disable=import-outside-toplevel

  # This process may have imported config before the lines above ran, in which
  # case settings still holds what the environment said then. Its field
  # defaults are read at class definition, so rebuilding Settings() would not
  # help.
  config.settings.instance_connection_name = None
  config.settings.database_url = url

  # Through make_engine, so the tests see production's pool settings.
  test_engine = db.make_engine(url)
  db.engine = test_engine
  # configure() mutates the existing sessionmaker in place, which matters
  # because run_client.py does `from prism.server.db import SessionLocal`.
  # Replacing the module attribute alone would leave that binding on the old
  # engine.
  db.SessionLocal.configure(bind=test_engine)

  return url
