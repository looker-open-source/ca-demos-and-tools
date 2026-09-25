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

"""Suggestions belong to the test case that was run, and only to that one.

``store-suggestions`` holds the assertions the last simulation proposed.
``handle_inline_suggestion`` reads it on Accept and writes the chosen one onto
whichever test case is selected at that moment, then hands the suite to
``_sync_suite``. So a suggestion raised by running test case A, left in the
store while the selection moves to B, is accepted onto B and saved there.

Four callbacks move the selection and all four have to clear the store. The
playground result store was already cleared by three of them, which is why the
round that added it looked like it had covered this: that store is not the one
the Accept path reads.

``tests/ui/test_dispatch_selection_clears_stale_results.py`` covers the
playground result store on the same four callbacks.
"""

from __future__ import annotations

from typing import Any

from prism.ui.ids import TestSuiteIds as Ids
from tests.ui import dash_http

# Two suggestions, in the shape run_simulation writes. Distinctive values, so
# an assertion that lands on a test case can be traced back to the suggestion
# it came from.
_SUGGESTIONS = [
    {"type": "text-contains", "value": "orders", "_reason": "from run of A"},
    {"type": "text-contains", "value": "shipped", "_reason": "from run of A"},
]

_TEST_CASES = [
    {
        "id": 11,
        "question": "How many orders are there?",
        "asserts": [{"type": "text-contains", "value": "orders"}],
    },
    {
        "id": 22,
        "question": "How many customers are there?",
        "asserts": [],
    },
]


def _callback(
    deps: list[dict[str, Any]], output: str, *inputs: str
) -> dict[str, Any]:
  """The one callback with this output and these Inputs, in order.

  Seven callbacks write the suggestions store, all with allow_duplicate, so
  the output address does not name one of them. The Input side does.
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


def test_clicking_another_test_case_clears_the_suggestions(
    dash_client, callback_errors
):
  """The store outlived the test case it was raised for.

  Running test case A and clicking test case B left A's suggestion cards on
  screen next to B's assertions, and Accept wrote one of them onto B.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_SUGGESTIONS}.data", Ids.TC_LIST_ITEM)
  pattern = dep["inputs"][0]

  response = dash_http.fire(
      dash_client,
      dep,
      {dash_http.address(pattern): [(0, 1), (1, 1)]},
      changed=[dash_http.pattern_address(pattern, 1)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 1
  assert values[f"{Ids.STORE_SUGGESTIONS}.data"] is None
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None


def test_a_deep_link_to_another_test_case_clears_the_suggestions(
    dash_client, callback_errors
):
  """The same move from the address bar, which the back button also makes."""
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_SUGGESTIONS}.data", "url")

  response = dash_http.fire(
      dash_client,
      dep,
      {
          "url.search": "?test_case_id=22",
          f"{Ids.STORE_BUILDER}.data": _TEST_CASES,
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 1
  assert values[f"{Ids.STORE_SUGGESTIONS}.data"] is None
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None


def test_landing_on_the_test_case_already_open_clears_nothing(
    dash_client, callback_errors
):
  """Clearing on every URL change would throw a run's suggestions away.

  ``update_url_on_test_case_select`` writes the same query string back after a
  click, so this callback fires again with the selection it already agrees
  with. That arm returns no_update for all three outputs.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_SUGGESTIONS}.data", "url")

  response = dash_http.fire(
      dash_client,
      dep,
      {
          "url.search": "?test_case_id=22",
          f"{Ids.STORE_BUILDER}.data": _TEST_CASES,
          f"{Ids.STORE_SELECTED_INDEX}.data": 1,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert _values(response) == {}


def test_adding_a_test_case_clears_both_stores(
    dash_client, callback_errors, seeded
):
  """The fourth callback that moves the selection, and the one left out.

  sync_selection_from_url does not rescue it. The new row is not named in the
  query string, and when the new index happens to equal the one already
  selected that callback returns no_update for everything.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.STORE_SUGGESTIONS}.data", Ids.TC_PLAYGROUND_ADD_BTN
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.TC_PLAYGROUND_ADD_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": _TEST_CASES,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.TC_PLAYGROUND_ADD_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 2
  assert len(values[f"{Ids.STORE_BUILDER}.data"]) == 3
  assert values[f"{Ids.STORE_SUGGESTIONS}.data"] is None
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None


def test_the_accept_path_writes_whatever_the_store_holds(
    dash_client, callback_errors
):
  """Why the clearing has to happen, in the callback that does the writing.

  handle_inline_suggestion pairs the store with the selected index and has no
  way to tell which test case the suggestions were raised for. The test case
  here carries no id, so the write stops at the store instead of reaching
  _sync_suite, and the store is what render_assertion_list and the next save
  both read.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.STORE_SUGGESTIONS}.data",
      Ids.INLINE_SUG_ADD_BTN,
      Ids.INLINE_SUG_REJECT_BTN,
  )
  accept = dep["inputs"][0]
  unsaved = [{"question": "How many customers are there?", "asserts": []}]

  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(accept): [(0, 1)],
          dash_http.address(dep["inputs"][1]): [(0, None)],
          f"{Ids.STORE_SUGGESTIONS}.data": _SUGGESTIONS,
          f"{Ids.STORE_BUILDER}.data": unsaved,
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          "url.pathname": "/test_suites/edit/1",
      },
      changed=[dash_http.pattern_address(accept, 0)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  written = values[f"{Ids.STORE_BUILDER}.data"][0]["asserts"]
  assert [a["value"] for a in written] == ["orders"], (
      "the accepted suggestion lands on the selected test case, whichever one"
      " that is"
  )
