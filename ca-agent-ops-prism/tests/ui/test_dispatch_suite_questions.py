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

"""The test case playground, driven through Dash's HTTP route.

Everything on ``/test_suites/edit/<id>`` runs off two dcc.Stores: the builder
holds the whole suite and the selected index says which row the editor is
pointed at. The callbacks here read those, write the database, and hand the
store back. None of that needs a browser, and all of it is in the POST body.

``test_callback_dispatch.py`` already covers the accuracy switch
(``toggle_assertion_weight``), so it is not repeated here.
"""

from __future__ import annotations

from typing import Any

from prism.client.suite_client import SuitesClient
from prism.common.schemas.assertion import MatchMode
from prism.common.schemas.assertion import TextContains
from prism.server.models.assertion import Assertion
from prism.server.models.example import Example
from prism.server.repositories.example_repository import ExampleRepository
from prism.ui import constants
from prism.ui.callbacks import test_suite_questions_callbacks
from prism.ui.ids import TestSuiteIds as Ids
import pytest
from tests.ui import dash_http

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import


def _callback(
    deps: list[dict[str, Any]], output: str, *inputs: str
) -> dict[str, Any]:
  """The one callback with this output and these Inputs, in order.

  ``dash_http.find`` takes an output on its own, which is not enough here.
  Nine callbacks on this page write STORE_BUILDER with allow_duplicate, so the
  output address does not name one of them. The Input side does.
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

  Dash leaves out every output the callback returned no_update for, so a
  missing key is itself the assertion that nothing was written.
  """
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def _guide(assert_type: str) -> dict[str, str]:
  """The guide entry the editor renders for an assertion type."""
  found = [g for g in constants.ASSERTS_GUIDE if g["name"] == assert_type]
  assert len(found) == 1, f"no guide entry for {assert_type}"
  return found[0]


def _example(db_session, suite_id: int) -> Example:
  """The one example the ``seeded`` fixture put in the suite."""
  return db_session.query(Example).filter_by(test_suite_id=suite_id).one()


def _test_case(example: Example, asserts: list[dict[str, Any]] | None = None):
  """One builder-store row, the shape ``load_playground_data`` writes."""
  return {
      "id": example.id,
      "question": example.question,
      "asserts": asserts or [],
  }


def _editor_state(example: Example, suite_id: int, **extra: Any):
  """The store and URL state every editor callback reads."""
  values = {
      f"{Ids.STORE_BUILDER}.data": [_test_case(example)],
      f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      "url.pathname": f"/test_suites/edit/{suite_id}",
  }
  values.update(extra)
  return values


def test_opening_the_editor_loads_the_suite_the_agents_and_the_breadcrumb(
    dash_client, callback_errors, seeded
):
  """The editor has no content until this callback answers.

  It is the only source of the agent dropdown, and the Run button stays
  disabled without one, so an empty options list is a page that cannot run
  anything. It is also the only writer of the breadcrumb, which is the way back
  to the suite.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_BUILDER}.data", Ids.TC_AGENT_SELECT)

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.TC_AGENT_SELECT}.id": Ids.TC_AGENT_SELECT,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
          "url.search": "",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  values = _values(response)
  assert [tc["question"] for tc in values[f"{Ids.STORE_BUILDER}.data"]] == [
      seeded.question
  ]
  assert values[f"{Ids.TC_AGENT_SELECT}.data"] == [
      {"label": seeded.agent_name, "value": str(seeded.agent_id)}
  ]
  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 0
  assert values[f"{Ids.TC_BREADCRUMB_SUITE_NAME}.children"] == seeded.suite_name
  assert (
      values[f"{Ids.TC_BREADCRUMB_SUITE_NAME}.href"]
      == f"/test_suites/view/{seeded.suite_id}"
  )


def test_the_add_and_test_case_deep_links_land_on_the_right_row(
    dash_client, callback_errors, db_session, seeded
):
  """Both ways into the editor from the suite view page are deep links.

  "Add test case" is ``?action=add``, which creates the row during the page
  load, and clicking a question is ``?test_case_id=N``. Nothing else
  implements either, so a drift in the parsing lands the user on row zero of
  someone else's question with no sign anything went wrong.
  """
  suite_id = seeded.suite_id
  second = ExampleRepository(db_session).create(suite_id, "A second question")
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_BUILDER}.data", Ids.TC_AGENT_SELECT)

  def load(search: str):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ids.TC_AGENT_SELECT}.id": Ids.TC_AGENT_SELECT,
            "url.pathname": f"/test_suites/edit/{suite_id}",
            "url.search": search,
        },
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  values = load(f"?test_case_id={second.id}")
  selected = values[f"{Ids.STORE_SELECTED_INDEX}.data"]
  loaded = values[f"{Ids.STORE_BUILDER}.data"]
  assert loaded[selected]["id"] == second.id

  values = load("?action=add")
  selected = values[f"{Ids.STORE_SELECTED_INDEX}.data"]
  loaded = values[f"{Ids.STORE_BUILDER}.data"]
  assert loaded[selected]["question"] == "New Test Case"
  # The row is created by the load itself, not by a later save.
  assert (
      db_session.query(Example).filter_by(test_suite_id=suite_id).count() == 3
  )

  callback_errors.assert_none()


def test_selecting_a_test_case_and_the_url_do_not_fight_each_other(
    dash_client, callback_errors, seeded
):
  """The store and the URL write to each other, so both need a stop.

  Selecting a row puts ``?test_case_id=`` in the URL and a URL carrying one
  moves the selection. Each returns no_update when the other already agrees,
  and those two guards are the only thing between them and a write loop.
  """
  test_cases = [
      {"id": 11, "question": "first", "asserts": []},
      {"id": 22, "question": "second", "asserts": []},
  ]
  deps = dash_http.dependencies(dash_client)
  del seeded  # Neither callback reads the database.

  to_url = _callback(deps, "url.search", Ids.STORE_SELECTED_INDEX)
  response = dash_http.fire(
      dash_client,
      to_url,
      {
          f"{Ids.STORE_SELECTED_INDEX}.data": 1,
          f"{Ids.STORE_BUILDER}.data": test_cases,
          "url.search": "",
      },
  )
  assert response.status_code == 200, response.data[:2000]
  assert _values(response)["url.search"] == "?test_case_id=22"

  settled = dash_http.fire(
      dash_client,
      to_url,
      {
          f"{Ids.STORE_SELECTED_INDEX}.data": 1,
          f"{Ids.STORE_BUILDER}.data": test_cases,
          "url.search": "?test_case_id=22",
      },
  )
  assert _values(settled) == {}, "rewrote the URL to what it already said"

  from_url = _callback(deps, f"{Ids.STORE_SELECTED_INDEX}.data", "url")
  response = dash_http.fire(
      dash_client,
      from_url,
      {
          "url.search": "?test_case_id=22",
          f"{Ids.STORE_BUILDER}.data": test_cases,
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
  )
  assert response.status_code == 200, response.data[:2000]
  assert _values(response)[f"{Ids.STORE_SELECTED_INDEX}.data"] == 1

  settled = dash_http.fire(
      dash_client,
      from_url,
      {
          "url.search": "?test_case_id=22",
          f"{Ids.STORE_BUILDER}.data": test_cases,
          f"{Ids.STORE_SELECTED_INDEX}.data": 1,
      },
  )
  assert _values(settled) == {}, "reselected the row that was already selected"

  callback_errors.assert_none()


def test_the_save_and_revert_buttons_appear_only_on_an_edit(
    dash_client, callback_errors, seeded
):
  """The group is hidden until the box differs from what is stored.

  Showing it always would offer a Save that writes the text back unchanged,
  and hiding it always would leave no way to commit the edit.
  """
  test_cases = [{"id": 11, "question": "stored", "asserts": [{"type": "x"}]}]
  del seeded
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.TC_CHANGE_ACTIONS_GROUP}.style",
      Ids.TC_INPUT_TEST_CASE,
      Ids.STORE_BUILDER,
  )

  def typed(text: str):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ids.TC_INPUT_TEST_CASE}.value": text,
            f"{Ids.STORE_BUILDER}.data": test_cases,
            f"{Ids.STORE_SELECTED_INDEX}.data": 0,
        },
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  unchanged = typed("stored")
  assert unchanged[f"{Ids.TC_CHANGE_ACTIONS_GROUP}.style"] == {
      "display": "none"
  }
  assert unchanged[f"{Ids.VAL_MSG}-char-count.children"] == "6 chars"
  assert unchanged[f"{Ids.TC_ASSERT_COUNT}.children"] == "1"

  edited = typed("stored and edited")
  assert edited[f"{Ids.TC_CHANGE_ACTIONS_GROUP}.style"] == {"display": "flex"}
  assert edited[f"{Ids.VAL_MSG}-char-count.children"] == "17 chars"

  callback_errors.assert_none()


def test_revert_restores_the_saved_question(dash_client, callback_errors):
  """Revert reads the store, which is the last value that reached the database.

  Reverting to the box's own value, or to the wrong row, would leave the edit
  in place and the Save group on screen with nothing to undo it.
  """
  test_cases = [
      {"id": 11, "question": "first", "asserts": []},
      {"id": 22, "question": "second", "asserts": []},
  ]
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.TC_INPUT_TEST_CASE}.value", Ids.TC_REVERT_BTN)

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.TC_REVERT_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": test_cases,
          f"{Ids.STORE_SELECTED_INDEX}.data": 1,
      },
      changed=[f"{Ids.TC_REVERT_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert _values(response)[f"{Ids.TC_INPUT_TEST_CASE}.value"] == "second"


# Every assertion type in ASSERTS_GUIDE, the input the modal saves it from,
# and the box its worked example goes in. chart-check-type has no example box:
# it is a Select, so the choices are the example.
_EDITOR_FIELDS = [
    ("text-contains", Ids.TC_ASSERT_VALUE, Ids.ASSERT_EXAMPLE_VALUE),
    ("query-contains", Ids.TC_ASSERT_VALUE, Ids.ASSERT_EXAMPLE_VALUE),
    ("ai-judge", Ids.TC_ASSERT_VALUE, Ids.ASSERT_EXAMPLE_VALUE),
    ("duration-max-ms", Ids.TC_ASSERT_VALUE, Ids.ASSERT_EXAMPLE_VALUE),
    # Deprecated, and the last time it was left out of a list like this the
    # Assertion Type select lost it, so an existing assertion of this type
    # opened the select blank and saving changed its type.
    ("latency-max-ms", Ids.TC_ASSERT_VALUE, Ids.ASSERT_EXAMPLE_VALUE),
    ("data-check-row-count", Ids.TC_ASSERT_VALUE, Ids.ASSERT_EXAMPLE_VALUE),
    ("data-check-row", Ids.TC_ASSERT_YAML, Ids.ASSERT_EXAMPLE_YAML),
    ("looker-query-match", Ids.TC_ASSERT_YAML, Ids.ASSERT_EXAMPLE_YAML),
    ("chart-check-type", Ids.ASSERT_CHART_TYPE, None),
]

_EDITOR_INPUTS = [
    Ids.TC_ASSERT_VALUE,
    Ids.TC_ASSERT_YAML,
    Ids.ASSERT_CHART_TYPE,
]


@pytest.mark.parametrize("assert_type,field,example_box", _EDITOR_FIELDS)
def test_each_assertion_type_shows_the_field_it_is_saved_from(
    dash_client, callback_errors, assert_type, field, example_box
):
  """The save reads one input per type, and it has to be the visible one.

  ``save_assertion_from_modal`` takes the YAML box for data-check-row and
  looker-query-match, the Select for chart-check-type and the text box for
  everything else. Show the wrong one and the user fills in a field the save
  never reads, so Save reports an empty value on a form that looks complete.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.ASSERT_GUIDE_TITLE}.children", Ids.TC_ASSERT_TYPE
  )

  response = dash_http.fire(
      dash_client, dep, {f"{Ids.TC_ASSERT_TYPE}.value": assert_type}
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  for candidate in _EDITOR_INPUTS:
    expected = "block" if candidate == field else "none"
    assert values[f"{candidate}.style"]["display"] == expected, candidate

  guide = _guide(assert_type)
  assert values[f"{Ids.ASSERT_GUIDE_TITLE}.children"] == guide["label"]
  assert values[f"{Ids.ASSERT_GUIDE_DESC}.children"] == guide["description"]

  if example_box is None:
    assert values[f"{Ids.ASSERT_EXAMPLE_CONTAINER}.style"] == {
        "display": "none"
    }
  else:
    assert values[f"{example_box}.value"] == guide["example"]
    assert values[f"{example_box}.style"]["display"] == "block"
    assert values[f"{Ids.ASSERT_EXAMPLE_CONTAINER}.style"] == {}


# One stored assertion of each shape the reopen has to rebuild, and the field
# it has to come back in.
_REOPEN_CASES = [
    (
        {"type": "text-contains", "value": "revenue", "weight": 1.0},
        {f"{Ids.TC_ASSERT_VALUE}.value": "revenue"},
    ),
    (
        {"type": "chart-check-type", "value": "bar", "weight": 1.0},
        {f"{Ids.ASSERT_CHART_TYPE}.value": "bar"},
    ),
    (
        {
            "type": "data-check-row",
            "columns": {"city": "Paris"},
            "weight": 1.0,
        },
        {f"{Ids.TC_ASSERT_YAML}.value": "city: Paris\n"},
    ),
    (
        {
            "type": "looker-query-match",
            "params": {"model": "thelook", "explore": "orders"},
            "weight": 1.0,
        },
        {f"{Ids.TC_ASSERT_YAML}.value": "explore: orders\nmodel: thelook\n"},
    ),
]


@pytest.mark.parametrize("stored,expected", _REOPEN_CASES)
def test_reopening_an_assertion_loads_every_field_it_was_saved_with(
    dash_client, callback_errors, stored, expected
):
  """A blank reopen is a silent duplicate, not a visible failure.

  The load is wrapped in a broad except that logs and falls through to the Add
  defaults, so a failure reopens the modal titled "Add Assertion" with an empty
  edit index. Saving then appends a second assertion instead of replacing the
  one being edited. ``callback_errors`` catches the swallowed exception and the
  title catches the fall-through on its own.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.ASSERT_MODAL_TITLE_TEXT}.children",
      Ids.ASSERT_MODAL_OPEN_BTN,
      Ids.ASSERT_EDIT_BTN,
  )
  edit_buttons = dep["inputs"][1]

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.ASSERT_MODAL_OPEN_BTN}.n_clicks": None,
          dash_http.address(edit_buttons): [(0, None), (1, 1)],
          f"{Ids.STORE_BUILDER}.data": [{
              "id": 1,
              "question": "q",
              "asserts": [{"type": "ai-judge", "value": "other"}, stored],
          }],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
      changed=[dash_http.pattern_address(edit_buttons, 1)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.ASSERT_MODAL}.opened"] is True
  assert values[f"{Ids.ASSERT_MODAL_TITLE_TEXT}.children"] == "Edit Assertion"
  assert values[f"{Ids.TC_ASSERT_TYPE}.value"] == stored["type"]
  assert values[f"{Ids.STORE_ASSERT_EDIT_INDEX}.data"] == 1
  # Delete is only offered on an assertion that exists.
  assert values[f"{Ids.ASSERT_MODAL_DELETE_BTN}.style"] == {"display": "block"}
  for address, value in expected.items():
    assert values[address] == value


def test_reopening_a_diagnostic_assertion_leaves_the_switch_off(
    dash_client, callback_errors
):
  """Weight zero is the whole difference between diagnostic and accuracy.

  The switch is checked from ``weight > 0``. Defaulting it to on would turn a
  diagnostic assertion into one that counts towards the run score the first
  time anyone opens it and saves.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.ASSERT_MODAL_TITLE_TEXT}.children",
      Ids.ASSERT_MODAL_OPEN_BTN,
      Ids.ASSERT_EDIT_BTN,
  )
  edit_buttons = dep["inputs"][1]

  def reopen(weight: float):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ids.ASSERT_MODAL_OPEN_BTN}.n_clicks": None,
            dash_http.address(edit_buttons): [(0, 1)],
            f"{Ids.STORE_BUILDER}.data": [{
                "id": 1,
                "question": "q",
                "asserts": [
                    {"type": "text-contains", "value": "v", "weight": weight}
                ],
            }],
            f"{Ids.STORE_SELECTED_INDEX}.data": 0,
        },
        changed=[dash_http.pattern_address(edit_buttons, 0)],
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)[f"{Ids.TC_ASSERT_WEIGHT}.checked"]

  assert reopen(0.0) is False
  assert reopen(1.0) is True
  callback_errors.assert_none()


def test_opening_the_modal_to_add_offers_no_delete(
    dash_client, callback_errors
):
  """Add and Edit are one modal, so Add has to clear what Edit set.

  A leftover edit index is the bad one: the next Save overwrites the assertion
  that was open last time instead of adding the new one.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.ASSERT_MODAL_TITLE_TEXT}.children",
      Ids.ASSERT_MODAL_OPEN_BTN,
      Ids.ASSERT_EDIT_BTN,
  )
  edit_buttons = dep["inputs"][1]

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.ASSERT_MODAL_OPEN_BTN}.n_clicks": 1,
          dash_http.address(edit_buttons): [(0, None)],
          f"{Ids.STORE_BUILDER}.data": [{
              "id": 1,
              "question": "q",
              "asserts": [{"type": "text-contains", "value": "v"}],
          }],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
      changed=[f"{Ids.ASSERT_MODAL_OPEN_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.ASSERT_MODAL_TITLE_TEXT}.children"] == "Add Assertion"
  assert values[f"{Ids.ASSERT_MODAL_DELETE_BTN}.style"] == {"display": "none"}
  assert values[f"{Ids.STORE_ASSERT_EDIT_INDEX}.data"] is None
  assert values[f"{Ids.TC_ASSERT_TYPE}.value"] is None
  assert values[f"{Ids.TC_ASSERT_MODE}.value"] == MatchMode.CONTAINS.value


# Each type the save builds a payload for, the input it reads, and the key the
# schema wants it under. All nine, because the schemas set extra="forbid", so
# the wrong key is a validation error and the modal will not close.
_SAVE_CASES = [
    ("data-check-row", "yaml", "city: Paris\n", "columns", {"city": "Paris"}),
    (
        "looker-query-match",
        "yaml",
        "model: thelook\nexplore: orders\n",
        "params",
        {
            "model": "thelook",
            "explore": "orders",
            "fields": None,
            "filters": None,
            "sorts": None,
            "limit": None,
        },
    ),
    ("duration-max-ms", "value", "5000", "value", 5000.0),
    ("latency-max-ms", "value", "5000", "value", 5000.0),
    ("data-check-row-count", "value", "3", "value", 3),
    ("ai-judge", "value", "Be polite", "value", "Be polite"),
    ("text-contains", "value", "9 orders", "value", "9 orders"),
    ("query-contains", "value", "FROM orders", "value", "FROM orders"),
    ("chart-check-type", "chart", "bar", "value", "bar"),
]


@pytest.mark.parametrize("assert_type,box,typed,key,stored", _SAVE_CASES)
def test_each_assertion_type_saves_the_payload_its_schema_expects(
    dash_client,
    callback_errors,
    db_session,
    seeded,
    assert_type,
    box,
    typed,
    key,
    stored,
):
  """One save builds nine different payloads, one for each assertion type.

  data-check-row puts the parsed YAML under ``columns`` and looker-query-match
  under ``params``, chart-check-type reads the Select, and the rest go under
  ``value``. Nothing downstream repairs a wrong key: the schema rejects it, the
  save returns the validation message, and the modal stays open over an
  assertion the user believes is stored.
  """
  example = _example(db_session, seeded.suite_id)
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.ASSERT_MODAL}.opened", Ids.ASSERT_MODAL_CONFIRM_BTN
  )

  response = dash_http.fire(
      dash_client,
      dep,
      _editor_state(
          example,
          seeded.suite_id,
          **{
              f"{Ids.ASSERT_MODAL_CONFIRM_BTN}.n_clicks": 1,
              f"{Ids.TC_ASSERT_TYPE}.value": assert_type,
              f"{Ids.TC_ASSERT_VALUE}.value": typed if box == "value" else "",
              f"{Ids.TC_ASSERT_YAML}.value": typed if box == "yaml" else "",
              f"{Ids.TC_ASSERT_MODE}.value": MatchMode.CONTAINS.value,
              f"{Ids.ASSERT_CHART_TYPE}.value": (
                  typed if box == "chart" else None
              ),
              f"{Ids.TC_ASSERT_WEIGHT}.checked": True,
              f"{Ids.STORE_ASSERT_EDIT_INDEX}.data": None,
          },
      ),
      changed=[f"{Ids.ASSERT_MODAL_CONFIRM_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  # A payload the schema refused comes back with the modal still open.
  assert values[f"{Ids.ASSERT_VAL_MSG}.children"] == ""
  assert values[f"{Ids.ASSERT_MODAL}.opened"] is False

  saved = values[f"{Ids.STORE_BUILDER}.data"][0]["asserts"]
  assert len(saved) == 1, saved
  assert saved[0][key] == stored
  assert saved[0]["type"] == assert_type

  db_session.expire_all()
  written = db_session.query(Assertion).filter_by(example_id=example.id).all()
  assert [(a.type.value, a.weight) for a in written] == [(assert_type, 1.0)]


def test_a_bad_save_keeps_the_modal_open_and_shows_why(
    dash_client, callback_errors, db_session, seeded
):
  """Closing the modal is the only signal the user gets that a save worked.

  Both error returns hand back ``opened=True`` and the message. Drift either to
  False and a rejected assertion closes the modal like an accepted one, so the
  user walks away believing it is stored.
  """
  example = _example(db_session, seeded.suite_id)
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.ASSERT_MODAL}.opened", Ids.ASSERT_MODAL_CONFIRM_BTN
  )

  def save(assert_type: str | None, value: str, yaml_text: str):
    response = dash_http.fire(
        dash_client,
        dep,
        _editor_state(
            example,
            seeded.suite_id,
            **{
                f"{Ids.ASSERT_MODAL_CONFIRM_BTN}.n_clicks": 1,
                f"{Ids.TC_ASSERT_TYPE}.value": assert_type,
                f"{Ids.TC_ASSERT_VALUE}.value": value,
                f"{Ids.TC_ASSERT_YAML}.value": yaml_text,
                f"{Ids.TC_ASSERT_MODE}.value": MatchMode.CONTAINS.value,
                f"{Ids.ASSERT_CHART_TYPE}.value": None,
                f"{Ids.TC_ASSERT_WEIGHT}.checked": True,
                f"{Ids.STORE_ASSERT_EDIT_INDEX}.data": None,
            },
        ),
        changed=[f"{Ids.ASSERT_MODAL_CONFIRM_BTN}.n_clicks"],
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  broken_yaml = save("data-check-row", "", "columns: [unclosed\n")
  assert broken_yaml[f"{Ids.ASSERT_MODAL}.opened"] is True
  assert broken_yaml[f"{Ids.ASSERT_VAL_MSG}.style"] == {"display": "block"}
  assert broken_yaml[f"{Ids.ASSERT_VAL_MSG}.children"]
  assert f"{Ids.STORE_BUILDER}.data" not in broken_yaml

  # Valid YAML, wrong shape for the schema: value has to be an integer.
  rejected = save("data-check-row-count", "not a number", "")
  assert rejected[f"{Ids.ASSERT_MODAL}.opened"] is True
  assert rejected[f"{Ids.ASSERT_VAL_MSG}.style"] == {"display": "block"}
  assert rejected[f"{Ids.ASSERT_VAL_MSG}.children"]
  assert f"{Ids.STORE_BUILDER}.data" not in rejected

  callback_errors.assert_none()
  db_session.expire_all()
  assert not db_session.query(Assertion).filter_by(example_id=example.id).all()


def test_the_assertion_list_renders_the_selected_test_cases_cards(
    dash_client, callback_errors
):
  """The cards are the only place a run result is attached to an assertion.

  Results are mapped onto the cards by position, so the reasoning under card i
  has to be the result of assertion i. The out-of-range guard is the state
  right after a test case delete, when the store has shrunk and the selected
  index has not caught up yet.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.TC_ASSERT_LIST}.children",
      Ids.STORE_BUILDER,
      Ids.STORE_SELECTED_INDEX,
      Ids.STORE_PLAYGROUND_RESULT,
  )
  test_cases = [
      {"id": 11, "question": "other", "asserts": []},
      {
          "id": 22,
          "question": "selected",
          "asserts": [
              {"type": "text-contains", "value": "alpha", "weight": 1},
              {"type": "text-contains", "value": "beta", "weight": 0},
          ],
      },
  ]
  result = {
      "assertion_results": [
          {"passed": True, "reasoning": "found alpha"},
          {"passed": False, "reasoning": "no beta anywhere"},
      ]
  }

  def render(selected_index):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ids.STORE_BUILDER}.data": test_cases,
            f"{Ids.STORE_SELECTED_INDEX}.data": selected_index,
            f"{Ids.STORE_PLAYGROUND_RESULT}.data": result,
        },
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)[f"{Ids.TC_ASSERT_LIST}.children"]

  cards = render(1)
  assert len(cards) == 2, cards
  first, second = (str(card) for card in cards)
  assert "alpha" in first and "found alpha" in first
  assert "beta" in second and "no beta anywhere" in second
  # Positional, so a swap has to show up as the reasoning on the wrong card.
  assert "no beta anywhere" not in first

  assert render(2) == []
  callback_errors.assert_none()


def test_the_delete_modal_routes_a_test_case_and_an_assertion_apart(
    dash_client, callback_errors
):
  """One modal confirms both deletes, and two stores say which one it is.

  ``confirm_delete_item`` reads the test case index first, so an assertion
  delete that leaves the test case index set deletes the whole question
  instead. Each branch has to set its own store and clear the other.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.MODAL_DELETE_BODY}.children",
      Ids.TC_REMOVE_TEST_CASE_BTN,
      Ids.ASSERT_MODAL_DELETE_BTN,
  )
  remove_buttons = dep["inputs"][0]

  def open_modal(remove_clicks, modal_clicks, changed):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            dash_http.address(remove_buttons): remove_clicks,
            f"{Ids.ASSERT_MODAL_DELETE_BTN}.n_clicks": modal_clicks,
            f"{Ids.STORE_SELECTED_INDEX}.data": 1,
            f"{Ids.STORE_ASSERT_EDIT_INDEX}.data": 2,
        },
        changed=[changed],
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  row = open_modal(
      [(0, None), (1, 1)],
      None,
      dash_http.pattern_address(remove_buttons, 1),
  )
  assert row[f"{Ids.MODAL_DELETE}.opened"] is True
  assert row[f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data"] == 1
  assert row[f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data"] is None
  assert "test case" in row[f"{Ids.MODAL_DELETE_BODY}.children"]

  # The page's own Delete button is not in the list, so it says "current" and
  # the callback resolves it against the selection.
  current = open_modal(
      [("current", 1)],
      None,
      dash_http.pattern_address(remove_buttons, "current"),
  )
  assert current[f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data"] == 1

  assertion = open_modal(
      [(0, None)], 1, f"{Ids.ASSERT_MODAL_DELETE_BTN}.n_clicks"
  )
  assert assertion[f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data"] == 2
  assert assertion[f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data"] is None
  assert "assertion" in assertion[f"{Ids.MODAL_DELETE_BODY}.children"]
  # The assertion modal has to get out of the way of the confirmation.
  assert assertion[f"{Ids.ASSERT_MODAL}.opened"] is False

  callback_errors.assert_none()


def test_confirming_an_assertion_delete_removes_only_that_assertion(
    dash_client, callback_errors, db_session, seeded
):
  """The confirm reads whichever index is set, and picks the test case first.

  With the assertion index set the question has to survive and the one
  assertion has to go, from the store and from the database both.
  """
  example = _example(db_session, seeded.suite_id)
  repo = ExampleRepository(db_session)
  for value in ("first", "second"):
    repo.add_assertion(
        example.id, TextContains(type="text-contains", value=value)
    )
  db_session.commit()
  asserts = [
      {"id": a.id, "type": "text-contains", "value": a.params["value"]}
      for a in example.asserts
  ]

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.MODAL_DELETE}.opened", Ids.MODAL_CONFIRM_REMOVE_BTN
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": [_test_case(example, asserts)],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data": None,
          f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data": 0,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.MODAL_DELETE}.opened"] is False
  assert values[f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data"] is None
  assert values[f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data"] is None
  remaining = values[f"{Ids.STORE_BUILDER}.data"]
  assert [tc["question"] for tc in remaining] == [seeded.question]
  assert [a["value"] for a in remaining[0]["asserts"]] == ["second"]

  db_session.expire_all()
  written = db_session.query(Assertion).filter_by(example_id=example.id).all()
  assert [a.params["value"] for a in written] == ["second"]


def test_confirming_an_assertion_delete_clears_the_last_runs_badges(
    dash_client, callback_errors, db_session, seeded
):
  """``render_assertion_list`` maps the playground result on by position.

  Nothing cleared that store on a delete, so the assertion below the gap moved
  up into the deleted one's slot and wore its pass badge and its reasoning,
  over a run that never saw it. The delete owns the store now and returns None
  for it, which takes every badge off until the next run.
  """
  example = _example(db_session, seeded.suite_id)
  repo = ExampleRepository(db_session)
  for value in ("first", "second"):
    repo.add_assertion(
        example.id, TextContains(type="text-contains", value=value)
    )
  db_session.commit()
  asserts = [
      {"id": a.id, "type": "text-contains", "value": a.params["value"]}
      for a in example.asserts
  ]

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.MODAL_DELETE}.opened", Ids.MODAL_CONFIRM_REMOVE_BTN
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": [_test_case(example, asserts)],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data": None,
          f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data": 0,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert _values(response)[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None


def test_confirming_a_test_case_delete_removes_the_example(
    dash_client, callback_errors, db_session, seeded
):
  """Deleting a question archives the row and moves the selection off it.

  Leaving the index where it was points the editor past the end of the store,
  which renders as an empty editor over a suite that still has questions in it.
  """
  example = _example(db_session, seeded.suite_id)
  second = ExampleRepository(db_session).create(seeded.suite_id, "second")
  db_session.commit()
  test_cases = [_test_case(example), _test_case(second)]

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.MODAL_DELETE}.opened", Ids.MODAL_CONFIRM_REMOVE_BTN
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": test_cases,
          f"{Ids.STORE_SELECTED_INDEX}.data": 1,
          f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data": 1,
          f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data": None,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.MODAL_DELETE}.opened"] is False
  assert [tc["id"] for tc in values[f"{Ids.STORE_BUILDER}.data"]] == [
      example.id
  ]
  assert values[f"{Ids.STORE_SELECTED_INDEX}.data"] == 0
  assert values[f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data"] is None

  db_session.expire_all()
  assert db_session.get(Example, second.id).is_archived


def test_a_failed_delete_toasts_instead_of_dropping_the_row(
    dash_client, callback_errors, db_session, monkeypatch, seeded
):
  """The delete must not be undone on screen while it stands in the database.

  ``delete_example`` is called outside any try, and the pop that follows it
  runs either way. Swallowing the failure would take the question off the page
  and leave it in the database, where it comes back on the next load with no
  explanation.

  The failure goes on ``delete_example`` itself, not on ``get_client``. A
  client that cannot be built is refused before the callback reaches the pop,
  so it says nothing about the order the two run in.
  """
  example = _example(db_session, seeded.suite_id)

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(SuitesClient, "delete_example", boom)

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.MODAL_DELETE}.opened", Ids.MODAL_CONFIRM_REMOVE_BTN
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": [_test_case(example)],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.STORE_DELETE_TEST_CASE_INDEX}.data": 0,
          f"{Ids.STORE_DELETE_ASSERTION_INDEX}.data": None,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.MODAL_CONFIRM_REMOVE_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)
  assert "sideUpdate" in body, "the failure raised no toast"
  assert f"{Ids.STORE_BUILDER}.data" not in _values(response)
  assert any("seeded failure" in m for m in callback_errors.messages)
  callback_errors.clear()

  db_session.expire_all()
  assert not db_session.get(Example, example.id).is_archived


def test_a_failed_suite_write_toasts_and_leaves_the_store_alone(
    dash_client, callback_errors, db_session, monkeypatch, seeded
):
  """``_sync_suite`` does not catch, and six callbacks depend on that.

  It returns the suite as the server stored it, ids and all. Catching the
  failure and carrying on would put rows with no id back in the store, and the
  next save would add duplicates instead of updating them.
  """
  example = _example(db_session, seeded.suite_id)

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(test_suite_questions_callbacks, "get_client", boom)

  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_BUILDER}.data", Ids.TC_SAVE_BTN)
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.TC_SAVE_BTN}.n_clicks": 1,
          f"{Ids.TC_INPUT_TEST_CASE}.value": "an edited question",
          f"{Ids.STORE_BUILDER}.data": [_test_case(example)],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.TC_SAVE_BTN}.n_clicks"],
  )

  assert "sideUpdate" in dash_http.body(response), "the failure raised no toast"
  assert f"{Ids.STORE_BUILDER}.data" not in _values(response)
  assert any("seeded failure" in m for m in callback_errors.messages)
  callback_errors.clear()

  db_session.expire_all()
  assert db_session.get(Example, example.id).question == seeded.question


def test_the_bulk_add_mode_switch_shows_the_yaml_helpers_only_in_advanced(
    dash_client, callback_errors
):
  """Simple mode is one question per line, so the YAML guide would mislead.

  The AI fix button rewrites free text into the structured form, which is only
  something advanced mode can take.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.BTN_BULK_FIX_AI}.style", Ids.TC_BULK_MODE)

  def switch(mode: str):
    response = dash_http.fire(
        dash_client, dep, {f"{Ids.TC_BULK_MODE}.value": mode}
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  simple = switch("simple")
  assert simple["bulk-add-guide-wrapper.style"] == {"display": "none"}
  assert simple[f"{Ids.BTN_BULK_FIX_AI}.style"] == {"display": "none"}
  assert "one per line" in simple["bulk-add-input-title.children"].lower()

  advanced = switch("advanced")
  assert advanced["bulk-add-guide-wrapper.style"] == {"display": "block"}
  assert advanced[f"{Ids.BTN_BULK_FIX_AI}.style"] == {"display": "inline-flex"}

  callback_errors.assert_none()


def test_the_bulk_preview_counts_what_confirm_will_create(
    dash_client, callback_errors
):
  """Confirm is disabled from the preview, the only parse the user is shown.

  ``confirm_bulk_add`` answers a failed parse with three no_updates, so a
  Confirm left enabled over unparseable input is a click that does nothing at
  all.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled",
      Ids.INPUT_BULK_TEXT,
      Ids.TC_BULK_MODE,
  )

  def preview(text: str | None, mode: str):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ids.INPUT_BULK_TEXT}.value": text,
            f"{Ids.TC_BULK_MODE}.value": mode,
        },
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  counted = preview("first question\n\nsecond question\n", "simple")
  assert counted[f"{Ids.VAL_MSG}-bulk-count.children"] == "2 test cases found"
  assert counted[f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled"] is False
  rendered = str(counted[f"{Ids.PREVIEW_BULK_ADD}.children"])
  assert "first question" in rendered and "second question" in rendered

  assert preview("", "simple")[f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled"] is True

  broken = preview("- question: [unclosed\n", "advanced")
  assert broken[f"{Ids.BTN_BULK_ADD_CONFIRM}.disabled"] is True
  assert "Parsing Error" in str(broken[f"{Ids.VAL_MSG}-bulk-count.children"])

  callback_errors.assert_none()


@pytest.mark.parametrize("trailing", ["", "/"])
def test_confirming_bulk_add_writes_one_example_per_question(
    dash_client, callback_errors, db_session, seeded, trailing
):
  """Every line is its own row, and it has to reach the database on Confirm.

  The store is appended to, not replaced, so the question that was already
  there stays. The rows carry ids because the editor cannot save an assertion
  onto a row that has none.

  Both spellings of the URL are fired. The suite id was read by taking
  everything after "/test_suites/edit/", which keeps a trailing slash, so
  Confirm on /test_suites/edit/3/ found no suite and added nothing.
  """
  example = _example(db_session, seeded.suite_id)
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.MODAL_BULK_ADD}.opened", Ids.BTN_BULK_ADD_CONFIRM
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.BTN_BULK_ADD_CONFIRM}.n_clicks": 1,
          f"{Ids.INPUT_BULK_TEXT}.value": "first question\nsecond question",
          f"{Ids.TC_BULK_MODE}.value": "simple",
          f"{Ids.STORE_BUILDER}.data": [_test_case(example)],
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}{trailing}",
      },
      changed=[f"{Ids.BTN_BULK_ADD_CONFIRM}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert values[f"{Ids.MODAL_BULK_ADD}.opened"] is False
  assert values[f"{Ids.INPUT_BULK_TEXT}.value"] == ""
  added = values[f"{Ids.STORE_BUILDER}.data"]
  assert [tc["question"] for tc in added] == [
      seeded.question,
      "first question",
      "second question",
  ]
  assert all(tc["id"] for tc in added)

  db_session.expire_all()
  written = db_session.query(Example).filter_by(test_suite_id=seeded.suite_id)
  assert sorted(e.question for e in written) == sorted(
      [seeded.question, "first question", "second question"]
  )
