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

"""How a large run is streamed to BigQuery, and in what order the tables go.

insert_rows_json is one HTTP POST and BigQuery caps it at 10 MB. Each table
used to go in a single call, so a 40-trial run with one large result payload in
a trace event built a request that was rejected whole, and the run landed with
no traces at all.

The order matters for the same reason. The run row is what is_run_exported
looks for, and it used to be written first: an insert that raised part way
through left a run that reads as exported with its traces missing. The only way
back is force=True, which appends a second copy of every row and makes every
average downstream count the run twice. It goes last now, so an insert that
raises stops the export before the run is claimed.

An insert that returns per-row errors rather than raising is the other case,
and it is handled the other way round: see test_bigquery_partial_failure.py.
"""

from __future__ import annotations

import datetime
from unittest import mock

from google.api_core import exceptions
from google.cloud import bigquery
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.bigquery_exporter import BigQueryExporter
import pytest
from sqlalchemy import orm

_TRACES = bigquery.DatasetReference("test-project", "test_dataset").table(
    "prism_eval_traces"
)


def _exporter(client: mock.MagicMock) -> BigQueryExporter:
  return BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )


def _client() -> mock.MagicMock:
  client = mock.MagicMock()
  client.project = "test-project"
  client.insert_rows_json.return_value = []
  return client


def _sent_rows(client: mock.MagicMock, table_id: str) -> list[list[dict]]:
  """The row lists sent to one table, one entry per request."""
  return [
      call.args[1]
      for call in client.insert_rows_json.call_args_list
      if call.args[0].table_id == table_id
  ]


def test_more_rows_than_one_request_holds_are_split_across_requests():
  """A 40-trial run with a long trace is thousands of rows in one POST."""
  client = _client()
  rows = [{"trial_id": 1, "step_index": i} for i in range(1200)]
  row_ids = [f"trace-1-{i}" for i in range(1200)]

  errors = _exporter(client)._insert_chunked(_TRACES, rows, row_ids)

  assert not errors
  assert [len(chunk) for chunk in _sent_rows(client, "prism_eval_traces")] == [
      500,
      500,
      200,
  ]
  # Every row goes exactly once, and keeps the id that deduplicates a retry.
  sent_ids = [
      row_id
      for call in client.insert_rows_json.call_args_list
      for row_id in call.kwargs["row_ids"]
  ]
  assert sent_ids == row_ids


def test_rows_too_large_for_one_request_are_split_before_they_are_sent():
  """Four rows are under the row limit and over the byte limit.

  This is the shape that broke: a single data event holding a few thousand
  result rows, which is megabytes on its own.
  """
  client = _client()
  rows = [{"payload": "x" * (2 * 1024 * 1024)} for _ in range(4)]
  row_ids = [f"trace-1-{i}" for i in range(4)]

  _exporter(client)._insert_chunked(_TRACES, rows, row_ids)

  chunks = _sent_rows(client, "prism_eval_traces")
  assert len(chunks) > 1
  for chunk in chunks:
    assert sum(len(row["payload"]) for row in chunk) < 5 * 1024 * 1024


def test_a_row_bigger_than_a_whole_request_is_skipped_and_reported():
  """Chunking cannot help here, and sending it alone only loses the chunk.

  A trace event carrying a full query result goes over the request cap on its
  own. It used to be put in a chunk of one and posted, and BigQuery rejected
  the request, so the rows that happened to share the chunk boundary went with
  it. Skipping it costs one row, and the error it leaves is what stops the run
  row being written.
  """
  client = _client()
  rows = [
      {"payload": "x" * 1024},
      {"payload": "x" * (6 * 1024 * 1024)},
      {"payload": "y" * 1024},
  ]
  row_ids = [f"trace-1-{i}" for i in range(3)]

  errors = _exporter(client)._insert_chunked(_TRACES, rows, row_ids)

  assert len(errors) == 1
  assert errors[0]["index"] == 1
  sent = [
      row for chunk in _sent_rows(client, "prism_eval_traces") for row in chunk
  ]
  assert sent == [rows[0], rows[2]], "the two rows that fit still had to go"


def test_the_skipped_row_is_named_in_the_log_not_in_the_error():
  """The error is stored and rendered on the run page, so it carries a size.

  The row id is the only way to find which event it was, and it goes to the
  log with everything else the reader is sent there for.
  """
  client = _client()
  rows = [{"payload": "x" * (6 * 1024 * 1024)}]

  errors = _exporter(client)._insert_chunked(_TRACES, rows, ["trace-9-3"])

  assert errors[0]["errors"][0]["reason"] == "rowTooLarge"
  assert "trace-9-3" not in str(errors)
  assert not client.insert_rows_json.called


@pytest.fixture(name="run_id")
def _run_id(db_session: orm.Session) -> int:
  """A finished run of one trial, one assertion and two trace events."""
  agent = Agent(
      name="Chunking Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-chunk",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Chunking Suite", description="")
  db_session.add(suite_snapshot)
  db_session.flush()

  example_snapshot = ExampleSnapshot(
      snapshot_suite_id=suite_snapshot.id,
      question="How many orders shipped?",
      logical_id="ex-chunk",
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
      trace_results=[
          {"type": "user_input", "timestamp": now.isoformat()},
          {"type": "model_output", "timestamp": now.isoformat()},
      ],
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


def test_the_run_row_is_written_after_everything_that_hangs_off_it(
    db_session: orm.Session, run_id: int
):
  """is_run_exported reads the run row, so it is the commit of the export."""
  client = _client()
  exporter = _exporter(client)

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    exporter.export_run(run_id, db_session)

  written = [
      call.args[0].table_id for call in client.insert_rows_json.call_args_list
  ]
  assert written[-1] == "prism_eval_runs"
  assert "prism_eval_traces" in written


def test_a_rejected_trace_insert_leaves_no_run_row_behind(
    db_session: orm.Session, run_id: int
):
  """The retry path only works while the run still reads as un-exported.

  A run row on top of missing traces is a run nothing will export again, and
  the traces are what the trial timeline is drawn from.
  """
  client = _client()

  def insert_rows_json(table_ref, rows, row_ids=None):
    del rows, row_ids
    if table_ref.table_id == "prism_eval_traces":
      raise exceptions.BadRequest("request payload size exceeds the limit")
    return []

  client.insert_rows_json.side_effect = insert_rows_json
  exporter = _exporter(client)

  with mock.patch.object(exporter, "is_run_exported", return_value=False):
    with pytest.raises(exceptions.BadRequest):
      exporter.export_run(run_id, db_session)

  written = [
      call.args[0].table_id for call in client.insert_rows_json.call_args_list
  ]
  assert "prism_eval_runs" not in written
  # And nothing marked it exported in this process either, which would skip
  # the retry just as effectively as a row in the table.
  assert exporter.is_run_exported(run_id) is False
