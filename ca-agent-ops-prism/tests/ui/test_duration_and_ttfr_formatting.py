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

"""Tests for Duration and TTFR formatting in UI tables and cards."""

from __future__ import annotations

import datetime
from typing import Any, Iterator

from dash import html
import dash_mantine_components as dmc
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.execution import Trial
from prism.ui.components import tables
from prism.ui.utils import format_duration
from prism.ui.utils import format_ttfr
import pytest


def _walk(component: Any) -> Iterator[Any]:
  """Yields every component in a rendered tree, depth first."""
  yield component
  children = getattr(component, "children", None)
  if children is None:
    return
  if not isinstance(children, (list, tuple)):
    children = [children]
  for child in children:
    if child is not None and not isinstance(child, (str, int, float)):
      yield from _walk(child)


def test_format_duration_converts_ms_to_minutes_and_seconds():
  assert format_duration(None) == "-"
  assert format_duration(0) == "0m 0s"
  assert format_duration(500) == "0m 0s"
  assert format_duration(13751) == "0m 13s"
  assert format_duration(60000) == "1m 0s"
  assert format_duration(95000) == "1m 35s"
  assert format_duration(125400) == "2m 5s"


def test_format_ttfr_converts_ms_to_seconds_with_tenths():
  assert format_ttfr(None) == "-"
  assert format_ttfr(0) == "0.0s"
  assert format_ttfr(500) == "0.5s"
  assert format_ttfr(2713) == "2.7s"
  assert format_ttfr(2015) == "2.0s"
  assert format_ttfr(13751) == "13.8s"


def test_render_trial_table_formats_duration_and_ttfr():
  now = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc)
  trial_with_metrics = Trial(
      id=1,
      run_id=1,
      example_snapshot_id=1,
      question="What is the revenue?",
      status=RunStatus.COMPLETED,
      duration_ms=13751,
      ttfr_ms=2713,
      score=1.0,
      created_at=now,
  )
  trial_without_metrics = Trial(
      id=2,
      run_id=1,
      example_snapshot_id=1,
      question="What is the churn?",
      status=RunStatus.PENDING,
      duration_ms=None,
      ttfr_ms=None,
      score=None,
      created_at=now,
  )

  paper = tables.render_trial_table([trial_with_metrics, trial_without_metrics])
  body = next(c for c in _walk(paper) if isinstance(c, html.Tbody))
  rows = body.children
  assert len(rows) == 2

  row1_cells = rows[0].children
  # Cell 3 is TTFR, Cell 4 is Duration
  assert row1_cells[3].children.children == "2.7s"
  assert row1_cells[4].children.children == "0m 13s"

  row2_cells = rows[1].children
  assert row2_cells[3].children.children == "-"
  assert row2_cells[4].children.children == "-"


def test_render_run_table_formats_duration():
  run_with_duration = RunSchema(
      id=1,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      duration_ms=95000,
  )
  run_without_duration = RunSchema(
      id=2,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=RunStatus.PENDING,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      duration_ms=None,
  )

  table = tables.render_run_table([run_with_duration, run_without_duration])
  body = next(c for c in _walk(table) if isinstance(c, html.Tbody))
  rows = body.children
  assert len(rows) == 2

  # Cell 5 is DURATION in render_run_table
  row1_cells = rows[0].children
  assert row1_cells[5].children.children == "1m 35s"

  row2_cells = rows[1].children
  assert row2_cells[5].children.children == "Pending"
