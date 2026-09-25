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

"""What the Avg Trial Duration card on the run-detail page averages over.

The card shipped averaging over every trial in the run, pending ones included:
each unstarted trial contributed a 0 to the sum and a 1 to the denominator. Two
of ten trials done at 20s each read 4.00s, and the page repolls every three
seconds, so the number crept up through the whole run and only landed on the
truth at the end. The average is over the trials that have run.

Every other caller of ``render_run_detail_components`` passes ``trials=[]``, so
the arithmetic itself has no coverage anywhere else.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest import mock

import dash_mantine_components as dmc
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.execution import Trial
from prism.server.config import settings
from prism.ui.callbacks.evaluation_callbacks import render_run_detail_components
from prism.ui.models.ui_state import RunDetailPageState
import pytest

# Index of the stat cards in the callback's output tuple, which is ordered to
# match the output=[...] list on the decorator.
_STATS = 1

_CREATED_AT = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)


@pytest.fixture(name="export_disabled", autouse=True)
def _export_disabled():
  """Keeps the BigQuery badge out of it. This is a test about arithmetic."""
  with mock.patch.object(settings, "bigquery_export_enabled", False):
    yield


def _trial(trial_id: int, status: RunStatus, duration_ms: int | None) -> Trial:
  return Trial(
      id=trial_id,
      run_id=1,
      example_snapshot_id=1,
      status=status,
      duration_ms=duration_ms,
      created_at=_CREATED_AT,
  )


def _avg_duration(trials: list[Trial]) -> str:
  """Renders the run-detail page and returns the Avg Trial Duration value."""
  run = RunSchema(
      id=1,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=RunStatus.RUNNING,
      created_at=_CREATED_AT,
  )
  state = RunDetailPageState(run=run, trials=trials).model_dump(mode="json")

  stats = render_run_detail_components(state, None)[_STATS]

  return _card_value(stats, "Avg Trial Duration")


def _card_value(stats: list[Any], title: str) -> str:
  """Digs the value out of the stat card titled ``title``.

  Found by title, not by position. A card inserted above this one would
  otherwise move the assertions onto somebody else's number.
  """
  for card in stats:
    heading, value = card.children[0], card.children[1]
    if heading.children[1].children == title:
      assert isinstance(value, dmc.Text), f"{title} is not a plain value card"
      return value.children
  raise AssertionError(f"no stat card titled {title!r}")


def test_pending_trials_are_not_averaged_in():
  """Two trials done at 20s each is 20s, not 4s across ten.

  This is the shipped bug. A pending trial has no duration, so it belongs in
  neither half of the fraction, and putting it in the denominator alone made
  the card read low and climb as the run went on.
  """
  trials = [
      _trial(1, RunStatus.COMPLETED, 20_000),
      _trial(2, RunStatus.COMPLETED, 20_000),
  ] + [_trial(i, RunStatus.PENDING, None) for i in range(3, 11)]

  assert _avg_duration(trials) == "20.00s"


def test_the_denominator_is_the_durations_not_a_count_of_statuses():
  """A trial that failed before it started has a status but no duration.

  The page keeps a second count of finished trials, COMPLETED and FAILED
  together, and that is the other tempting denominator. Here the three
  candidates all give different answers: 5000 over the two durations is 2.50s,
  over the three finished trials 1.67s, over all four 1.25s.
  """
  trials = [
      _trial(1, RunStatus.COMPLETED, 1_000),
      _trial(2, RunStatus.COMPLETED, 4_000),
      _trial(3, RunStatus.FAILED, None),
      _trial(4, RunStatus.PENDING, None),
  ]

  assert _avg_duration(trials) == "2.50s"


def test_a_run_where_nothing_has_started_reads_zero():
  """Nothing has run, so there is no average. It must not divide by zero."""
  trials = [_trial(i, RunStatus.PENDING, None) for i in range(1, 4)]

  assert _avg_duration(trials) == "0.00s"


def test_a_run_with_no_trials_reads_zero():
  """The state every other unit caller of this callback passes."""
  assert _avg_duration([]) == "0.00s"
