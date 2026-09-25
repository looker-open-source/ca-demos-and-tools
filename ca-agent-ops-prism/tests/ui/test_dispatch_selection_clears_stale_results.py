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

"""Moving the editor onto another test case takes the last run off screen.

``store-playground-result`` holds one simulation: its assertion results, in
the order the assertions ran. ``render_assertion_list`` maps that onto the
selected test case's assertions by position, so the store only means anything
next to the test case it was produced for.

Both ways of changing the selection have to clear it, the same way the delete
path already did. Selecting is a click on the list and a ``?test_case_id=`` in
the URL, and until this the store survived both.
"""

from __future__ import annotations

from typing import Any

from prism.ui.ids import TestSuiteIds as Ids
from tests.ui import dash_http

# The shape ``run_simulation`` writes, cut down to the part the assertion
# cards read. One result, so it can only ever line up with a first assertion.
_RESULT = {
    "passed": False,
    "score": 0.0,
    "assertion_results": [{
        "passed": False,
        "score": 0.0,
        "reasoning": "the answer never mentioned the order count",
    }],
}

_TEST_CASES = [
    {
        "id": 11,
        "question": "How many orders are there?",
        "asserts": [{"type": "text-contains", "value": "orders"}],
    },
    {
        "id": 22,
        "question": "How many customers are there?",
        "asserts": [{"type": "text-contains", "value": "customers"}],
    },
]


def _callback(
    deps: list[dict[str, Any]], output: str, *inputs: str
) -> dict[str, Any]:
  """The one callback with this output and these Inputs, in order.

  Four callbacks write the playground result store and six write the selected
  index, all with allow_duplicate, so the output address does not name one of
  them. The Input side does.
  """
  matches = [
      dep
      for dep in deps
      if output in dep["output"]
      and len(dep["inputs"]) == len(inputs)
      and all(
          want in str(got["id"]) for want, got in zip(inputs, dep["inputs"])
      )
  ]
  assert len(matches) == 1, (
      f"expected one callback writing {output} from {list(inputs)}, found"
      f" {len(matches)}"
  )
  return matches[0]


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


def _click(dash_client, index: int, clicks: list[tuple[int, Any]]):
  """Fires the list click callback as if the row at ``index`` was clicked."""
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_PLAYGROUND_RESULT}.data", Ids.TC_LIST_ITEM)
  pattern = dep["inputs"][0]
  return dash_http.fire(
      dash_client,
      dep,
      {dash_http.address(pattern): clicks},
      changed=[dash_http.pattern_address(pattern, index)],
  )


def _navigate(dash_client, search: str, current_index: int):
  """Fires the URL sync callback as if the address bar had just changed."""
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_PLAYGROUND_RESULT}.data", "url")
  return dash_http.fire(
      dash_client,
      dep,
      {
          "url.search": search,
          f"{Ids.STORE_BUILDER}.data": _TEST_CASES,
          f"{Ids.STORE_SELECTED_INDEX}.data": current_index,
      },
  )


def test_clicking_another_test_case_clears_the_previous_runs_result(
    dash_client, callback_errors
):
  """The badges belong to the test case that was run, not to the editor.

  Running the first test case and then clicking the second drew the second
  one's assertions wearing the first one's pass and fail badges and its
  reasoning, with no run having happened for them. Nothing on screen said the
  badges were from somewhere else.
  """
  response = _click(dash_client, 1, [(0, 1), (1, 1)])

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 1
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None


def test_a_deep_link_to_another_test_case_clears_it_too(
    dash_client, callback_errors
):
  """The same move, made from the address bar instead of the list.

  The suite view page links to one test case at a time, and the back button
  walks the same query string. Clearing on the click alone left the whole of
  that route showing the previous run's badges.
  """
  response = _navigate(dash_client, "?test_case_id=22", current_index=0)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 1
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None


def test_landing_on_the_test_case_already_open_leaves_the_result_alone(
    dash_client, callback_errors
):
  """Clearing on every URL change would throw a run away on a reload.

  ``update_url_on_test_case_select`` writes the same query string back after a
  click, so this callback fires again with the selection it already agrees
  with. That arm returns no_update for both outputs, which Dash answers 200
  with an empty response.
  """
  response = _navigate(dash_client, "?test_case_id=22", current_index=1)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert _values(response) == {}


def test_a_list_rendered_but_never_clicked_changes_nothing(
    dash_client, callback_errors
):
  """Every row arrives with n_clicks None the first time the list renders.

  Reading one of those as a click would move the selection to row zero and
  clear the result on the page load itself.
  """
  response = _click(dash_client, 0, [(0, None), (1, None)])

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert _values(response) == {}


def test_the_assertion_badges_are_drawn_from_the_store_that_is_cleared(
    dash_client, callback_errors
):
  """Why the clearing has to happen, in the callback that does the drawing.

  ``render_assertion_list`` takes the selected index and the result store as
  Inputs and pairs them up by position. It has no way to tell which test case
  the result came from, so the only place the mismatch can be stopped is where
  the selection moves.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.TC_ASSERT_LIST}.children",
      Ids.STORE_BUILDER,
      Ids.STORE_SELECTED_INDEX,
      Ids.STORE_PLAYGROUND_RESULT,
  )

  def render(result):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ids.STORE_BUILDER}.data": _TEST_CASES,
            f"{Ids.STORE_SELECTED_INDEX}.data": 1,
            f"{Ids.STORE_PLAYGROUND_RESULT}.data": result,
        },
    )
    assert response.status_code == 200, response.data[:2000]
    return str(_values(response)[f"{Ids.TC_ASSERT_LIST}.children"])

  reasoning = _RESULT["assertion_results"][0]["reasoning"]

  assert reasoning in render(_RESULT), "the store is not read by position"
  assert reasoning not in render(None)
  callback_errors.assert_none()
