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

"""What the BigQuery export owes the rest of Prism.

Three properties the exporter's own tests don't pin, each of which broke
because the exporter was written independently of the code it has to agree
with:

  * the accuracy it writes is the same accuracy the UI shows;
  * asking whether a run is exported costs a query job, so it is asked as
    rarely as the answer allows;
  * a check that fails is not the same as a run that is absent.

test_bigquery_exporter.py covers the exporter's internals. This file covers its
contract with Run.accuracy and with the UI.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest import mock

from google.api_core import exceptions
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

# An autouse fixture in tests/conftest.py resets the exporter's module-level
# bookkeeping around every test. These tests depend on that, since several
# assert on how many times a run is looked up.


@pytest.fixture(name="run_with_one_pass_one_error")
def _run_with_one_pass_one_error(db_session: orm.Session) -> Run:
  """A finished run of two trials: one scored 1.0, one that crashed.

  The asymmetry is the point. A FAILED trial produces no assertion results, so
  its ``score`` is None, which makes it easy to drop from an average by
  accident.
  """
  agent = Agent(
      name="Contract Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-contract",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Contract Suite", description="")
  db_session.add(suite_snapshot)
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

  for index, trial_status in enumerate((RunStatus.COMPLETED, RunStatus.FAILED)):
    example_snapshot = ExampleSnapshot(
        snapshot_suite_id=suite_snapshot.id,
        question=f"Question {index}?",
        logical_id=f"ex-{index}",
    )
    db_session.add(example_snapshot)
    db_session.flush()

    assertion_snapshot = AssertionSnapshot(
        example_snapshot_id=example_snapshot.id,
        type=AssertionType.TEXT_CONTAINS,
        weight=1.0,
        params={"value": "10"},
    )
    db_session.add(assertion_snapshot)
    db_session.flush()

    trial = Trial(
        run_id=run.id,
        example_snapshot_id=example_snapshot.id,
        status=trial_status,
        created_at=now,
        started_at=now,
        completed_at=now + datetime.timedelta(seconds=2),
    )
    db_session.add(trial)
    db_session.flush()

    if trial_status == RunStatus.COMPLETED:
      db_session.add(
          AssertionResult(
              trial_id=trial.id,
              assertion_snapshot_id=assertion_snapshot.id,
              passed=True,
              score=1.0,
              reasoning="Matched.",
          )
      )
    else:
      trial.error_message = "The agent raised."

  db_session.commit()
  db_session.refresh(run)
  return run


def test_exported_accuracy_is_the_same_accuracy_the_ui_shows(
    run_with_one_pass_one_error: Run,
):
  """serialize_run must not compute its own average.

  One of two trials crashed, so the run scored 50%. The version this replaces
  averaged only over trials with a score, saw a single 1.0, and wrote 100% into
  the warehouse, disagreeing with the run page for the same run.
  """
  run = run_with_one_pass_one_error
  exporter = BigQueryExporter(client=mock.MagicMock())

  record = exporter.serialize_run(run)

  assert run.accuracy == pytest.approx(0.5), (
      "Fixture is wrong, not the exporter: one passing trial and one errored"
      " trial is 50%."
  )
  assert record["accuracy"] == pytest.approx(run.accuracy)


def test_a_run_with_nothing_to_score_exports_a_null_accuracy(
    db_session: orm.Session,
):
  """No weighted assertions anywhere means no accuracy, not zero."""
  agent = Agent(
      name="Unscored Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-unscored",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.flush()
  suite_snapshot = TestSuiteSnapshot(name="Unscored Suite", description="")
  db_session.add(suite_snapshot)
  db_session.flush()
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snapshot.id,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime.now(datetime.timezone.utc),
  )
  db_session.add(run)
  db_session.commit()

  record = BigQueryExporter(client=mock.MagicMock()).serialize_run(run)

  assert record["accuracy"] is None
  assert record["total_trials"] == 0


def _exporter_returning(rows: list[Any]) -> tuple[BigQueryExporter, Any]:
  """An exporter whose is_run_exported query yields ``rows``."""
  client = mock.MagicMock()
  client.project = "test-project"
  client.query.return_value.result.return_value = rows
  return (
      BigQueryExporter(
          project_id="test-project", dataset_id="test_dataset", client=client
      ),
      client,
  )


def test_a_confirmed_export_is_only_looked_up_once():
  """The second question is answered from memory, not from a query job.

  The run-detail page re-renders on every poll tick and on every visit. A run
  in BigQuery cannot leave it, so re-asking spends money to be told the same
  thing.
  """
  exporter, client = _exporter_returning([(1,)])

  assert exporter.is_run_exported(7) is True
  assert exporter.is_run_exported(7) is True
  assert exporter.is_run_exported(7) is True

  assert client.query.call_count == 1


def test_an_absent_run_is_looked_up_again():
  """A negative answer is not cached, since the export may yet happen."""
  exporter, client = _exporter_returning([])

  assert exporter.is_run_exported(7) is False
  assert exporter.is_run_exported(7) is False

  assert client.query.call_count == 2


def test_a_successful_export_records_itself():
  """export_run populates the memo, so the badge needs no query to confirm."""
  exporter, client = _exporter_returning([])
  client.insert_rows_json.return_value = []
  session = mock.MagicMock()
  # A real Run, not a mock. The exporter measures each row with json.dumps to
  # decide where to split the request, and a mock attribute that slipped into a
  # row failed to serialize.
  run = Run(id=42, status=RunStatus.COMPLETED)

  with mock.patch.object(
      bigquery_exporter, "RunRepository"
  ) as repository_class:
    repository_class.return_value.get_by_id.return_value = run
    exporter.export_run(42, session)

  client.query.reset_mock()
  assert exporter.is_run_exported(42) is True
  assert (
      not client.query.called
  ), "The export just wrote the run; confirming it should not cost a query."


def test_a_missing_table_means_not_exported():
  """Nothing has been exported yet, which is an answer, not a failure."""
  client = mock.MagicMock()
  client.project = "test-project"
  client.query.side_effect = exceptions.NotFound("No such table")
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )

  assert exporter.is_run_exported(7) is False


def test_an_unreadable_dataset_is_reported_before_it_is_swallowed(caplog):
  """A denied or broken check still reads False, but must say why.

  Returning False on a permissions error makes a misconfigured export look like
  an ordinary un-exported run. The badge can't show the reason, so the log has
  to.
  """
  client = mock.MagicMock()
  client.project = "test-project"
  client.query.side_effect = exceptions.Forbidden("bigquery.tables.get denied")
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )

  assert exporter.is_run_exported(7) is False
  assert "test_dataset" in caplog.text
  assert "denied" in caplog.text


def test_a_failed_check_is_not_cached_as_exported():
  """An error must not poison the memo into claiming the run is present."""
  client = mock.MagicMock()
  client.project = "test-project"
  client.query.side_effect = exceptions.Forbidden("denied")
  exporter = BigQueryExporter(
      project_id="test-project", dataset_id="test_dataset", client=client
  )

  exporter.is_run_exported(7)
  client.query.side_effect = None
  client.query.return_value.result.return_value = []

  assert exporter.is_run_exported(7) is False
