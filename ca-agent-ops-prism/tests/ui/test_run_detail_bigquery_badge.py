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

"""What the run-detail page is allowed to ask BigQuery, and what it may claim.

The BigQuery badge is rendered inside ``render_run_detail_components``, which
a 3-second polling interval re-runs for as long as a run is unfinished.
Anything expensive in that function costs once per tick per open tab, and
``check_run_exported`` is a query job. So most of what these tests check is that
the page holds back. A unit test is the only place to check it: the E2E specs
run with the export disabled and nothing else counts the calls.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest import mock

import dash_mantine_components as dmc
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.config import settings
from prism.server.services import bigquery_exporter
from prism.ui.callbacks.evaluation_callbacks import render_run_detail_components
from prism.ui.models.ui_state import RunDetailPageState
import pytest

# Index of the BigQuery badge in the callback's output tuple, which is ordered
# to match the ``output=[...]`` list on the decorator.
_BQ_BADGE = 6
# Index of the "Sync to BigQuery" button's style.
_SYNC_BUTTON_STYLE = 10


def _run_data(status: RunStatus) -> dict[str, Any]:
  """The RUN_DATA_STORE payload for a run in the given status."""
  run = RunSchema(
      id=99,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=status,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
  )
  return RunDetailPageState(run=run, trials=[]).model_dump(mode="json")


def _badge_text(component: Any) -> str:
  """Digs the label out of the Tooltip-wrapped Badge the callback returns."""
  badge = component.children
  assert isinstance(badge, dmc.Badge), f"Expected a Badge, got {type(badge)}"
  return badge.children


@pytest.fixture(autouse=True)
def _schema(db_session):
  """Gives every test in this file the run table.

  The recorded export failure moved from a process global onto the run row, so
  get_run_export_error opens its own session now. These tests never needed a
  database before. Without the schema that read raises, and the status call
  reports any error as a failed export, so every badge here came back
  "BQ: Failed", the happy path included.
  """
  del db_session


@pytest.fixture(name="export_enabled")
def _export_enabled():
  """Turns the feature on for the duration of a test."""
  with mock.patch.object(settings, "bigquery_export_enabled", True):
    yield


@pytest.fixture(name="exported_check")
def _exported_check():
  """Counts and controls every question put to BigQuery."""
  with mock.patch(
      "prism.server.services.bigquery_exporter.BigQueryExporter"
      ".check_run_exported",
      return_value=bigquery_exporter.EXPORT_STATE_NOT_EXPORTED,
  ) as patched:
    yield patched


@pytest.mark.parametrize(
    "status",
    [
        RunStatus.PENDING,
        RunStatus.RUNNING,
        RunStatus.EXECUTING,
        RunStatus.EVALUATING,
        RunStatus.PAUSED,
    ],
)
def test_an_unfinished_run_is_never_looked_up_in_bigquery(
    status: RunStatus, export_enabled, exported_check
):
  """These are exactly the statuses that keep the 3s poll running.

  Export is triggered when a run reaches COMPLETED, so for all of these the
  answer is "no" without asking, and asking bills a query job every three
  seconds to hear it.
  """
  render_run_detail_components(_run_data(status), None)

  assert (
      not exported_check.called
  ), f"A {status.value} run cannot be in BigQuery yet, but the page asked."


def test_a_finished_run_is_looked_up(export_enabled, exported_check):
  """The restraint above must not turn into never checking at all."""
  render_run_detail_components(_run_data(RunStatus.COMPLETED), None)

  assert exported_check.called


def test_an_unfinished_run_reads_as_pending(export_enabled, exported_check):
  """Not yet exported, and honest that it is waiting on the run."""
  result = render_run_detail_components(_run_data(RunStatus.RUNNING), None)

  assert _badge_text(result[_BQ_BADGE]) == "BQ: Pending"


def test_a_finished_unexported_run_does_not_claim_to_be_syncing(
    export_enabled, exported_check
):
  """Nothing is in flight, so the badge must not show a spinner.

  This branch used to be shared with "syncing", so any completed run not in
  BigQuery showed "BQ: Syncing" forever. Polling is off once a run completes,
  so nothing would ever correct it, and no thread was doing the transfer.
  """
  result = render_run_detail_components(_run_data(RunStatus.COMPLETED), None)

  assert _badge_text(result[_BQ_BADGE]) == "BQ: Not Synced"
  assert result[_SYNC_BUTTON_STYLE] == {"display": "block"}, (
      "The badge says it is not synced, so the button that syncs it has to be"
      " on screen."
  )


def test_a_run_in_flight_reads_as_syncing(export_enabled, exported_check):
  """A run mid-export must not read as unsynced, or it gets synced twice."""
  with mock.patch(
      "prism.server.services.bigquery_exporter.is_run_syncing",
      return_value=True,
  ):
    result = render_run_detail_components(_run_data(RunStatus.COMPLETED), None)

  assert _badge_text(result[_BQ_BADGE]) == "BQ: Syncing"


def test_an_exported_run_reads_as_synced(export_enabled, exported_check):
  """The happy path still resolves to the green badge."""
  exported_check.return_value = bigquery_exporter.EXPORT_STATE_EXPORTED

  result = render_run_detail_components(_run_data(RunStatus.COMPLETED), None)

  assert _badge_text(result[_BQ_BADGE]) == "BQ: Synced"
  assert result[_SYNC_BUTTON_STYLE] == {"display": "none"}


def test_a_check_that_could_not_complete_says_so(
    export_enabled, exported_check
):
  """A denied or broken lookup is its own answer, not a "no".

  It used to fold into "not exported", so a permissions error on the check
  painted a finished run as never exported and said so flatly. The Sync button
  still shows: the run may well need exporting, and the export skips a run that
  is already there.
  """
  exported_check.return_value = bigquery_exporter.EXPORT_STATE_UNKNOWN

  result = render_run_detail_components(_run_data(RunStatus.COMPLETED), None)

  assert _badge_text(result[_BQ_BADGE]) == "BQ: Unknown"
  assert result[_SYNC_BUTTON_STYLE] == {"display": "block"}


def test_the_disabled_feature_costs_nothing(exported_check):
  """With the export off, the page must not reach for BigQuery at all."""
  with mock.patch.object(settings, "bigquery_export_enabled", False):
    result = render_run_detail_components(_run_data(RunStatus.COMPLETED), None)

  assert not exported_check.called
  assert _badge_text(result[_BQ_BADGE]) == "BQ: Disabled"
  assert result[_SYNC_BUTTON_STYLE] == {"display": "none"}
