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

"""The contains/regex selector on the assertion editor.

Text contains and query contains both take a value and look for it in the
trace. Regex mode reads that value as a pattern instead of a substring. The
selector is the only thing that says which, so it has to be visible for exactly
those two types, and what it is set to has to survive a save and a reopen.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Iterator
from unittest import mock

import dash
import dash_mantine_components as dmc
from prism.common.schemas.assertion import MatchMode
from prism.ui.callbacks import test_suite_questions_callbacks
from prism.ui.ids import TestSuiteIds
import pytest

# Importing either of these registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import
from tests.ui import dash_http

# The two types that take a match mode, and one of each kind that does not.
_CONTAINS_TYPES = ["text-contains", "query-contains"]
_OTHER_TYPES = [
    "ai-judge",
    "chart-check-type",
    "data-check-row",
    "duration-max-ms",
    "looker-query-match",
]


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


def _all_page_components() -> list[Any]:
  """Every component in every registered page layout."""
  components = []
  for page in dash.page_registry.values():
    layout = page.get("layout")
    if callable(layout):
      try:
        layout = layout()
      except TypeError:
        continue
    if layout is not None:
      components.extend(_walk(layout))
  return components


@pytest.fixture(name="page_components", scope="module")
def _page_components() -> list[Any]:
  return _all_page_components()


def _find(components: list[Any], component_id: str) -> Any:
  found = [c for c in components if getattr(c, "id", None) == component_id]
  assert len(found) == 1, f"expected one {component_id}, got {len(found)}"
  return found[0]


def test_the_editor_has_a_mode_selector(page_components):
  """All three editors share one component, so all three get the selector."""
  field = _find(page_components, TestSuiteIds.TC_ASSERT_MODE)

  assert isinstance(field, dmc.SegmentedControl)
  assert [d["value"] for d in field.data] == ["contains", "regex"]
  assert [d["label"] for d in field.data] == ["Text Match", "Regex Match"]


def test_the_selector_opens_on_contains(page_components):
  """Contains is what the assertion did before the mode existed.

  Every stored assertion predates the field, so the default has to be the
  behaviour they already have.
  """
  field = _find(page_components, TestSuiteIds.TC_ASSERT_MODE)

  assert field.value == MatchMode.CONTAINS.value


def test_the_selector_starts_hidden(page_components):
  """No type is selected when the editor opens, so nothing takes a mode yet."""
  field = _find(page_components, TestSuiteIds.TC_ASSERT_MODE)

  assert field.style == {"display": "none"}


def _mode_style(assert_type: str | None) -> Any:
  """The mode selector's style, found by output name rather than by position.

  It used to read the last element of the tuple. Two minRows outputs were
  appended after it, the helper started returning a row count, and every spec
  below compared that number against a style dict.
  """
  outputs = test_suite_questions_callbacks.update_assertion_ui(assert_type)
  position = dash_http.output_position(TestSuiteIds.TC_ASSERT_MODE, "style")
  return outputs[position]


@pytest.mark.parametrize("assert_type", _CONTAINS_TYPES)
def test_picking_a_contains_type_shows_the_selector(assert_type):
  """Picking text contains has to reveal the choice between the two modes.

  Showing it means clearing the inline display, not setting one. A
  SegmentedControl lays its options out with flex, and display:block stacked
  Contains over Regex with no pill behind them, spilling over the value box.
  """
  assert _mode_style(assert_type) == {}


@pytest.mark.parametrize("assert_type", _OTHER_TYPES)
def test_every_other_type_hides_the_selector(assert_type):
  """A row count has no substring to match, so the choice would mean nothing."""
  assert _mode_style(assert_type) == {"display": "none"}


def test_clearing_the_type_hides_the_selector():
  """Nothing selected is not a contains type either."""
  assert _mode_style(None) == {"display": "none"}


@pytest.fixture(name="suite_client")
def _suite_client():
  """Patches the client the suite questions callbacks reach for."""
  with mock.patch(
      "prism.ui.callbacks.test_suite_questions_callbacks.get_client"
  ) as factory:
    client = factory.return_value.suites
    client.validate_assertion.return_value = None
    yield client


def _save(assert_type: str, value: str, mode: str, suite_client):
  """Saves one assertion off the modal and returns it as the store holds it.

  The test case carries an id and the pathname names a suite. Together they
  are what sends the save on to _sync_suite, which is the only thing here that
  writes. With the id left None the callback edits the store in place and
  returns, so the mode could be dropped between validate_assertion and the
  server and the specs below would still pass on the argument they had
  already seen.
  """
  # Echoes a copy, the way the real sync_suite hands back the rows the server
  # stored. A copy, so reading the result cannot read the object the callback
  # passed in.
  suite_client.sync_suite.side_effect = (
      lambda suite_id, test_cases: copy.deepcopy(test_cases)
  )

  returned = test_suite_questions_callbacks.save_assertion_from_modal(
      1,  # n_clicks
      [{"id": 7, "question": "q", "asserts": []}],
      0,  # selected_index
      assert_type,
      value,
      "",  # yaml
      mode,
      None,  # chart type
      True,  # accuracy
      None,  # edit index
      "/test_suites/edit/4",
  )

  suite_client.validate_assertion.assert_called_once()
  suite_id, _ = suite_client.sync_suite.call_args.args
  assert suite_id == 4, "The save went somewhere other than the open suite."

  store = returned[0]
  (written,) = store[0]["asserts"]
  return written


@pytest.mark.parametrize("assert_type", _CONTAINS_TYPES)
@pytest.mark.parametrize("mode", ["contains", "regex"])
def test_saving_keeps_the_mode_that_was_picked(suite_client, assert_type, mode):
  """Picking regex and not having it stored is the same as not having it."""
  saved = _save(assert_type, "revenue", mode, suite_client)

  assert saved["mode"] == mode


def test_saving_a_type_without_a_mode_does_not_invent_one(suite_client):
  """The schema forbids extra fields, so a stray mode fails validation."""
  saved = _save("chart-check-type", "bar", "regex", suite_client)

  assert "mode" not in saved


def test_reopening_an_assertion_shows_the_mode_it_was_saved_with(suite_client):
  """The editor has to read back what it wrote, or the mode looks unsaved."""
  del suite_client  # Opening the modal does not reach the client.
  stored = {
      "type": "query-contains",
      "value": r"SUM\(.*\)",
      "mode": "regex",
      "weight": 1.0,
  }
  context = mock.Mock()
  edit_button = json.dumps(
      {"index": 0, "type": TestSuiteIds.ASSERT_EDIT_BTN}, sort_keys=True
  )
  context.triggered = [{"prop_id": f"{edit_button}.n_clicks", "value": 1}]

  with mock.patch.object(dash, "callback_context", context):
    opened = test_suite_questions_callbacks.open_assertion_modal(
        None,
        [1],
        [{"id": 1, "question": "q", "asserts": [stored]}],
        0,
    )

  # (opened, type, value, yaml, mode, ...)
  assert opened[4] == "regex"


def test_reopening_an_assertion_saved_before_the_mode_existed(suite_client):
  """Rows stored without the field read back as contains, not as blank."""
  del suite_client
  stored = {"type": "text-contains", "value": "revenue", "weight": 1.0}
  context = mock.Mock()
  edit_button = json.dumps(
      {"index": 0, "type": TestSuiteIds.ASSERT_EDIT_BTN}, sort_keys=True
  )
  context.triggered = [{"prop_id": f"{edit_button}.n_clicks", "value": 1}]

  with mock.patch.object(dash, "callback_context", context):
    opened = test_suite_questions_callbacks.open_assertion_modal(
        None,
        [1],
        [{"id": 1, "question": "q", "asserts": [stored]}],
        0,
    )

  assert opened[4] == MatchMode.CONTAINS.value


def test_saving_invalid_regex_returns_clean_validation_error():
  """Saving an invalid regex returns the concise compiler error."""
  returned = test_suite_questions_callbacks.save_assertion_from_modal(
      1,
      [{"id": 7, "question": "q", "asserts": []}],
      0,
      "text-contains",
      "order_[a-z",
      "",
      "regex",
      None,
      True,
      None,
      "/test_suites/edit/4",
  )
  assert returned[0] == dash.no_update
  assert returned[1] is True
  assert (
      returned[2]
      == "Invalid regular expression: unterminated character set at position 6"
  )
  assert returned[3] == {"display": "block"}
