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

"""Where a failed BigQuery export is remembered.

The exporter kept its failures in a module-level dict. Two things followed from
that. A restart between the failure and the next look at the run page lost it,
and the badge went green over a warehouse that was missing its trials. And a
second server process never saw it at all, so the same run read as failed in
one worker and clean in the other.

The failure is a column on the run row now. These pin the two cases the
process global could not cover, and the clearing of it, which is the part a
durable record gets wrong in the other direction.

tests/services/test_bigquery_partial_failure.py covers what counts as a
failure. This file covers only where it is kept.
"""

from __future__ import annotations

import datetime
from unittest import mock

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services import bigquery_exporter
from prism.server.services.bigquery_exporter import BigQueryExporter
import pytest
from sqlalchemy import orm

_ROW_ERROR = [{
    "index": 0,
    "errors": [{"reason": "invalid", "message": "no such field: output_text."}],
}]


@pytest.fixture(name="run_id")
def _run_id(db_session: orm.Session) -> int:
  """A finished run of one trial and one assertion."""
  agent = Agent(
      name="Export Persistence Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-persist",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Persistence Suite", description="")
  db_session.add(suite_snapshot)
  db_session.flush()

  example_snapshot = ExampleSnapshot(
      snapshot_suite_id=suite_snapshot.id,
      question="How many orders shipped?",
      logical_id="ex-persist",
  )
  db_session.add(example_snapshot)
  db_session.flush()

  assertion_snapshot = AssertionSnapshot(
      example_snapshot_id=example_snapshot.id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
      params={"value": "orders"},
  )
  db_session.add(assertion_snapshot)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snapshot.id,
      status=RunStatus.COMPLETED,
      created_at=now,
      started_at=now,
      completed_at=now + datetime.timedelta(seconds=5),
  )
  db_session.add(run)
  db_session.flush()

  trial = Trial(
      run_id=run.id,
      example_snapshot_id=example_snapshot.id,
      status=RunStatus.COMPLETED,
      output_text="412 orders shipped.",
      created_at=now,
      started_at=now,
      completed_at=now + datetime.timedelta(seconds=2),
      trace_results=[{"type": "model_output", "timestamp": now.isoformat()}],
  )
  db_session.add(trial)
  db_session.flush()

  db_session.add(
      AssertionResult(
          trial_id=trial.id,
          assertion_snapshot_id=assertion_snapshot.id,
          passed=True,
          score=1.0,
          reasoning="Matched.",
      )
  )
  db_session.commit()
  return run.id


def _exporter(rejected_table: str | None) -> BigQueryExporter:
  """An exporter whose insert of rejected_table comes back with a row error."""
  client = mock.MagicMock()
  client.project = "test-project"

  def insert_rows_json(table_ref, rows, row_ids=None):
    del rows, row_ids
    return _ROW_ERROR if table_ref.table_id == rejected_table else []

  client.insert_rows_json.side_effect = insert_rows_json
  return BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )


def _export(exporter: BigQueryExporter, run_id: int, session: orm.Session):
  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    return exporter.export_run(run_id, session)


def test_the_failure_outlives_the_process_that_saw_it(
    db_session: orm.Session, run_id: int
):
  """reset_export_state is the restart. The record has to be on the row."""
  _export(_exporter("prism_eval_trials"), run_id, db_session)
  assert bigquery_exporter.get_run_export_error(run_id)

  bigquery_exporter.reset_export_state()

  error = bigquery_exporter.get_run_export_error(run_id)
  assert error is not None, "A restart lost the failure, so the badge lies"
  assert "trials" in error


def test_another_process_reads_the_same_failure(
    db_session: orm.Session, session_factory: orm.sessionmaker, run_id: int
):
  """The UI and the worker are separate processes in a deployed prism."""
  _export(_exporter("prism_eval_trials"), run_id, db_session)

  with session_factory() as other_process:
    run = other_process.get(Run, run_id)
    assert run.bigquery_export_error is not None
    assert "trials" in run.bigquery_export_error


def test_a_clean_export_clears_the_stored_failure(
    db_session: orm.Session, run_id: int
):
  """Durable is only useful if the retry that fixed it is durable too."""
  _export(_exporter("prism_eval_trials"), run_id, db_session)
  assert bigquery_exporter.get_run_export_error(run_id)

  _export(_exporter(None), run_id, db_session)

  assert bigquery_exporter.get_run_export_error(run_id) is None


def test_a_background_export_that_raises_records_why(
    db_session: orm.Session, session_factory: orm.sessionmaker, run_id: int
):
  """The thread is the only caller, so an unrecorded raise is lost entirely."""
  del db_session
  exporter = _exporter(None)
  with mock.patch.object(
      exporter, "export_run", side_effect=RuntimeError("dataset is gone")
  ):
    thread = exporter.export_run_async(run_id, session_factory)
    thread.join(timeout=30)

  assert not thread.is_alive()
  # The stored message names the type and sends the reader to the log. The
  # exception text itself carries project ids and dataset names, and this
  # string is rendered on the run page.
  stored = bigquery_exporter.get_run_export_error(run_id)
  assert "RuntimeError" in stored
  assert "dataset is gone" not in stored


def test_a_run_with_no_failure_reads_as_none(
    db_session: orm.Session, run_id: int
):
  del db_session
  assert bigquery_exporter.get_run_export_error(run_id) is None


def test_a_run_that_does_not_exist_reads_as_none(db_session: orm.Session):
  """The badge asks about whatever id is in the URL."""
  # db_session for the schema alone. get_run_export_error opens its own.
  del db_session
  assert bigquery_exporter.get_run_export_error(-1) is None
