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

"""Unit tests for scripts/export_to_bigquery.py CLI utility."""

import importlib.util
import os
import sys
from typing import Any
from unittest import mock
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.models.snapshot import TestSuiteSnapshot
import pytest
from sqlalchemy import orm

_SCRIPTS_PATH = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ),
    "scripts",
    "export_to_bigquery.py",
)


def _get_cli_module():
  spec = importlib.util.spec_from_file_location(
      "export_to_bigquery", _SCRIPTS_PATH
  )
  mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(mod)
  return mod


@pytest.fixture
def sample_cli_runs(db_session: orm.Session):
  """One COMPLETED run and one RUNNING one, under the same agent.

  The RUNNING run is the point. --all and --agent-id sweep up whatever runs
  they find, and a run still in flight has trials that have not finished, so
  it has to be skipped until it lands.
  """
  agent = Agent(
      name="CLI Test Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-cli",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(name="CLI Suite", description="CLI testing")
  db_session.add(suite_snap)
  db_session.flush()

  run1 = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snap.id,
      status=RunStatus.COMPLETED,
  )
  run2 = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snap.id,
      status=RunStatus.RUNNING,
  )
  db_session.add_all([run1, run2])
  db_session.commit()

  class _SessionCtx:

    def __init__(self, session):
      self.session = session

    def __enter__(self):
      return self.session

    def __exit__(self, exc_type, exc_val, exc_tb):
      pass

  return {
      "agent_id": agent.id,
      "completed_run_id": run1.id,
      "running_run_id": run2.id,
      "session_ctx": _SessionCtx(db_session),
  }


def test_cli_export_single_run(sample_cli_runs: dict[str, Any]):
  cli_mod = _get_cli_module()

  test_args = [
      "export_to_bigquery.py",
      "--run-id",
      str(sample_cli_runs["completed_run_id"]),
      "--project",
      "test-p",
      "--dataset",
      "test-d",
  ]
  with mock.patch.object(sys, "argv", test_args):
    with mock.patch.object(
        cli_mod.db, "SessionLocal", return_value=sample_cli_runs["session_ctx"]
    ):
      with mock.patch.object(cli_mod, "BigQueryExporter") as mock_exporter_cls:
        mock_exporter = mock.MagicMock()
        mock_exporter.dataset_id = "test-d"
        mock_exporter.export_run.return_value = {
            "runs": 1,
            "trials": 0,
            "assertions": 0,
            "traces": 0,
        }
        mock_exporter_cls.return_value = mock_exporter

        cli_mod.main()

        mock_exporter.export_run.assert_called_once()
        assert (
            mock_exporter.export_run.call_args[0][0]
            == sample_cli_runs["completed_run_id"]
        )


def test_cli_export_agent_runs(sample_cli_runs: dict[str, Any]):
  cli_mod = _get_cli_module()

  test_args = [
      "export_to_bigquery.py",
      "--agent-id",
      str(sample_cli_runs["agent_id"]),
      "--project",
      "test-p",
      "--dataset",
      "test-d",
  ]
  with mock.patch.object(sys, "argv", test_args):
    with mock.patch.object(
        cli_mod.db, "SessionLocal", return_value=sample_cli_runs["session_ctx"]
    ):
      with mock.patch.object(cli_mod, "BigQueryExporter") as mock_exporter_cls:
        mock_exporter = mock.MagicMock()
        mock_exporter.dataset_id = "test-d"
        mock_exporter.export_run.return_value = {
            "runs": 1,
            "trials": 0,
            "assertions": 0,
            "traces": 0,
        }
        mock_exporter_cls.return_value = mock_exporter

        cli_mod.main()

        # Once, for the completed run. A run still going has trials that will
        # change, so exporting it would write a half-finished result.
        mock_exporter.export_run.assert_called_once()
        assert (
            mock_exporter.export_run.call_args[0][0]
            == sample_cli_runs["completed_run_id"]
        )


def test_cli_export_all_runs(sample_cli_runs: dict[str, Any]):
  cli_mod = _get_cli_module()

  test_args = [
      "export_to_bigquery.py",
      "--all",
      "--force",
      "--project",
      "test-p",
      "--dataset",
      "test-d",
  ]
  with mock.patch.object(sys, "argv", test_args):
    with mock.patch.object(
        cli_mod.db, "SessionLocal", return_value=sample_cli_runs["session_ctx"]
    ):
      with mock.patch.object(cli_mod, "BigQueryExporter") as mock_exporter_cls:
        mock_exporter = mock.MagicMock()
        mock_exporter.dataset_id = "test-d"
        mock_exporter.export_run.return_value = {
            "runs": 1,
            "trials": 0,
            "assertions": 0,
            "traces": 0,
        }
        mock_exporter_cls.return_value = mock_exporter

        cli_mod.main()

        mock_exporter.export_run.assert_called_once()
        assert mock_exporter.export_run.call_args[1]["force"] is True


def test_cli_exits_nonzero_when_rows_were_rejected(
    sample_cli_runs: dict[str, Any],
):
  """The exit code comes from the recorded error, not from the counts.

  A partial export writes the run row and records the failure against the run,
  so the counts on their own can still read like a clean pass. Sign-off used to
  be taken from them, and a schema drift ended in a zero exit over a warehouse
  missing its trials.
  """
  cli_mod = _get_cli_module()

  test_args = [
      "export_to_bigquery.py",
      "--run-id",
      str(sample_cli_runs["completed_run_id"]),
      "--project",
      "test-p",
      "--dataset",
      "test-d",
  ]
  with (
      mock.patch.object(sys, "argv", test_args),
      mock.patch.object(
          cli_mod.db,
          "SessionLocal",
          return_value=sample_cli_runs["session_ctx"],
      ),
      mock.patch.object(cli_mod, "BigQueryExporter") as mock_exporter_cls,
      mock.patch.object(
          cli_mod, "get_run_export_error", return_value="trials: no such field"
      ),
  ):
    mock_exporter = mock.MagicMock()
    mock_exporter.dataset_id = "test-d"
    mock_exporter.export_run.return_value = {
        "runs": 1,
        "trials": 4,
        "assertions": 0,
        "traces": 0,
    }
    mock_exporter_cls.return_value = mock_exporter

    with pytest.raises(SystemExit) as exc_info:
      cli_mod.main()

  assert exc_info.value.code == 1


def test_cli_missing_arguments():
  cli_mod = _get_cli_module()

  test_args = ["export_to_bigquery.py"]
  with mock.patch.object(sys, "argv", test_args):
    with pytest.raises(SystemExit) as exc_info:
      cli_mod.main()
    assert exc_info.value.code == 1
