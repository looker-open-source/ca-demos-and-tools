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

"""Tests for the test-database guard.

``tests/db_guard.py`` is what stands between ``uv run pytest`` and a
developer's real data. The suite truncates every table, and trial execution
writes from a spawned subprocess that never sees the pytest fixtures. A wrong
guard is worse than no guard because it gets trusted, so the classifier is
pinned here, near misses included.
"""

from __future__ import annotations

import os
from unittest import mock

from prism.server import config
from prism.server import db
import pytest
from tests import db_guard

_LOCAL_TEST_URL = "postgresql://prism:pw@localhost:5432/prism_test"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://prism:pw@localhost:5432/prism_test",
        "postgresql://prism:pw@localhost:5432/prism_e2e",
        "postgresql:///prism_test?host=/var/run/postgresql",
        "postgresql://localhost/prism-e2e",
        # A database named for nothing but its purpose is still a test database.
        "postgresql://localhost/test",
        "postgresql://localhost/e2e",
    ],
)
def test_test_shaped_names_are_accepted(url: str):
  assert db_guard.is_safe_test_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/prism",
        # Both end in the letters "test" without being test databases, which is
        # what a substring check gets wrong.
        "postgresql://localhost/contest",
        "postgresql://localhost/latest",
        # A leading marker is not a marker: _SAFE_NAME_RE wants it at the end.
        # This is the production database of a product called "test_harness".
        "postgresql://localhost/test_harness",
        # No database at all, which is the Cloud SQL connector form.
        "postgresql+pg8000://",
        "not a url",
    ],
)
def test_other_names_are_rejected(url: str):
  assert not db_guard.is_safe_test_database(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/prism_test",
        "postgresql://127.0.0.1:5432/prism_test",
        "postgresql://[::1]/prism_test",
        # The unix socket form, which carries the directory in a query param
        # instead of the netloc.
        "postgresql:///prism_test?host=/var/run/postgresql",
    ],
)
def test_local_hosts_are_accepted(url: str):
  assert db_guard.is_local_host(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://prod-host/prism_test",
        "postgresql://10.0.0.4:5432/prism_test",
        "postgresql:///prism_test?host=/cloudsql/proj:us-central1:prism",
    ],
)
def test_remote_hosts_are_rejected(url: str):
  assert not db_guard.is_local_host(url)


def test_resolve_accepts_a_local_test_database(monkeypatch):
  monkeypatch.setenv("TEST_DATABASE_URL", _LOCAL_TEST_URL)
  monkeypatch.delenv("DATABASE_URL", raising=False)
  assert db_guard.resolve_test_database_url() == _LOCAL_TEST_URL


def test_resolve_rejects_a_real_database(monkeypatch):
  monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://localhost/prism")
  monkeypatch.delenv("DATABASE_URL", raising=False)
  with pytest.raises(db_guard.UnsafeTestDatabaseError, match="prism"):
    db_guard.resolve_test_database_url()


def test_resolve_rejects_a_test_name_on_a_remote_host(monkeypatch):
  """The name alone cannot tell you whose server you are truncating."""
  monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://prod-host/prism_test")
  monkeypatch.delenv("DATABASE_URL", raising=False)
  with pytest.raises(db_guard.UnsafeTestDatabaseError, match="prod-host"):
    db_guard.resolve_test_database_url()


def test_resolve_rejects_a_disagreeing_database_url(monkeypatch):
  """A spawned trial worker reads DATABASE_URL, not TEST_DATABASE_URL."""
  monkeypatch.setenv("TEST_DATABASE_URL", _LOCAL_TEST_URL)
  monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/prism")
  with pytest.raises(db_guard.UnsafeTestDatabaseError, match="disagree"):
    db_guard.resolve_test_database_url()


def test_resolve_falls_back_to_the_documented_default(monkeypatch):
  monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
  monkeypatch.delenv("DATABASE_URL", raising=False)
  url = db_guard.resolve_test_database_url()
  assert url == db_guard.DEFAULT_TEST_DATABASE_URL
  assert db_guard.is_safe_test_database(url)
  assert db_guard.is_local_host(url)


_CLOUD_SQL_INSTANCE = "prism-prod:us-central1:prism"


def test_an_instance_connection_name_outranks_database_url():
  """This is why the guard has to deal with it, and not just with the URL."""
  settings = config.Settings(
      instance_connection_name=_CLOUD_SQL_INSTANCE,
      database_url=_LOCAL_TEST_URL,
  )

  assert settings.final_database_url != _LOCAL_TEST_URL


def test_an_emptied_instance_connection_name_falls_through():
  """Empty has to be as good as absent, because absent is not an option."""
  settings = config.Settings(
      instance_connection_name="", database_url=_LOCAL_TEST_URL
  )

  assert settings.final_database_url == _LOCAL_TEST_URL


def test_enforce_takes_the_cloud_sql_instance_out_of_the_environment(
    monkeypatch,
):
  """A spawned trial worker read it, dialled Cloud SQL, and wrote real data.

  The guard set DATABASE_URL and stopped there. settings.final_database_url
  takes INSTANCE_CONNECTION_NAME ahead of DATABASE_URL, so the child ignored
  what the guard had set. Nothing failed: the suite passed, against the
  deployed database.
  """
  monkeypatch.setenv("TEST_DATABASE_URL", _LOCAL_TEST_URL)
  monkeypatch.setenv("DATABASE_URL", _LOCAL_TEST_URL)
  monkeypatch.setenv("INSTANCE_CONNECTION_NAME", _CLOUD_SQL_INSTANCE)
  monkeypatch.setattr(
      config.settings, "instance_connection_name", _CLOUD_SQL_INSTANCE
  )
  # The real rebind would swap the engine the rest of this session is running
  # on, so only the environment is under test here.
  monkeypatch.setattr(db, "make_engine", lambda url: mock.Mock(name=url))
  monkeypatch.setattr(db, "engine", mock.Mock())
  monkeypatch.setattr(db, "SessionLocal", mock.Mock())

  db_guard.enforce()

  # Emptied, not deleted. config.py calls load_dotenv, which sets a variable
  # that is absent and leaves one that is present alone, so deleting it would
  # let the developer's .env restore it in the child.
  assert os.environ["INSTANCE_CONNECTION_NAME"] == ""
  assert not config.settings.instance_connection_name
