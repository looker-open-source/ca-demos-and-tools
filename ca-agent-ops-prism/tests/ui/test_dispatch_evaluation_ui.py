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

"""Four defects on the run detail and trial detail pages.

Three of these are dispatch tests, driven through the same HTTP route as
``test_dispatch_trial_detail.py``. The last one is not: a badge colour never
reaches a callback, so the only thing that can read it is the component
function itself.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

import dash_mantine_components as dmc
import plotly.utils
from prism.common.schemas.agent import Agent
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.execution import Trial

# Importing the app registers every page and every callback.
from prism.ui.app import app
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.components import agent_components
from prism.ui.components import run_components
from prism.ui.ids import EvaluationIds
from prism.ui.models.ui_state import RunDetailPageState
from prism.ui.pages import evaluation_detail
import pytest
from tests.ui import dash_http

_SNAPSHOT = {"system_instruction": "Answer questions about orders."}
_LIVE = {"system_instruction": "Answer questions about refunds."}


def _serialized(component: Any) -> Any:
  """The component tree as Dash's encoder writes it to the browser.

  Layout and component functions return Python objects, and the dispatch
  responses these tests read are already JSON. Putting both through the same
  encoder lets one walker find a component in either.
  """
  return json.loads(json.dumps(component, cls=plotly.utils.PlotlyJSONEncoder))


def _component(tree: Any, component_id: Any) -> dict[str, Any]:
  """The one serialized component in ``tree`` carrying ``component_id``."""
  found = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      props = node.get("props")
      if isinstance(props, dict) and props.get("id") == component_id:
        found.append(node)
      stack.extend(node.values())
  assert len(found) == 1, f"{component_id} appears {len(found)} times"
  return found[0]


def _pattern_indices(tree: Any, id_type: str) -> list[Any]:
  """Every ``index`` carried by a pattern-matching id of ``id_type``."""
  found = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      props = node.get("props")
      if isinstance(props, dict):
        component_id = props.get("id")
        if isinstance(component_id, dict) and component_id.get("type") == (
            id_type
        ):
          found.append(component_id.get("index"))
      stack.extend(node.values())
  return found


def _run_data(run_id: int = 99) -> dict[str, Any]:
  """The RUN_DATA_STORE payload for one completed run with no trials."""
  run = RunSchema(
      id=run_id,
      test_suite_snapshot_id=1,
      agent_id=7,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      agent_context_snapshot=_SNAPSHOT,
  )
  return RunDetailPageState(run=run, trials=[]).model_dump(mode="json")


def _run_detail_dep(dash_client) -> dict[str, Any]:
  """The ``render_run_detail_components`` entry."""
  deps = dash_http.dependencies(dash_client)
  return dash_http.find(deps, f"{EvaluationIds.RUN_DETAIL_STATS}.children")


def _live_fetch_dep(dash_client) -> dict[str, Any]:
  """The ``fetch_live_config_for_diff`` entry.

  Two callbacks write the download button's disabled flag, so this is picked
  out by being the one whose only input is the diff store itself.
  """
  deps = dash_http.dependencies(dash_client)
  matches = [
      dep
      for dep in deps
      if [i["id"] for i in dep["inputs"]]
      == [EvaluationIds.RUN_CONTEXT_DIFF_STORE]
      and EvaluationIds.BTN_DOWNLOAD_DIFF in dep["output"]
  ]
  assert len(matches) == 1, f"expected one live-fetch callback, got {matches}"
  return matches[0]


def _toggle_dep(dash_client) -> dict[str, Any]:
  """The ``toggle_config_diff_modal`` entry, the only one opening the modal."""
  deps = dash_http.dependencies(dash_client)
  return dash_http.find(deps, f"{EvaluationIds.RUN_CONTEXT_DIFF_MODAL}.opened")


def test_the_download_button_is_dead_until_a_live_context_arrives(
    dash_client, callback_errors, monkeypatch
):
  """A modal with no live context must not offer a download.

  ``download_diff_context`` returns no_update when ``live`` is unset, so the
  click produced no file, no toast and no log line. The failed-fetch branch is
  where that is reachable: the alert says the live context is unavailable and
  the button sat enabled beside it. The three states go in together because a
  button hardcoded disabled would pass the first two on its own.
  """
  seeded = _component(
      _serialized(run_components.render_diff_modal()),
      EvaluationIds.BTN_DOWNLOAD_DIFF,
  )
  assert seeded["props"]["disabled"] is True

  class _Client:
    """A client whose published-context lookup comes back empty."""

    class agents:  # pylint: disable=invalid-name

      @staticmethod
      def get_published_context(agent_id):
        del agent_id
        return None

  monkeypatch.setattr(evaluation_callbacks, "get_client", _Client)

  failed = dash_http.fire(
      dash_client,
      _live_fetch_dep(dash_client),
      {
          f"{EvaluationIds.RUN_CONTEXT_DIFF_STORE}.data": {
              "snapshot": _SNAPSHOT,
              "live": None,
              "agent_id": 7,
              "is_fetching": True,
          }
      },
  )
  assert failed.status_code == 200, failed.data[:2000]
  body = dash_http.body(failed)["response"]
  assert body[EvaluationIds.BTN_DOWNLOAD_DIFF]["disabled"] is True

  opened = dash_http.fire(
      dash_client,
      _toggle_dep(dash_client),
      {
          f"{EvaluationIds.RUN_CONTEXT_DIFF_BTN}.n_clicks": 1,
          f"{EvaluationIds.RUN_CONTEXT_DIFF_STORE}.data": {
              "snapshot": _SNAPSHOT,
              "live": _LIVE,
              "agent_id": 7,
              "is_fetching": False,
          },
      },
  )
  assert opened.status_code == 200, opened.data[:2000]
  body = dash_http.body(opened)["response"]
  assert body[EvaluationIds.BTN_DOWNLOAD_DIFF]["disabled"] is False

  callback_errors.assert_none()


def test_a_suggestion_without_an_id_is_dropped_not_renumbered(
    dash_client, callback_errors, monkeypatch
):
  """A card's index is a row id, so a list position must not stand in for it.

  ``curate_trial_suggestion`` reads the index off the clicked button and hands
  it to ``curate_suggestion`` as a primary key. Falling back to the loop
  position meant the second id-less suggestion on the page accepted or
  rejected whichever row happens to hold id 1. The trial goes in through the
  client because a row with no id cannot be seeded: the database assigns one.
  """
  real_client = evaluation_callbacks.get_client()
  trial = Trial(
      id=5,
      run_id=3,
      example_snapshot_id=1,
      status=RunStatus.COMPLETED,
      question="How many seeded orders are there?",
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      suggested_asserts=[
          {
              "type": "text-contains",
              "value": "has-an-id",
              "mode": "contains",
              "weight": 1.0,
              "id": 41,
          },
          {
              "type": "text-contains",
              "value": "no-id-at-all",
              "mode": "contains",
              "weight": 1.0,
              "id": None,
          },
      ],
  )

  class _Runs:
    """Only the three calls ``render_trial_detail`` makes."""

    @staticmethod
    def get_trial(trial_id):
      del trial_id
      return trial

    @staticmethod
    def get_run(run_id):
      del run_id
      return None

    parse_timeline = real_client.runs.parse_timeline

  class _Client:
    runs = _Runs

  monkeypatch.setattr(evaluation_callbacks, "get_client", _Client)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.TRIAL_DETAIL_CONTAINER}.children")
  response = dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": f"/evaluations/trials/{trial.id}",
          "url.search": "",
          f"{EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL}.data": 0,
          f"{EvaluationIds.TRIAL_SUG_LOADING_STORE}.data": False,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  children = dash_http.body(response)["response"][
      EvaluationIds.TRIAL_DETAIL_CONTAINER
  ]["children"]

  assert _pattern_indices(children, EvaluationIds.INLINE_SUG_ADD_BTN) == [41]
  assert _pattern_indices(children, EvaluationIds.INLINE_SUG_REJECT_BTN) == [41]
  # The card is gone, not drawn with buttons pointing at another row.
  assert "no-id-at-all" not in str(children)
  assert "has-an-id" in str(children)

  callback_errors.assert_logged("has no id")
  callback_errors.assert_none()


def test_the_stats_row_seeds_one_skeleton_per_card(
    dash_client, callback_errors
):
  """The loading skeletons have to fill the grid the cards fill.

  The row is a four-column grid and the callback returns four cards, so three
  skeletons left a gap on the right of every load and the row jumped once the
  data arrived. All three counts go in the same assertion because the point is
  that they agree, not what the number is.
  """
  grid = _component(
      _serialized(evaluation_detail.layout("99")),
      EvaluationIds.RUN_DETAIL_STATS,
  )
  skeletons = grid["props"]["children"]
  assert all(node["type"] == "Skeleton" for node in skeletons), skeletons

  response = dash_http.fire(
      dash_client,
      _run_detail_dep(dash_client),
      {f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data()},
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)["response"]
  cards = body[EvaluationIds.RUN_DETAIL_STATS]["children"]
  assert len(skeletons) == len(cards) == grid["props"]["cols"]["lg"]

  callback_errors.assert_none()


# Every colour name Mantine resolves here: its own palette plus the two the
# app registers. An unknown name is not an error, which is the problem. The
# theme passes the string to toRgba, that returns black, and variant="light"
# paints a black badge with black text on it.
_KNOWN_COLORS = (
    set(dmc.DEFAULT_THEME["colors"])
    | set(app.layout.theme["colors"])
    | {"dimmed"}
)


def _unresolvable_colors(tree: Any) -> list[tuple[str, str]]:
  """Every ``color`` or ``c`` prop in ``tree`` naming no palette entry.

  Shades are stripped, since "blue.6" resolves as long as blue does. CSS
  values are skipped: a var() or a hex code never goes near the palette.
  """
  bad = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      props = node.get("props")
      if isinstance(props, dict):
        for prop in ("color", "c"):
          value = props.get(prop)
          if not isinstance(value, str) or value.startswith(("var(", "#")):
            continue
          if value.split(".")[0] not in _KNOWN_COLORS:
            bad.append((node.get("type"), value))
      stack.extend(node.values())
  return bad


@pytest.mark.parametrize(
    "datasource,badge",
    [
        (
            LookerConfig(instance_uri="https://looker.example", explores=["e"]),
            "Looker",
        ),
        (BigQueryConfig(tables=["p.d.t"]), "BigQuery"),
    ],
    ids=["looker", "bigquery"],
)
def test_the_agent_card_paints_only_colours_mantine_knows(datasource, badge):
  """The datasource badge named a colour the palette does not have.

  Not a dispatch test. The colour is a string that goes straight to the
  browser, so no callback ever reads it and no response says whether it
  resolves. "purple" is not a Mantine colour, and a name the theme cannot find
  comes back black, which on a light badge is black on black. Both datasource
  branches go in, because they pick different colours.
  """
  agent = Agent(
      id=1,
      name="Seeded Agent",
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=datasource,
      ),
  )

  card = _serialized(agent_components.render_agent_card(agent))

  assert badge in str(card)
  assert not _unresolvable_colors(card)
