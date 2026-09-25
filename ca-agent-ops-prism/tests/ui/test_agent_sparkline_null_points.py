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

"""The HISTORY sparkline leaves out the runs that scored nothing.

A queued or cancelled run has no accuracy. It used to arrive here as 0.0,
because the history point was typed float, and the sparkline plotted it: one
run still sitting in the queue dropped the last point to the floor and turned
the trend red. The "Last eval" cell on the same row was already reading "--"
for that run, so the two halves of the row disagreed.
"""

from __future__ import annotations

import datetime
from typing import Any

from prism.common.schemas.execution import RunHistoryPoint
from prism.server.models.agent import Agent
from prism.ui.components import tables

_T0 = datetime.datetime(2026, 3, 1, 9, 0, tzinfo=datetime.timezone.utc)


def _point(index: int, accuracy: float | None) -> RunHistoryPoint:
  return RunHistoryPoint(
      run_id=index,
      created_at=_T0 + datetime.timedelta(days=index),
      accuracy=accuracy,
  )


def _sparkline_data(history: list[RunHistoryPoint]) -> list[float] | None:
  """The data the one rendered Sparkline carries, or None if there is none."""
  agent = Agent(
      id=1, name="Agent", project_id="p", location="l", agent_resource_id="r"
  )
  table = tables.render_agent_table([agent], {}, {1: history})

  found = [node for node in _walk(table) if _is_sparkline(node)]
  if not found:
    return None
  assert len(found) == 1, f"{len(found)} sparklines rendered"
  return found[0].data


def _is_sparkline(node: Any) -> bool:
  return type(node).__name__ == "Sparkline"


def _walk(node: Any):
  """Every Dash component under ``node``, this one included."""
  yield node
  children = getattr(node, "children", None)
  if children is None:
    return
  if not isinstance(children, (list, tuple)):
    children = [children]
  for child in children:
    if hasattr(child, "children") or _is_sparkline(child):
      yield from _walk(child)


def test_a_run_with_no_accuracy_is_left_off_the_sparkline():
  data = _sparkline_data([_point(1, 0.8), _point(2, None), _point(3, 0.9)])

  assert data == [80.0, 90.0]


def test_a_history_of_nothing_but_unscored_runs_draws_no_sparkline():
  """Zeros would have drawn a flat line along the bottom instead."""
  assert _sparkline_data([_point(1, None), _point(2, None)]) is None


def test_the_scored_runs_are_still_plotted():
  """So the fix cannot be to stop drawing the sparkline."""
  assert _sparkline_data([_point(1, 0.25), _point(2, 1.0)]) == [25.0, 100.0]
