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

"""``?action=add`` has to leave the URL once it has been acted on.

The suite editor opens on ``?action=add``, and the page load creates an empty
test case from it. Selecting a row then rewrites the URL to name that row.
That rewrite used to carry the action along, so the address bar kept an
instruction that had already been carried out. Reloading the page, or opening
the link a second time, made another empty test case, and went on making one
every time.

The order of the two guards inside the callback is what this is about. The
"the URL already names this row" short-circuit used to run first, and the row
the action just created is the selected one, so the common case returned
no_update and left ``action=add`` in the bar. ``had_action`` is what holds
that guard back.
"""

from __future__ import annotations

from typing import Any
import urllib.parse

from prism.ui.ids import TestSuiteIds as Ids
from tests.ui import dash_http

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import

_TEST_CASES = [
    {"id": 11, "question": "first", "asserts": []},
    {"id": 22, "question": "second", "asserts": []},
]


def _select_callback(client) -> dict[str, Any]:
  """The one callback turning the selected row into a URL.

  Several callbacks write ``url.search`` with allow_duplicate, so the output
  address does not name one of them. The Input side does.
  """
  matches = [
      dep
      for dep in dash_http.dependencies(client)
      if "url.search" in dep["output"]
      and [i["id"] for i in dep["inputs"]] == [Ids.STORE_SELECTED_INDEX]
  ]
  assert len(matches) == 1, f"expected one such callback, found {len(matches)}"
  return matches[0]


def _select(client, dep, index: int, search: str) -> str | None:
  """Selects a row and returns the URL written, or None for no_update."""
  response = dash_http.fire(
      client,
      dep,
      {
          f"{Ids.STORE_SELECTED_INDEX}.data": index,
          f"{Ids.STORE_BUILDER}.data": _TEST_CASES,
          "url.search": search,
      },
  )
  assert response.status_code == 200, response.data[:2000]
  written = dash_http.body(response).get("response", {})
  return written.get("url", {}).get("search")


def _params(search: str | None) -> dict[str, list[str]]:
  """The written URL as parameters, failing if nothing was written."""
  assert search is not None, "the callback left the URL alone"
  return urllib.parse.parse_qs(search.lstrip("?"))


def test_selecting_a_test_case_drops_the_add_action(
    dash_client, callback_errors
):
  """Arriving on ?action=add and landing on a row leaves the action behind.

  The row is created during the page load, so by the time the selection is
  written the action has been carried out. Anything else in the bar here is an
  instruction that will be obeyed again on the next reload.
  """
  dep = _select_callback(dash_client)

  written = _select(dash_client, dep, 1, "?action=add")

  callback_errors.assert_none()
  assert _params(written) == {"test_case_id": ["22"]}


def test_the_add_action_is_cleared_even_when_the_url_names_that_row(
    dash_client, callback_errors
):
  """The action has to go even when there is no selection change to write.

  This is the case the ``had_action`` flag exists for, and the one that
  actually happens: the page load creates the row, names it in the URL and
  selects it, all before this callback runs. With the equality guard first the
  callback returned no_update and ``action=add`` stayed in the bar.
  """
  dep = _select_callback(dash_client)

  written = _select(dash_client, dep, 1, "?test_case_id=22&action=add")

  callback_errors.assert_none()
  assert _params(written) == {"test_case_id": ["22"]}


def test_reselecting_the_row_the_url_already_names_writes_nothing(
    dash_client, callback_errors
):
  """Without an action to clear, the equality guard still has to hold.

  The URL and the selection write to each other. Rewriting the URL to what it
  already says is the half of that loop this callback is responsible for
  stopping.
  """
  dep = _select_callback(dash_client)

  written = _select(dash_client, dep, 1, "?test_case_id=22")

  callback_errors.assert_none()
  assert written is None


def test_the_rest_of_the_query_string_survives(dash_client, callback_errors):
  """The action is the only parameter dropped, whatever else is in the URL.

  The rewrite rebuilds the whole search string from the parsed parameters, so
  everything that is not ``action`` has to be put back. Nothing on this page
  reads a third parameter today, so losing one would go unnoticed until
  something did.
  """
  dep = _select_callback(dash_client)

  written = _select(dash_client, dep, 0, "?action=add&from=suite_view")

  callback_errors.assert_none()
  assert _params(written) == {
      "test_case_id": ["11"],
      "from": ["suite_view"],
  }
