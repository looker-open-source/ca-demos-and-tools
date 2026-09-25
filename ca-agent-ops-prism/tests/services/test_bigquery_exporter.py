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

"""Unit tests for the BigQuery Exporter Service."""

import datetime
import importlib.util
import os
import sys
from unittest import mock
from google.api_core import exceptions
from prism.client.run_client import RunsClient
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.config import settings
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services import bigquery_exporter as bq_mod
from prism.server.services.bigquery_exporter import BigQueryExporter
import pytest
from sqlalchemy import orm


@pytest.fixture
def sample_run_data(db_session: orm.Session):
  """A full run hierarchy: trials, assertions and traces."""
  agent = Agent(
      name="Test BigQuery Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-123",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(
      name="BQ Suite Snapshot", description="Test suite snapshot"
  )
  db_session.add(suite_snap)
  db_session.flush()

  example_snap = ExampleSnapshot(
      snapshot_suite_id=suite_snap.id,
      question="How many users registered yesterday?",
      logical_id="ex-123",
  )
  db_session.add(example_snap)
  db_session.flush()

  assert_snap = AssertionSnapshot(
      example_snapshot_id=example_snap.id,
      type=AssertionType.DATA_CHECK_ROW_COUNT,
      weight=1.0,
      params={"expected": 10},
  )
  db_session.add(assert_snap)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snap.id,
      status=RunStatus.COMPLETED,
      created_at=now,
      started_at=now,
      completed_at=now + datetime.timedelta(seconds=5),
      agent_context_snapshot={"published_version": "v1"},
  )
  db_session.add(run)
  db_session.flush()

  trial = Trial(
      run_id=run.id,
      example_snapshot_id=example_snap.id,
      status=RunStatus.COMPLETED,
      output_text="SELECT COUNT(*) FROM users",
      created_at=now,
      started_at=now,
      completed_at=now + datetime.timedelta(seconds=2),
      retry_count=0,
      trace_results=[
          {
              "type": "user_input",
              "timestamp": now.isoformat(),
              "query": "How many users?",
          },
          {
              "type": "model_output",
              "timestamp": (now + datetime.timedelta(seconds=1)).isoformat(),
              "sql": "SELECT 10",
          },
      ],
  )
  db_session.add(trial)
  db_session.flush()

  ar = AssertionResult(
      trial_id=trial.id,
      assertion_snapshot_id=assert_snap.id,
      passed=True,
      score=1.0,
      reasoning="Expected row count matched.",
  )
  db_session.add(ar)
  db_session.commit()

  return run.id


def test_ensure_dataset_and_tables():
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"

  exporter = BigQueryExporter(
      project_id="test-project",
      dataset_id="test_dataset",
      client=mock_client,
  )

  exporter.ensure_dataset_and_tables()

  assert mock_client.create_dataset.called
  # runs, trials, assertion_results, traces.
  assert mock_client.create_table.call_count == 4


def test_serialize_run(db_session: orm.Session, sample_run_data: int):
  mock_client = mock.MagicMock()
  exporter = BigQueryExporter(client=mock_client)

  run = db_session.get(Run, sample_run_data)
  record = exporter.serialize_run(run)

  assert record["run_id"] == sample_run_data
  assert record["agent_name"] == "Test BigQuery Agent"
  assert record["suite_name"] == "BQ Suite Snapshot"
  assert record["accuracy"] == 1.0
  assert record["total_trials"] == 1
  assert record["status"] == "COMPLETED"
  assert "published_version" in record["agent_context_snapshot"]


def test_serialize_trial(db_session: orm.Session, sample_run_data: int):
  mock_client = mock.MagicMock()
  exporter = BigQueryExporter(client=mock_client)

  run = db_session.get(Run, sample_run_data)
  trial = run.trials[0]
  record = exporter.serialize_trial(trial)

  assert record["trial_id"] == trial.id
  assert record["run_id"] == run.id
  assert record["question"] == "How many users registered yesterday?"
  assert record["score"] == 1.0
  assert record["output_text"] == "SELECT COUNT(*) FROM users"
  assert record["status"] == "COMPLETED"


def test_export_run(db_session: orm.Session, sample_run_data: int):
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"
  mock_client.insert_rows_json.return_value = []

  exporter = BigQueryExporter(
      project_id="test-project",
      dataset_id="test_dataset",
      client=mock_client,
  )

  stats = exporter.export_run(sample_run_data, db_session)

  assert stats["runs"] == 1
  assert stats["trials"] == 1
  assert stats["assertions"] == 1
  assert stats["traces"] == 2

  assert mock_client.insert_rows_json.call_count == 4


def test_export_run_not_found(db_session: orm.Session):
  mock_client = mock.MagicMock()
  exporter = BigQueryExporter(client=mock_client)

  stats = exporter.export_run(999999, db_session)
  assert stats == {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}
  assert not mock_client.insert_rows_json.called


def test_export_run_async():
  mock_client = mock.MagicMock()
  exporter = BigQueryExporter(
      project_id="test-project",
      dataset_id="test_dataset",
      client=mock_client,
  )

  mock_session = mock.MagicMock()
  mock_session_factory = mock.MagicMock()
  mock_session_factory.return_value.__enter__.return_value = mock_session

  with mock.patch.object(exporter, "export_run") as mock_export:
    thread = exporter.export_run_async(123, mock_session_factory)
    thread.join(timeout=5)

    assert not thread.is_alive()
    mock_export.assert_called_once_with(123, mock_session, force=False)


def test_export_run_async_deduplication():
  mock_client = mock.MagicMock()
  exporter = BigQueryExporter(
      project_id="test-project",
      dataset_id="test_dataset",
      client=mock_client,
  )

  mock_session_factory = mock.MagicMock()

  with mock.patch.object(exporter, "export_run") as mock_export:
    with bq_mod._export_lock:
      bq_mod._active_exports.add(456)

    try:
      # An export already in flight for this run, so the second call is a
      # no-op: no thread, no export_run.
      result = exporter.export_run_async(456, mock_session_factory)
      assert result is None
      assert not mock_export.called
    finally:
      with bq_mod._export_lock:
        bq_mod._active_exports.discard(456)


def test_serialize_trial_traces_timestamp_formats(
    db_session: orm.Session, sample_run_data: int
):
  """ISO strings, epoch ints/floats and invalid timestamps all export safely."""
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"
  exporter = BigQueryExporter(client=mock_client)

  run = db_session.get(Run, sample_run_data)
  trial = run.trials[0]

  trial.trace_results = [
      {"type": "step1", "timestamp": "2026-08-12T20:00:00Z"},
      {"type": "step2", "timestamp": 1723500000},
      {"type": "step3", "timestamp": 1723500000.5},
      {"type": "step4", "timestamp": None},
      {"type": "step5", "timestamp": {"nested": "invalid"}},
      {"type": "step6"},  # missing timestamp
  ]
  db_session.commit()

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    mock_client.insert_rows_json.return_value = []
    stats = exporter.export_run(sample_run_data, db_session)
    assert stats["traces"] == 6

    trace_calls = [
        c
        for c in mock_client.insert_rows_json.call_args_list
        if "prism_eval_traces" in str(c)
    ]
    assert len(trace_calls) == 1
    trace_rows = trace_calls[0].args[1]
    assert len(trace_rows) == 6
    assert trace_rows[0]["timestamp"] == "2026-08-12T20:00:00+00:00"
    assert (
        "2024" in trace_rows[1]["timestamp"]
    )  # 1723500000 corresponds to Aug 2024
    assert trace_rows[3]["timestamp"] is None
    assert trace_rows[4]["timestamp"] is None
    assert trace_rows[5]["timestamp"] is None


def test_is_run_exported():
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=mock_client
  )

  # A distinct run id per case. These are three independent scenarios, and a
  # confirmed export is now memoized (a run cannot leave BigQuery, so a repeat
  # question is answered from memory instead of a second query job). Reusing
  # one id would make case 2 a question about the memo, not about the query
  # result it means to test.

  # The query comes back with a row.
  mock_query_job = mock.MagicMock()
  mock_query_job.result.return_value = [{"f0_": 1}]
  mock_client.query.return_value = mock_query_job

  assert exporter.is_run_exported(123) is True

  # The query comes back empty.
  mock_query_job.result.return_value = []
  assert exporter.is_run_exported(124) is False

  # The query raises NotFound, which is what a missing table looks like from
  # here. It has to be that exact type: a bare Exception lands in the generic
  # handler and returns EXPORT_STATE_UNKNOWN, which is_run_exported also folds
  # to False, so this case used to pass over the wrong branch.
  mock_client.query.side_effect = exceptions.NotFound("Table not found")
  assert exporter.check_run_exported(125) == bq_mod.EXPORT_STATE_NOT_EXPORTED
  assert exporter.is_run_exported(125) is False


def test_export_run_idempotency_skip(
    db_session: orm.Session, sample_run_data: int
):
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"
  exporter = BigQueryExporter(client=mock_client)

  with mock.patch.object(exporter, "is_run_exported", return_value=True):
    stats = exporter.export_run(sample_run_data, db_session, force=False)
    assert stats == {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}
    assert not mock_client.insert_rows_json.called


def test_export_run_force(db_session: orm.Session, sample_run_data: int):
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"
  mock_client.insert_rows_json.return_value = []
  exporter = BigQueryExporter(client=mock_client)

  with mock.patch.object(exporter, "is_run_exported", return_value=True):
    stats = exporter.export_run(sample_run_data, db_session, force=True)
    assert stats["runs"] == 1
    assert mock_client.insert_rows_json.called


def _check_returns(state: str):
  """Pins the answer the status call gets out of BigQuery."""
  return mock.patch(
      "prism.server.services.bigquery_exporter.BigQueryExporter"
      ".check_run_exported",
      return_value=state,
  )


def test_runs_client_bigquery_methods(db_session):
  # db_session for the schema alone. The recorded export failure is a column
  # on the run now, so the status call reads the runs table, and without one
  # the whole call falls into its own error handler and reports the run as
  # failed. Run 123 is still absent, which is the case being asserted: a run
  # with no recorded failure has none.
  del db_session

  client = RunsClient()

  with mock.patch.object(settings, "bigquery_export_enabled", False):
    status = client.get_bigquery_export_status(123)
    assert status["enabled"] is False
    assert status["exported"] is False

    with pytest.raises(ValueError, match="not enabled"):
      client.sync_run_to_bigquery(123)

  with mock.patch.object(settings, "bigquery_export_enabled", True):
    with _check_returns(bq_mod.EXPORT_STATE_EXPORTED):
      status = client.get_bigquery_export_status(123)
      assert status["enabled"] is True
      assert status["exported"] is True
      assert status["failed"] is False
      assert status["error"] is None

    with _check_returns(bq_mod.EXPORT_STATE_NOT_EXPORTED):
      with mock.patch(
          "prism.server.services.bigquery_exporter.get_run_export_error",
          return_value="Quota exceeded",
      ):
        status = client.get_bigquery_export_status(123)
        assert status["enabled"] is True
        assert status["exported"] is False
        assert status["failed"] is True
        assert status["error"] == "Quota exceeded"

    with _check_returns(bq_mod.EXPORT_STATE_NOT_EXPORTED):
      with mock.patch(
          "prism.server.services.bigquery_exporter.is_run_syncing",
          return_value=True,
      ):
        status = client.get_bigquery_export_status(123)
        assert status["enabled"] is True
        assert status["exported"] is False
        assert status["syncing"] is True

    with mock.patch(
        "prism.server.services.bigquery_exporter.BigQueryExporter.export_run_async"
    ) as mock_async:
      mock_async.return_value = mock.MagicMock()
      result = client.sync_run_to_bigquery(123)
      assert result["status"] == "export_triggered"
      assert result["is_in_flight"] is True


def _exporter_rejecting(table: str) -> tuple[BigQueryExporter, mock.MagicMock]:
  """An exporter whose insert into ``table`` comes back with a row error.

  The other three tables take everything, which is the shape of the real
  failure: one oversized row, or one column that drifted, in one table.
  """
  client = mock.MagicMock()
  client.project = "test-project"

  def insert_rows_json(table_ref, rows, row_ids=None):
    del rows, row_ids
    if table_ref.table_id != table:
      return []
    return [{
        "index": 0,
        "errors": [{"reason": "rowTooLarge", "message": "Row is too large."}],
    }]

  client.insert_rows_json.side_effect = insert_rows_json
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )
  return exporter, client


def test_a_rejected_trace_row_still_writes_the_run_row(
    db_session: orm.Session, sample_run_data: int
):
  """Without the run row the rows that did land had nothing to join to.

  A trace event over the request cap is skipped by _insert_chunked, and that
  used to hold the run row back. Nothing else records that the export ran, so
  the run kept reading as never exported.
  """
  exporter, client = _exporter_rejecting("prism_eval_traces")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    stats = exporter.export_run(sample_run_data, db_session)

  written = [c.args[0].table_id for c in client.insert_rows_json.call_args_list]
  assert written[-1] == "prism_eval_runs"
  assert stats["runs"] == 1
  assert stats["traces"] == 1, "the trace that fit still had to go"
  # The partial failure is still the answer the caller and the badge get.
  assert "traces" in bq_mod.get_run_export_error(sample_run_data)


def test_a_half_exported_run_is_not_exported_again_without_force(
    db_session: orm.Session, sample_run_data: int
):
  """A run held back from the runs table was re-exported in full every time.

  The rows go in through the streaming API, so a second export appends a copy
  of every trial, assertion and trace rather than replacing them: the
  deduplication window is about a minute, and rows in the streaming buffer
  cannot be deleted for some time after they land. Three presses of Sync to
  BigQuery left three copies of a 39 trial run.
  """
  exporter, client = _exporter_rejecting("prism_eval_traces")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(sample_run_data, db_session)
  client.insert_rows_json.reset_mock()

  stats = exporter.export_run(sample_run_data, db_session)

  assert not client.insert_rows_json.called
  assert stats == {"runs": 0, "trials": 0, "assertions": 0, "traces": 0}


def test_the_scored_population_is_exported_beside_the_accuracy(
    db_session: orm.Session, sample_run_data: int
):
  """accuracy and total_trials are counted over different populations.

  Run.accuracy leaves out a COMPLETED trial whose example has no weighted
  assertion. A row reading accuracy 1.0 over total_trials 2 described one
  correct answer out of one scored, and nothing downstream could recover the
  one.
  """
  run = db_session.get(Run, sample_run_data)
  db_session.add(
      Trial(
          run_id=run.id,
          example_snapshot_id=run.trials[0].example_snapshot_id,
          status=RunStatus.COMPLETED,
          created_at=run.created_at,
      )
  )
  db_session.commit()
  db_session.refresh(run)

  record = BigQueryExporter(client=mock.MagicMock()).serialize_run(run)

  assert record["accuracy"] == 1.0, (
      "Fixture is wrong, not the exporter: the unscored trial is outside the"
      " average."
  )
  assert record["total_trials"] == 2
  assert record["scored_trials"] == 1


def test_every_field_of_an_exported_run_is_declared_in_the_table(
    db_session: orm.Session, sample_run_data: int
):
  """A column the table has never heard of is rejected row by row.

  scored_trials was added to serialize_run, and a run row carrying a field the
  schema does not declare comes back as "no such field" for every run.
  """
  mock_client = mock.MagicMock()
  mock_client.project = "test-project"
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=mock_client
  )

  exporter.ensure_dataset_and_tables()
  tables = {
      call.args[0].table_id: call.args[0]
      for call in mock_client.create_table.call_args_list
  }
  declared = {field.name for field in tables["prism_eval_runs"].schema}

  run = db_session.get(Run, sample_run_data)
  assert set(exporter.serialize_run(run)) <= declared


def _cli_module():
  """The export CLI, loaded by path: scripts/ is not a package."""
  path = os.path.join(
      os.path.dirname(
          os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
      ),
      "scripts",
      "export_to_bigquery.py",
  )
  spec = importlib.util.spec_from_file_location("export_to_bigquery", path)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


def test_the_cli_sign_off_names_what_it_counted(
    db_session: orm.Session, sample_run_data: int
):
  """export_run returns rows accepted, and the last line said offered.

  An export where BigQuery rejected two of 39 trial rows printed "Offered 37
  trials", which is neither the number offered nor a name for the number
  printed beside it.
  """
  cli = _cli_module()

  class _SessionCtx:

    def __enter__(self):
      return db_session

    def __exit__(self, *exc_info):
      return False

  argv = [
      "export_to_bigquery.py",
      "--run-id",
      str(sample_run_data),
      "--project",
      "test-p",
      "--dataset",
      "test-d",
  ]
  with (
      mock.patch.object(sys, "argv", argv),
      mock.patch.object(cli.db, "SessionLocal", return_value=_SessionCtx()),
      mock.patch.object(cli, "BigQueryExporter") as exporter_class,
      mock.patch.object(cli, "get_run_export_error", return_value=None),
      mock.patch.object(cli, "logger") as log,
  ):
    exporter_class.return_value.dataset_id = "test-d"
    exporter_class.return_value.export_run.return_value = {
        "runs": 1,
        "trials": 37,
        "assertions": 0,
        "traces": 0,
    }
    cli.main()

  sign_off = log.info.call_args_list[-1].args[0]
  assert "Offered" not in sign_off
  assert "accepted" in sign_off
