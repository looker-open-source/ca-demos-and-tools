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

"""The two suggestion stores, and the rest of the playground's first paint.

``store-suggestions`` holds what the last ad-hoc run proposed and feeds the
inline accordion. ``store-history-suggestions`` holds what the Suggestions
modal pulled out of past trials. One store used to hold both, and the two
panels are on screen together, so they overwrote each other: opening the modal
replaced the accordion's cards with suggestions from other trials and other
agents, and adding one from the modal left a live Accept button on the same
suggestion in the accordion behind it.

The rest of the file is the same page's opening state. Which half of the
editor is visible before anything is selected, whether the suggestion panel is
on screen while a run is in flight, and what the test case card draws.

``get_client`` is patched in every test that would reach an agent, because
tests/ui runs with ``PRISM_AGENT_BACKEND`` unset and a real client would put
the question to the agent for real.
"""

from __future__ import annotations

import datetime
import json
from typing import Any
from unittest import mock

import plotly.utils
from prism.common.schemas import assertion as assertion_schemas
from prism.ui.callbacks import test_suite_questions_callbacks
from prism.ui.components import test_case_components
from prism.ui.ids import TestSuiteIds as Ids
from prism.ui.models import ui_state
from prism.ui.pages import test_suite_questions
import pytest
from tests.ui import dash_http

_UTC = datetime.timezone.utc


def _values(response) -> dict[str, Any]:
  """The property values a 200 carries, keyed by ``<id>.<property>``.

  An output the callback returned no_update for is left out, so a missing key
  is the assertion that nothing was written.
  """
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def _written_ids(response) -> set[str]:
  """The component ids a 200 wrote to."""
  return set(dash_http.body(response).get("response", {}))


def _find(node: Any, component_id: Any) -> Any:
  """The first component in a built tree carrying ``component_id``.

  Walks the ``children`` the page composed rather than the JSON, because
  ``to_plotly_json`` is one level deep and the ids wanted here are nested
  inside a Flex inside a Box.
  """
  if node is None or isinstance(node, str):
    return None
  if isinstance(node, (list, tuple)):
    for child in node:
      found = _find(child, component_id)
      if found is not None:
        return found
    return None
  if getattr(node, "id", None) == component_id:
    return node
  return _find(getattr(node, "children", None), component_id)


def _every_id(node: Any) -> list[Any]:
  """Every component id in a built tree, dict ids included."""
  if node is None or isinstance(node, str):
    return []
  if isinstance(node, (list, tuple)):
    return [i for child in node for i in _every_id(child)]
  found = [node.id] if getattr(node, "id", None) is not None else []
  return found + _every_id(getattr(node, "children", None))


def _as_json(component: Any) -> str:
  """A built component tree as text, for substring assertions.

  ``json.dumps`` alone stops at the first nested component. Dash serializes
  with plotly's encoder, which is what the browser receives.
  """
  return json.dumps(component, cls=plotly.utils.PlotlyJSONEncoder)


@pytest.fixture(name="client")
def _client(monkeypatch):
  """Puts a stub where the playground callbacks reach for their client."""
  stub = mock.Mock()
  monkeypatch.setattr(
      test_suite_questions_callbacks, "get_client", lambda: stub
  )
  return stub


def _history_trial():
  """One past trial carrying one suggestion, as the trials client returns it."""
  trial = mock.Mock()
  trial.id = 5
  trial.run_id = 2
  trial.agent_name = "Some Other Agent"
  trial.created_at = datetime.datetime(2026, 1, 1, tzinfo=_UTC)
  trial.suggested_asserts = [
      assertion_schemas.TextContains(value="from a past run", weight=1.0)
  ]
  return trial


def _simulation(passed: bool):
  """What ``run_simulation`` hands ``execute_simulation``.

  Spelled out rather than produced by the real client, because the colour is
  all this file asserts on. tests/ui/test_dispatch_simulation.py builds the
  same thing through ``PlaygroundClient`` and is where a renamed key shows up.
  """
  result = mock.Mock()
  result.result_summary = {
      "passed": passed,
      "duration_ms": 1234,
      "assertion_results": [{
          "assertion": {"type": "text-contains", "weight": 1.0},
          "passed": passed,
          "score": 1.0 if passed else 0.0,
      }],
  }
  result.suggestions_ui = []
  return result


# Finding 3: the modal no longer writes the accordion's store.


def test_opening_the_modal_leaves_the_inline_suggestions_alone(
    dash_client, callback_errors, client
):
  """The modal used to overwrite the suggestions the last run raised.

  Both panels read one store, so a user who ran a test case, saw two
  suggestions in the accordion and then opened Suggestions from recent runs to
  compare found the accordion holding suggestions from other trials and other
  agents. The ones the run raised were gone short of running it again.
  """
  client.trials.list_trials_with_suggestions.return_value = [_history_trial()]

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(
      deps,
      f"{Ids.STORE_HISTORY_SUGGESTIONS}.data",
      triggered_by=Ids.TC_HISTORY_SUGGESTIONS_BTN,
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.TC_HISTORY_SUGGESTIONS_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": [
              {"id": 11, "question": "How many orders?", "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  offered = values[f"{Ids.STORE_HISTORY_SUGGESTIONS}.data"]
  assert [s["value"] for s in offered] == ["from a past run"]
  assert Ids.STORE_SUGGESTIONS not in _written_ids(
      response
  ), "the modal must not touch the store the inline accordion reads"


def test_the_two_panels_read_the_two_stores(dash_client):
  """One store behind both lists is the defect, so name the wiring.

  The lists render from whichever store their callback takes as an Input, and
  that Input is the only thing keeping them apart. The inline list is named by
  its trigger, because start_simulation_run writes the same children to put
  the skeleton up.
  """
  deps = dash_http.dependencies(dash_client)

  inline = dash_http.find(
      deps, f"{Ids.SUG_LIST}.children", triggered_by=Ids.STORE_SUGGESTIONS
  )
  modal = dash_http.find(deps, f"{Ids.SUGGESTION_LIST}.children")

  assert [i["id"] for i in inline["inputs"]] == [Ids.STORE_SUGGESTIONS]
  assert [i["id"] for i in modal["inputs"]] == [Ids.STORE_HISTORY_SUGGESTIONS]


# Finding 1: adding from the modal empties the modal's store.


def test_adding_from_the_modal_empties_the_list_it_added_from(
    dash_client, callback_errors
):
  """Nothing cleared the store, so the same suggestion could be added twice.

  Add Selected closes the modal and writes the ticked suggestions onto the
  test case. It left them in the store, still ticked, so reopening the modal
  offered them again and a second Add Selected wrote the same assertion onto
  the test case a second time.
  """
  suggestion = {
      "type": "text-contains",
      "value": "from a past run",
      "weight": 1.0,
      "_trial_id": 5,
      "_group_label": "2026-01-01 - Some Other Agent (Run 2 Trial 5)",
  }

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(
      deps,
      f"{Ids.SUGGESTION_MODAL}.opened",
      triggered_by=Ids.SUGGESTION_ADD_BTN,
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.SUGGESTION_ADD_BTN}.n_clicks": 1,
          f"{Ids.SUGGESTION_LIST}-group.value": [json.dumps(suggestion)],
          # No id on the test case, so the write stops at the store instead of
          # reaching _sync_suite and the database.
          f"{Ids.STORE_BUILDER}.data": [
              {"question": "How many orders?", "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          "url.pathname": "/test_suites/edit/1",
      },
      changed=[f"{Ids.SUGGESTION_ADD_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.SUGGESTION_MODAL}.opened"] is False
  written = values[f"{Ids.STORE_BUILDER}.data"][0]["asserts"]
  assert [a["value"] for a in written] == ["from a past run"]
  # The UI-only keys are stripped on the way in, so a store left holding the
  # suggestion is the only thing that could offer it again.
  assert values[f"{Ids.STORE_HISTORY_SUGGESTIONS}.data"] == []


# Finding 5: the suggestion panel is on screen while the run is in flight.


def test_the_suggestion_panel_is_shown_when_the_run_starts(
    dash_client, callback_errors
):
  """The skeleton went into a hidden container on the first run of a page load.

  The accordion ships ``display: none`` and only render_inline_suggestion_list
  used to show it, which runs after the agent call returns. So the suggestions
  area sat empty for the length of the call and the skeleton appeared at the
  moment it was no longer needed.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{Ids.STORE_START_RUN}.data")

  response = dash_http.fire(dash_client, dep, {f"{Ids.TC_RUN_BTN}.n_clicks": 1})

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.SUG_ACCORDION}.style"] == {"display": "block"}
  skeletons = json.dumps(values[f"{Ids.SUG_LIST}.children"])
  assert skeletons.count('"Skeleton"') == 2, skeletons


def test_the_panel_starts_hidden():
  """Why the callback has to un-hide it.

  Without this the fix reads as a no-op.
  """
  accordion = _find(test_suite_questions.layout(), Ids.SUG_ACCORDION)

  assert accordion is not None
  assert accordion.style == {"display": "none"}


# Finding 4: the result banner is coloured by Mantine variables.


def test_the_result_banner_is_coloured_by_mantine_variables(
    dash_client, callback_errors, client
):
  """The banner was flat white whether the run passed or failed.

  Its background and border were set with className="bg-green.0" and
  "border-green.1". The app ships no Tailwind, so both matched nothing. The
  round that replaced emerald with green fixed the c= prop on the text and
  left these two.
  """
  client.playground.run_simulation.return_value = _simulation(passed=True)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(
      deps,
      f"{Ids.STORE_PLAYGROUND_RESULT}.data",
      triggered_by=Ids.STORE_START_RUN,
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.STORE_START_RUN}.data": {"ts": 1758000000000},
          f"{Ids.STORE_BUILDER}.data": [
              {"id": 11, "question": "How many orders?", "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.TC_AGENT_SELECT}.value": "3",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  banner = json.dumps(
      _values(response)[f"{Ids.SIM_CONTEXT_CONTAINER}.children"]
  )
  assert "var(--mantine-color-green-0)" in banner
  assert "1px solid var(--mantine-color-green-1)" in banner
  assert "var(--mantine-color-green-6)" in banner
  assert "bg-green" not in banner
  assert "border-green" not in banner


def test_a_failing_run_is_banded_red_by_the_same_variables(
    dash_client, callback_errors, client
):
  """The colour is the signal at a glance, so both arms have to carry it."""
  client.playground.run_simulation.return_value = _simulation(passed=False)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(
      deps,
      f"{Ids.STORE_PLAYGROUND_RESULT}.data",
      triggered_by=Ids.STORE_START_RUN,
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.STORE_START_RUN}.data": {"ts": 1758000000000},
          f"{Ids.STORE_BUILDER}.data": [
              {"id": 11, "question": "How many orders?", "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.TC_AGENT_SELECT}.value": "3",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  banner = json.dumps(
      _values(response)[f"{Ids.SIM_CONTEXT_CONTAINER}.children"]
  )
  assert "var(--mantine-color-red-0)" in banner
  assert "green" not in banner
  assert "bg-red" not in banner


# Finding 2: the editor opens on the empty state.


def test_the_editor_opens_on_the_prompt_not_on_a_blank_form():
  """The two defaults were the other way round on first paint.

  On a suite with no test cases the sync callback never corrects them:
  load_playground_data writes selected_index=None, the value the store already
  holds, so the prop does not change and nothing fires. The page opened on an
  empty Test Case box, an assertion panel and a Save bar that
  save_test_case_text returns early out of.
  """
  page = test_suite_questions.layout()

  empty = _find(page, Ids.TC_EDITOR_EMPTY)
  editor = _find(page, Ids.TC_EDITOR_CONTAINER)

  assert empty.style["display"] == "flex"
  assert editor.style["display"] == "none"


def test_the_first_paint_agrees_with_the_no_selection_arm(
    dash_client, callback_errors
):
  """The defaults have to be what the callback writes for no selection.

  That arm is what runs on every later move back to nothing selected, so a
  first paint that disagrees with it is a page in a state the callback can
  never restore.
  """
  page = test_suite_questions.layout()
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{Ids.TC_EDITOR_EMPTY}.style")

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.STORE_SELECTED_INDEX}.data": None,
          f"{Ids.STORE_BUILDER}.data": [],
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.TC_EDITOR_EMPTY}.style"]["display"] == (
      _find(page, Ids.TC_EDITOR_EMPTY).style["display"]
  )
  assert values[f"{Ids.TC_EDITOR_CONTAINER}.style"]["display"] == (
      _find(page, Ids.TC_EDITOR_CONTAINER).style["display"]
  )


# Finding 6: dead code in the card and a dead Input on the add button.


def test_the_test_case_card_draws_no_action_buttons():
  """The editable variant of the card never reached a browser.

  render_test_case_list is the only caller and it passes
  ``read_only = "/view/" in pathname``. The container it writes into is only
  rendered by the suite view page, whose route is /test_suites/view/<id>, so
  read_only is always True. The pencil and trash drawn for the other case were
  unreachable, and the pencil carried the same id as the sidebar nav item, so
  a page that had rendered both would have had two components sharing an id.
  """
  test_case = ui_state.TestCaseState(question="How many orders?", asserts=[])

  for read_only in (True, False):
    card = _as_json(
        test_case_components.render_test_case_card(
            test_case, 0, read_only=read_only
        )
    )
    assert Ids.TC_LIST_ITEM not in card, read_only
    assert Ids.TC_REMOVE_TEST_CASE_BTN not in card, read_only


def test_the_add_test_case_button_is_a_plain_id(dash_client):
  """The callback declared a second Input nothing ever builds.

  It was an ALL over {"type": TC_PLAYGROUND_ADD_BTN, "index": ...}. The page
  renders the button with the plain string id, so that pattern matched no
  component and the wildcard resolved to an empty list on every fire.
  """
  page_ids = _every_id(test_suite_questions.layout())
  assert Ids.TC_PLAYGROUND_ADD_BTN in page_ids
  assert not [
      i
      for i in page_ids
      if isinstance(i, dict) and i.get("type") == Ids.TC_PLAYGROUND_ADD_BTN
  ], "nothing builds the pattern id, so no callback should declare it"

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(
      deps, f"{Ids.STORE_BUILDER}.data", triggered_by=Ids.TC_PLAYGROUND_ADD_BTN
  )
  assert [i["id"] for i in dep["inputs"]] == [Ids.TC_PLAYGROUND_ADD_BTN]
