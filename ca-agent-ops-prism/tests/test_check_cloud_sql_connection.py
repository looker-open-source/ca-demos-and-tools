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

"""The connection probe has to probe what the app connects to.

The script says it reads its inputs the same way prism.server.config does, and
that was true of INSTANCE_CONNECTION_NAME, DB_USER and DB_PASS only. DB_NAME
was hardcoded to "prism" and ip_type to PUBLIC, while config reads DB_NAME and
DB_IP_TYPE from the environment. In a deployment that sets either, the script
opened a different database over a different network path and could report
success while the app could not connect. Telling a bad instance name or
password apart from a problem inside the app is the one thing it is for.

The script is not importable as a module, so it is loaded by path.
"""

import importlib.util
import pathlib
from unittest import mock

import pytest

_SCRIPT = (
    pathlib.Path(__file__).resolve().parents[1]
    / "scripts"
    / "check_cloud_sql_connection.py"
)


@pytest.fixture(name="script")
def _script():
  """Loads the script under its own module name, once per test."""
  spec = importlib.util.spec_from_file_location(
      "check_cloud_sql_connection", _SCRIPT
  )
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


@pytest.fixture(name="connector")
def _connector(script, monkeypatch):
  """Replaces the connector and SQLAlchemy, leaving the env reading real.

  sqlalchemy is swapped on the script module only, so the engine is never
  built and the creator the script hands it can be called by the test.
  """
  connector = mock.MagicMock()
  monkeypatch.setattr(
      script, "Connector", mock.MagicMock(return_value=connector)
  )
  monkeypatch.setattr(script, "sqlalchemy", mock.MagicMock())
  return connector


def _connect_kwargs(script, connector) -> dict:
  """Runs the probe and returns the kwargs it would open the socket with."""
  assert script.check_connection() is True
  creator = script.sqlalchemy.create_engine.call_args.kwargs["creator"]
  creator()
  return connector.connect.call_args.kwargs


def test_the_probe_uses_the_database_name_and_ip_type_from_the_environment(
    script, connector, monkeypatch
):
  """A staging database behind private IP is the case that used to pass."""
  monkeypatch.setenv("INSTANCE_CONNECTION_NAME", "proj:us-central1:prism-db")
  monkeypatch.setenv("DB_PASS", "secret")
  monkeypatch.setenv("DB_NAME", "prism_staging")
  monkeypatch.setenv("DB_IP_TYPE", "PRIVATE")

  kwargs = _connect_kwargs(script, connector)

  assert kwargs["db"] == "prism_staging"
  assert kwargs["ip_type"] == "PRIVATE"


def test_the_probe_falls_back_to_the_same_defaults_config_uses(
    script, connector, monkeypatch
):
  """prism and PUBLIC, which is what prism.server.config defaults to."""
  monkeypatch.setenv("INSTANCE_CONNECTION_NAME", "proj:us-central1:prism-db")
  monkeypatch.setenv("DB_PASS", "secret")
  monkeypatch.delenv("DB_NAME", raising=False)
  monkeypatch.delenv("DB_IP_TYPE", raising=False)

  kwargs = _connect_kwargs(script, connector)

  assert kwargs["db"] == "prism"
  assert kwargs["ip_type"] == "PUBLIC"
  assert kwargs["user"] == "postgres"


def test_a_missing_instance_fails_before_opening_anything(
    script, connector, monkeypatch
):
  """There is nothing to connect to, so nothing is opened."""
  monkeypatch.delenv("INSTANCE_CONNECTION_NAME", raising=False)
  monkeypatch.setenv("DB_PASS", "secret")

  assert script.check_connection() is False
  connector.connect.assert_not_called()


def test_an_empty_password_still_tries_the_connection(
    script, connector, monkeypatch
):
  """The script has to fail where the app fails and nowhere else.

  config.py defaults DB_PASS to the empty string and hands it to the connector,
  which is how IAM database authentication works. Refusing here reported a
  working deployment as broken.
  """
  monkeypatch.setenv("INSTANCE_CONNECTION_NAME", "proj:us-central1:prism-db")
  monkeypatch.delenv("DB_PASS", raising=False)

  assert _connect_kwargs(script, connector)["password"] == ""
