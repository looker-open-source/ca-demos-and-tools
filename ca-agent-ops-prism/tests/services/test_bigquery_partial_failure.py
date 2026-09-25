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

"""What a half-written BigQuery export tells the user.

insert_rows_json does not fail as a unit. It returns a list of per-row errors
and keeps the rows it accepted, so one bad trial row leaves the other three
tables written and the trial row out of the warehouse. export_run notices,
writes the run row anyway and records the failure against the run.

Holding the run row back was tried and was worse. check_run_exported only looks
at prism_eval_runs, so a withheld row left the run reading NOT_EXPORTED with the
retry button live, and every press appended another full copy of the trials, the
assertions and the traces while the row that would have stopped it was rejected
again. The orphaned copies join to nothing, so they are invisible to every
run-level query and visible to every trial-level one. Deleting them first is not
open to us either: these are streaming inserts, and rows in the streaming buffer
cannot be removed by DML for some time after they land.

So the run row is written, the failure is recorded on the run, and the two are
read together. The badge is driven by the recorded error, not by the absence of
the row.

test_bigquery_exporter.py covers the all-or-nothing paths and
test_bigquery_export_contract.py covers the memo and the accuracy contract.
This file covers only the partial case. The autouse fixture in
tests/conftest.py clears the exporter's module state around each test.
"""

from __future__ import annotations

import datetime
from unittest import mock

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.config import settings
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services import bigquery_exporter
from prism.server.services.bigquery_exporter import BigQueryExporter
from prism.ui.callbacks.evaluation_callbacks import render_run_detail_components
from prism.ui.models.ui_state import RunDetailPageState
import pytest
from sqlalchemy import orm

# Positions in render_run_detail_components' output tuple, which is ordered to
# match the output=[...] list on its decorator.
_BQ_BADGE = 6
_SYNC_BUTTON_STYLE = 10

# What the streaming API hands back for one rejected row.
_ROW_ERROR = [{
    "index": 0,
    "errors": [{
        "reason": "invalid",
        "message": "no such field: output_text.",
    }],
}]


@pytest.fixture(name="run_id")
def _run_id(db_session: orm.Session) -> int:
  """A finished run of one trial, one assertion and one trace event."""
  agent = Agent(
      name="Partial Export Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-partial",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Partial Suite", description="")
  db_session.add(suite_snapshot)
  db_session.flush()

  example_snapshot = ExampleSnapshot(
      snapshot_suite_id=suite_snapshot.id,
      question="How many orders shipped?",
      logical_id="ex-partial",
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


def _exporter_rejecting(table: str) -> tuple[BigQueryExporter, mock.MagicMock]:
  """An exporter whose insert of ``table`` comes back with a row error.

  Every other table accepts its rows, which is the shape of the real failure:
  the schemas are written per table, so one of them drifts at a time.
  """
  client = mock.MagicMock()
  client.project = "test-project"

  def insert_rows_json(table_ref, rows, row_ids=None):
    del rows, row_ids
    return _ROW_ERROR if table_ref.table_id == table else []

  client.insert_rows_json.side_effect = insert_rows_json
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )
  return exporter, client


def test_a_rejected_trial_row_is_recorded_as_a_failure(
    db_session: orm.Session, run_id: int
):
  """The error has to name the table, since only one of the four broke."""
  exporter, _ = _exporter_rejecting("prism_eval_trials")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)

  error = bigquery_exporter.get_run_export_error(run_id)
  assert error is not None, "A rejected row is a failed export"
  assert "trials" in error
  # The table and a count. The row errors name columns and carry debugInfo,
  # and this string is rendered in the run page tooltip, so they stay in the
  # log. tests/services/test_bigquery_row_error_redaction.py holds that line.
  assert "no such field" not in error


def test_a_rejected_row_does_not_stop_the_remaining_tables(
    db_session: orm.Session, run_id: int
):
  """There is nothing to roll back, so the rest is still worth writing.

  insert_rows_json already kept the rows it accepted, and the run row goes in
  with them so the ones that landed can be joined to it.

  test_bigquery_export_chunking.py covers an insert that raises instead of
  returning errors, where export_run stops before the run row.
  """
  exporter, client = _exporter_rejecting("prism_eval_trials")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)

  written = {c.args[0].table_id for c in client.insert_rows_json.call_args_list}
  assert written == {
      "prism_eval_trials",
      "prism_eval_assertion_results",
      "prism_eval_traces",
      "prism_eval_runs",
  }


def test_the_counts_returned_are_rows_accepted_not_rows_offered(
    db_session: orm.Session, run_id: int
):
  """The CLI sums these and signs off with "Total: N trials".

  Offered counts told it every row landed on an export where BigQuery had
  rejected one, so a half-written warehouse printed as a clean run.
  """
  exporter, _ = _exporter_rejecting("prism_eval_trials")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    stats = exporter.export_run(run_id, db_session)

  assert stats["trials"] == 0, "The one trial row offered was rejected"
  assert stats["assertions"] == 1
  assert stats["traces"] == 1
  assert stats["runs"] == 1, "The run row is written whatever the rest did"
  assert bigquery_exporter.get_run_export_error(run_id) is not None


def test_a_clean_export_counts_every_row_it_wrote(
    db_session: orm.Session, run_id: int
):
  """Accepted and offered are the same number when nothing was rejected."""
  exporter, _ = _exporter_rejecting("no_such_table")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    stats = exporter.export_run(run_id, db_session)

  assert stats == {"runs": 1, "trials": 1, "assertions": 1, "traces": 1}


def test_a_partial_export_is_memoized_from_the_run_row(
    db_session: orm.Session, run_id: int
):
  """The memo tracks the run row, and the run row went in.

  It is not a claim that every row landed. The recorded error is what says
  otherwise, and the automatic paths skip the run so they stop appending a
  fresh copy of the children on every pass.
  """
  exporter, client = _exporter_rejecting("prism_eval_trials")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)

  # No patch this time: the memo is what answers before the query runs.
  client.query.return_value.result.return_value = []
  assert exporter.is_run_exported(run_id) is True
  assert bigquery_exporter.get_run_export_error(run_id) is not None


def test_a_later_clean_export_clears_the_recorded_failure(
    db_session: orm.Session, run_id: int
):
  """Retrying after the schema is fixed has to take the error off the page."""
  exporter, client = _exporter_rejecting("prism_eval_trials")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)
    client.insert_rows_json.side_effect = None
    client.insert_rows_json.return_value = []
    exporter.export_run(run_id, db_session, force=True)

  assert bigquery_exporter.get_run_export_error(run_id) is None


def test_a_half_exported_run_is_not_shown_as_a_clean_success(
    db_session: orm.Session, run_id: int
):
  """The regression this pair of flags was fixed for.

  get_bigquery_export_status used to set failed to `error and not exported`.
  is_run_exported asks whether the run row is present, and a run exported once
  before has one, so the recorded error rode along in the dict and was never
  read. The badge chain in
  evaluation_callbacks tested exported first and rendered a green "BQ: Synced"
  over a warehouse missing its trials, and the same two flags hid the Sync to
  BigQuery button, so the page offered no retry either.

  The badge and the button are read off the page callback, not recomputed from
  the two flags. Recomputing them here passed on a UI that had drifted: the
  order the branches are tested in is the defect, and a copy of the rule
  cannot see the order.
  """
  exporter, _ = _exporter_rejecting("prism_eval_trials")
  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)

  assert "trials" in bigquery_exporter.get_run_export_error(
      run_id
  ), "Fixture is wrong, not the page: the export did fail."

  run = RunSchema(
      id=run_id,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime.now(datetime.timezone.utc),
  )
  # An exported answer is forced, because the badge order is what is on trial
  # here, not how the answer was arrived at. A run row from an earlier export
  # gives the same pair of flags. Patched on check_run_exported, which is what
  # run_client calls. Patching is_run_exported instead did nothing: the render
  # path never reaches it, so the real check ran, built a live bigquery.Client
  # and issued a query job.
  with (
      mock.patch.object(settings, "bigquery_export_enabled", True),
      mock.patch.object(
          BigQueryExporter,
          "check_run_exported",
          return_value=bigquery_exporter.EXPORT_STATE_EXPORTED,
      ),
  ):
    rendered = render_run_detail_components(
        RunDetailPageState(run=run, trials=[]).model_dump(mode="json"), None
    )

  badge = rendered[_BQ_BADGE].children
  assert badge.children == "BQ: Failed", (
      "A run whose trials were rejected is being badged"
      f" {badge.children!r} over a warehouse missing them."
  )
  assert rendered[_SYNC_BUTTON_STYLE] == {
      "display": "block"
  }, "There has to be a way to retry the missing rows."


def test_the_recorded_failure_is_the_only_trace_of_a_partial_export(
    db_session: orm.Session, run_id: int
):
  """What a fix would have to surface, and where it already is.

  The exporter knows the export was incomplete. get_run_export_error reads it
  off the run row, so the record outlives the process that wrote it. Anything
  that wants to show a half-exported run has this to read, without a second
  round trip to BigQuery.
  """
  exporter, _ = _exporter_rejecting("prism_eval_assertion_results")

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)

  assert "assertions" in bigquery_exporter.get_run_export_error(run_id)
