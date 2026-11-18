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
from prism.server.models.agent import Agent
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


def test_archived_query_param_syncs_switch_and_guards_other_routes(
    dash_client, callback_errors
):
  """`/agents?archived=true` checks the switch; other routes are untouched."""
  deps = dash_http.dependencies(dash_client)
  sync_dep = dash_http.find(
      deps, f"{AgentIds.Home.SWITCH_ARCHIVED}.checked", triggered_by="url"
  )

  checked_resp = dash_http.fire_url(
      dash_client, sync_dep, "/agents", "?archived=true"
  )
  assert checked_resp.status_code == 200
  assert (
      dash_http.body(checked_resp)["response"][AgentIds.Home.SWITCH_ARCHIVED][
          "checked"
      ]
      is True
  )

  default_resp = dash_http.fire_url(dash_client, sync_dep, "/agents", "")
  assert default_resp.status_code == 200
  assert (
      dash_http.body(default_resp)["response"][AgentIds.Home.SWITCH_ARCHIVED][
          "checked"
      ]
      is False
  )

  other_resp = dash_http.fire_url(
      dash_client, sync_dep, "/test_suites", "?archived=true"
  )
  assert other_resp.status_code == 200
  assert dash_http.body(other_resp).get("response", {}) == {}

  callback_errors.assert_none()


def test_toggling_archived_switch_syncs_url_search_without_loops(
    dash_client, callback_errors
):
  """Toggling Show Archived updates url.search, preserves params, and stops."""
  deps = dash_http.dependencies(dash_client)
  write_dep = dash_http.find(
      deps, "url.search", triggered_by=AgentIds.Home.SWITCH_ARCHIVED
  )

  on_resp = dash_http.fire(
      dash_client,
      write_dep,
      {
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": True,
          "url.pathname": "/agents",
          "url.search": "?foo=bar",
      },
  )
  assert on_resp.status_code == 200
  assert (
      dash_http.body(on_resp)["response"]["url"]["search"]
      == "?foo=bar&archived=true"
  )

  settled_on = dash_http.fire(
      dash_client,
      write_dep,
      {
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": True,
          "url.pathname": "/agents",
          "url.search": "?foo=bar&archived=true",
      },
  )
  assert settled_on.status_code == 200
  assert dash_http.body(settled_on).get("response", {}) == {}

  off_resp = dash_http.fire(
      dash_client,
      write_dep,
      {
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": False,
          "url.pathname": "/agents",
          "url.search": "?foo=bar&archived=true",
      },
  )
  assert off_resp.status_code == 200
  assert dash_http.body(off_resp)["response"]["url"]["search"] == "?foo=bar"

  settled_off = dash_http.fire(
      dash_client,
      write_dep,
      {
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": False,
          "url.pathname": "/agents",
          "url.search": "",
      },
  )
  assert settled_off.status_code == 200
  assert dash_http.body(settled_off).get("response", {}) == {}

  for no_op_search in ("?archived=false", "?foo=a%20b"):
    no_op = dash_http.fire(
        dash_client,
        write_dep,
        {
            f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": False,
            "url.pathname": "/agents",
            "url.search": no_op_search,
        },
    )
    assert no_op.status_code == 200
    assert dash_http.body(no_op).get("response", {}) == {}

  wrong_route = dash_http.fire(
      dash_client,
      write_dep,
      {
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": True,
          "url.pathname": "/test_suites",
          "url.search": "",
      },
  )
  assert wrong_route.status_code == 200
  assert dash_http.body(wrong_route).get("response", {}) == {}

  callback_errors.assert_none()


def test_agent_list_respects_archived_flag_and_route_guard(
    dash_client, callback_errors, db_session, seeded
):
  """Archived agents render only when include_archived is True on /agents."""
  archived = Agent(
      name="Archived Fleet Agent",
      project_id="proj",
      location="global",
      agent_resource_id="archived-fleet-agent",
      datasource_config={"type": "bigquery", "tables": ["proj.ds.tbl"]},
      is_archived=True,
  )
  db_session.add(archived)
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Home.CARD_GRID}.children")

  active_only = dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": "/agents",
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": False,
      },
  )
  assert active_only.status_code == 200
  active_text = str(dash_http.body(active_only))
  assert seeded.agent_name in active_text
  assert "Archived Fleet Agent" not in active_text

  with_archived = dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": "/agents",
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": True,
      },
  )
  assert with_archived.status_code == 200
  all_text = str(dash_http.body(with_archived))
  assert seeded.agent_name in all_text
  assert "Archived Fleet Agent" in all_text

  other_route = dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": "/test_suites",
          f"{AgentIds.Home.SWITCH_ARCHIVED}.checked": True,
      },
  )
  assert other_route.status_code == 200
  assert dash_http.body(other_route).get("response", {}) == {}

  callback_errors.assert_none()
