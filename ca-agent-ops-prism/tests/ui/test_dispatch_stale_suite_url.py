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

"""Saving a suite from a URL that names no suite.

The save reads the suite id out of the path. ``id_from_pathname`` raises
ValueError when the path does not end in a number, and that reached nothing
but the blanket ``handle_errors``, so a stale tab or a hand-edited address bar
produced a red error toast. There is nothing for the reader to do about it and
nothing was written, so the no-op is the honest answer.

The Edit Configuration modal is the only way to rename a suite. A second
callback took a page Save button as its input, and that id was rendered as a
hidden ``html.Div`` on the view and new pages. A Div has no ``n_clicks``, so
nothing could fire it. Both the callback and the test that fired a control
nobody can press are gone.

``tests/ui/test_dispatch_suite_authoring.py`` covers the save that works.
"""

from __future__ import annotations

from typing import Any

from prism.server.models.suite import TestSuite as SuiteRow
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import TestSuiteIds
import pytest
from tests.ui import dash_http

# Both are paths the app itself produces. /test_suites is the list page, and
# the trailing-slash form of a view URL is what a copied link often becomes.
_NO_ID = "/test_suites"
_NOT_A_NUMBER = "/test_suites/view/"


def _outputs(dep: dict[str, Any]) -> list[dict[str, Any]]:
  """The dep's outputs as a list, however many it declares."""
  grouping = dash_http.outputs_grouping(dep["output"])
  return grouping if isinstance(grouping, list) else [grouping]


def _callback(
    deps: list[dict[str, Any]], input_address: str, output_id: str
) -> dict[str, Any]:
  """The one callback taking ``input_address`` and writing ``output_id``.

  Eleven callbacks write ``redirect-handler.href`` with allow_duplicate, so the
  output does not name one of them on its own.
  """
  matches = [
      dep
      for dep in deps
      if any(dash_http.address(i) == input_address for i in dep["inputs"])
      and any(o["id"] == output_id for o in _outputs(dep))
  ]
  assert len(matches) == 1, (
      f"expected one callback from {input_address} to {output_id}, found"
      f" {len(matches)}"
  )
  return matches[0]


def _save_from_the_modal(dash_client, pathname: str, name: str | None):
  """Fires the Edit Configuration modal's Save button."""
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{TestSuiteIds.MODAL_CONFIG_SAVE_BTN}.n_clicks",
      REDIRECT_HANDLER,
  )
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{TestSuiteIds.MODAL_CONFIG_SAVE_BTN}.n_clicks": 1,
          "url.pathname": pathname,
          f"{TestSuiteIds.NAME}.value": name,
          f"{TestSuiteIds.DESC}.value": "Rewritten description",
      },
      changed=[f"{TestSuiteIds.MODAL_CONFIG_SAVE_BTN}.n_clicks"],
  )


def _assert_quiet(response, callback_errors) -> None:
  """Nothing written, nothing logged, and no toast raised.

  An output returned as no_update is left out of the response, so the empty
  body is the assertion that the save did not happen. The toast is separate:
  ``handle_errors`` sends it through ``dash.set_props``, which arrives in
  ``sideUpdate`` and not in the response.
  """
  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)

  assert body.get("response", {}) == {}, "navigated away"
  assert NOTIFICATION_CONTAINER not in body.get(
      "sideUpdate", {}
  ), "raised a toast"
  callback_errors.assert_none()


@pytest.mark.parametrize("pathname", [_NO_ID, _NOT_A_NUMBER])
def test_saving_the_config_modal_from_a_path_with_no_suite_id_does_nothing(
    dash_client, callback_errors, db_session, seeded, pathname
):
  """A stale tab is the ordinary way to get here.

  The modal is opened from the suite view page, and the path is read when
  Save is clicked, not when the modal opens. ``id_from_pathname`` used to
  raise into ``handle_errors``, which put a red toast on screen saying
  something had gone wrong with a save that was never going to happen.
  """
  _assert_quiet(
      _save_from_the_modal(dash_client, pathname, "Renamed Suite"),
      callback_errors,
  )

  db_session.expire_all()
  assert db_session.get(SuiteRow, seeded.suite_id).name == seeded.suite_name


def test_saving_a_blank_name_over_a_real_suite_does_nothing(
    dash_client, callback_errors, db_session, seeded
):
  """The name is the only thing identifying a suite in any list.

  Clearing the field and saving would write an empty string into every one of
  them. This arm has always been there; it is pinned because it now shares a
  function with the path guard above and a change to one reaches the other.
  """
  _assert_quiet(
      _save_from_the_modal(
          dash_client, f"/test_suites/view/{seeded.suite_id}", ""
      ),
      callback_errors,
  )

  db_session.expire_all()
  assert db_session.get(SuiteRow, seeded.suite_id).name == seeded.suite_name
