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

"""The agents list table, driven over Dash's HTTP route.

``update_agent_list`` is fired by the URL and the archived switch, and it is
the only reader of ``get_latest_runs_with_stats``. The LAST EVALUATION cell
pairs that run's date with its accuracy, and the two come from different
places.
"""

from __future__ import annotations

from typing import Any

from prism.common.schemas.assertion import AssertionType
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.ui.pages.agent_ids import AgentIds
from tests.ui import dash_http


def _last_eval(dash_client, agent_id: int) -> str:
  """The text of one agent's LAST EVALUATION cell.

  The cells carry no ids, so the row is found by the link to the agent and the
  cell by position: it is the third of the five the row renders.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Home.CARD_GRID}.children")
  response = dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": "/agents",
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": False,
      },
  )
  assert response.status_code == 200, response.data[:2000]
  grid = dash_http.body(response)["response"][AgentIds.Home.CARD_GRID][
      "children"
  ]

  rows = [
      node
      for node in _walk(grid)
      if node.get("type") == "Tr" and f"/agents/view/{agent_id}" in str(node)
  ]
  assert len(rows) == 1, f"agent {agent_id} is on {len(rows)} rows"
  cells = rows[0]["props"]["children"]
  assert len(cells) == 5, f"the row has {len(cells)} cells, not 5"
  return str(cells[2])


def _walk(tree: Any):
  """Every serialized component in ``tree``, depth first."""
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      if isinstance(node.get("props"), dict):
        yield node
      stack.extend(node.values())


def test_a_run_that_has_scored_nothing_yet_does_not_read_as_zero(
    dash_client, callback_errors, db_session, seeded
):
  """Starting an evaluation used to put 0.0% next to today's date.

  The latest run is the newest one whatever its status, and its accuracy is
  None until something scores a trial. Formatting that None as a percentage
  said the agent had just failed everything it was asked. The date is still
  the run's, so the cell has to keep it.
  """
  run = db_session.get(Run, seeded.run_id)
  assert run.accuracy is None

  cell = _last_eval(dash_client, seeded.agent_id)
  callback_errors.assert_none()

  assert "0.0%" not in cell
  assert "--" in cell
  # Not the "Never" the no-run branch renders, since the run does exist.
  assert "Never" not in cell


def test_a_scored_run_still_reports_its_accuracy(
    dash_client, callback_errors, db_session, seeded
):
  """The other side of the same cell, so the fix cannot be to say nothing.

  One assertion result on the run's one COMPLETED trial is enough for
  ``Run.accuracy`` to have a value, and that value has to reach the table.
  """
  # The third seeded trial, because the mean only counts COMPLETED ones.
  trial = (
      db_session.query(Trial)
      .filter_by(run_id=seeded.run_id)
      .order_by(Trial.id)
      .all()[2]
  )
  snapshot = AssertionSnapshot(
      example_snapshot_id=trial.example_snapshot_id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
      params={"value": "seeded", "mode": "contains"},
  )
  db_session.add(snapshot)
  db_session.flush()
  db_session.add(
      AssertionResult(
          trial_id=trial.id,
          assertion_snapshot_id=snapshot.id,
          passed=True,
          score=1.0,
      )
  )
  db_session.commit()

  cell = _last_eval(dash_client, seeded.agent_id)
  callback_errors.assert_none()

  assert "100.0%" in cell
