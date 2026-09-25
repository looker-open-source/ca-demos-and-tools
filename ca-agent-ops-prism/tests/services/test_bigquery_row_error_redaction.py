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

"""What a rejected row is allowed to say on the run page.

``insert_rows_json`` answers with one dict per rejected row, and each carries
``reason``, ``location``, ``debugInfo`` and ``message``. The exporter used to
format that whole structure into the error it stores on the run, and the run
page renders the stored error verbatim in the BigQuery badge tooltip. debugInfo
is a backend diagnostic and the message names the offending column, so a schema
drift put the warehouse's internals in front of whoever opened the run.

The count is what the reader can act on: which table lost rows, and how many.
The rest belongs in the server log, which is where ``_displayable_error``
already puts everything else the exporter fails on.

``tests/services/test_bigquery_partial_failure.py`` covers the rest of the
partial export, including the badge that reads this error.
"""

from __future__ import annotations

import datetime
import logging
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

# Position in render_run_detail_components' output tuple, which is ordered to
# match the output=[...] list on its decorator.
_BQ_BADGE = 6

# Two rejected rows, in the shape the streaming API returns. Every string here
# is distinctive, so a test can say which part of the structure leaked.
_ROW_ERRORS = [
    {
        "index": 0,
        "errors": [{
            "reason": "invalid",
            "location": "output_text",
            "debugInfo": "generic::internal: backend shard 44 refused",
            "message": "no such field: output_text.",
        }],
    },
    {
        "index": 1,
        "errors": [{
            "reason": "invalid",
            "location": "output_text",
            "debugInfo": "generic::internal: backend shard 44 refused",
            "message": "no such field: output_text.",
        }],
    },
]

_LEAKED = [
    "debugInfo",
    "backend shard 44",
    "generic::internal",
    "no such field",
    "output_text",
    "reason",
    "location",
]


@pytest.fixture(name="run_id")
def _run_id(db_session: orm.Session) -> int:
  """A finished run of one trial and one assertion snapshot."""
  agent = Agent(
      name="Redaction Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-redaction",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Redaction Suite", description="")
  db_session.add(suite_snapshot)
  db_session.flush()

  example_snapshot = ExampleSnapshot(
      snapshot_suite_id=suite_snapshot.id,
      question="How many orders shipped?",
      logical_id="ex-redaction",
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
  )
  db_session.add(trial)
  db_session.flush()

  # An assertion result as well as a trial, because the exporter skips a table
  # it has no rows for and one of these tests rejects two tables at once.
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


def _export_rejecting(db_session: orm.Session, run_id: int, *tables: str):
  """Runs an export whose inserts into ``tables`` come back with row errors."""
  client = mock.MagicMock()
  client.project = "test-project"

  def insert_rows_json(table_ref, rows, row_ids=None):
    del rows, row_ids
    return _ROW_ERRORS if table_ref.table_id in tables else []

  client.insert_rows_json.side_effect = insert_rows_json
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )
  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)


def test_the_recorded_error_counts_the_rejected_rows(
    db_session: orm.Session, run_id: int
):
  """The table and the count, and nothing the backend said about why."""
  _export_rejecting(db_session, run_id, "prism_eval_trials")

  error = bigquery_exporter.get_run_export_error(run_id)

  assert error is not None, "a rejected row is a failed export"
  assert "trials: 2" in error
  for leaked in _LEAKED:
    assert leaked not in error, f"{leaked!r} came from the row error dicts"


def test_every_table_that_lost_rows_is_named(
    db_session: orm.Session, run_id: int
):
  """Four tables are written, and a schema drift can hit more than one.

  Reporting only the first would send a retry back to a table that is already
  fine while the other one goes on failing.
  """
  _export_rejecting(
      db_session, run_id, "prism_eval_trials", "prism_eval_assertion_results"
  )

  error = bigquery_exporter.get_run_export_error(run_id)

  assert "trials: 2" in error
  assert "assertions: 2" in error


def test_the_error_says_where_the_detail_went(
    db_session: orm.Session, run_id: int, caplog
):
  """Dropping the detail is only safe if it is written down somewhere.

  The log line is the one copy of the row errors, so the text on the page has
  to send the reader to it.
  """
  with caplog.at_level(logging.ERROR):
    _export_rejecting(db_session, run_id, "prism_eval_trials")

  error = bigquery_exporter.get_run_export_error(run_id)
  assert "server log" in error

  logged = " ".join(r.getMessage() for r in caplog.records)
  assert "BigQuery export encountered errors" in logged
  assert "no such field" in logged, "the detail was dropped, not moved"


def test_the_badge_tooltip_shows_the_stored_error_as_it_is(
    db_session: orm.Session, run_id: int
):
  """The page is why the stored text matters: it is rendered unchanged.

  Nothing between the run row and the tooltip trims anything, so whatever the
  exporter stored is what the reader sees on hover.
  """
  _export_rejecting(db_session, run_id, "prism_eval_trials")

  run = RunSchema(
      id=run_id,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime.now(datetime.timezone.utc),
  )
  # An exported answer is forced, so the tooltip is rendered on the branch
  # that shows the stored error. Patched on check_run_exported, which is what
  # run_client calls: patching is_run_exported instead lets the render path
  # build a live client and issue a query job.
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

  label = rendered[_BQ_BADGE].label
  assert "trials: 2" in label
  for leaked in _LEAKED:
    assert leaked not in label, f"{leaked!r} reached the run page"
