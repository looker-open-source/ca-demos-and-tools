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

"""Callbacks for the Test Case Playground."""

import json
import logging
import time
from typing import Any
import urllib.parse
import dash
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas.assertion import MatchMode
from prism.common.schemas.example import TestCaseInput
from prism.ui import constants
from prism.ui.components import assertion_components
from prism.ui.components import test_case_components
from prism.ui.constants import CP
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import TestSuiteIds as Ids
from prism.ui.models import ui_state
from prism.ui.utils import clean_empty
from prism.ui.utils import format_timestamp
from prism.ui.utils import typed_callback
import pydantic
import yaml

logger = logging.getLogger(__name__)

# Assertion types whose value is a single number. Everything else that shares
# the value box takes prose or a query fragment.
_SINGLE_LINE_ASSERTS = frozenset({
    "duration-max-ms",
    "latency-max-ms",
    "data-check-row-count",
})

# Resting height of the value box, in rows. It autosizes up to maxRows from
# here, so this only has to be tall enough to show that it takes more than a
# line.
_VALUE_ROWS = 4


def _clean_assertion_for_db(a: dict[str, Any]) -> dict[str, Any]:
  """Removes UI-only metadata fields (starting with _) from assertion dict."""
  return {k: v for k, v in a.items() if not k.startswith("_")}


def _validation_fields(e: Exception) -> str | None:
  """The field paths a rejected bulk import may name, or None.

  str() on a pydantic error prints input_value=, which is the whole rejected
  test case, and a link to errors.pydantic.dev. The field paths say as much
  about what to fix without putting the value back on the page. See
  agent_detail_callbacks._golden_query_error.

  BulkImportService.parse_yaml re-raises as ValueError("Invalid format: ..."),
  so the pydantic error is only reachable through __cause__. None means there
  was no validation error in the chain and the failure is not the input.
  """
  cause: BaseException | None = e
  while cause is not None:
    if isinstance(cause, pydantic.ValidationError):
      return ", ".join(
          ".".join(str(part) for part in error["loc"])
          for error in cause.errors()
      )
    cause = cause.__cause__
  return None


def _yaml_syntax_problem(e: Exception) -> str | None:
  """What the YAML parser objected to and where, or None.

  Reached through __cause__, the same way the pydantic error is. A typo in the
  textarea is the reader's own text, not a server fault, so it is reported as
  an input error rather than logged. The parser's own str() is five lines of
  caret art quoting the line back, which does not fit in an alert.
  """
  cause: BaseException | None = e
  while cause is not None:
    if isinstance(cause, yaml.MarkedYAMLError):
      if cause.problem_mark is None:
        return cause.problem
      return f"{cause.problem}, at line {cause.problem_mark.line + 1}"
    cause = cause.__cause__
  return None


def _sync_suite(
    pathname: str | None, test_cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
  """Writes the whole suite back, and returns it with the ids the server set.

  A failed write propagates. Six callbacks used to log it and carry on, so a
  save that never reached the database still closed the modal and left the
  store holding rows with no id. @handle_errors turns the raise into a toast
  and returns no_update, which leaves the store on its last good value.
  """
  suite_id = None
  if pathname and "/test_suites/edit/" in pathname:
    parts = pathname.split("/")
    try:
      suite_id = int(parts[parts.index("edit") + 1])
    except (ValueError, IndexError):
      pass

  if suite_id is None:
    logger.warning("Could not determine suite_id from pathname: %s", pathname)
    return test_cases

  return get_client().suites.sync_suite(suite_id, test_cases)


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.TC_AGENT_SELECT, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.TC_BREADCRUMB_SUITE_NAME, CP.CHILDREN),
        (Ids.TC_BREADCRUMB_SUITE_NAME, CP.HREF),
    ],
    inputs=[
        (Ids.TC_AGENT_SELECT, "id"),  # Trigger on component mount
    ],
    state=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
    allow_duplicate=True,
    prevent_initial_call="initial_duplicate",
)
def load_playground_data(_, pathname: str, search: str):
  """Loads test cases and agents when entering the playground."""
  if not pathname or "/test_suites/edit/" not in pathname:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  try:
    parts = pathname.split("/")
    if "edit" not in parts:
      return (
          typed_callback.no_update,
          typed_callback.no_update,
          typed_callback.no_update,
          typed_callback.no_update,
          typed_callback.no_update,
      )
    suite_id_idx = parts.index("edit") + 1
    suite_id = int(parts[suite_id_idx])
  except (ValueError, IndexError):
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  client = get_client()

  newly_added_id = None
  if search:
    parsed_search = urllib.parse.parse_qs(search.lstrip("?"))
    if parsed_search.get("action") == ["add"]:
      new_example = client.suites.add_example(
          suite_id=suite_id, question="New Test Case"
      )
      newly_added_id = new_example.id

  suite = client.suites.get_suite(suite_id)
  examples = client.suites.list_examples(suite_id)
  test_cases = [
      {
          "id": e.id,
          "question": e.question,
          "asserts": [a.model_dump() for a in e.asserts or []],
      }
      for e in examples
  ]

  all_agents = client.agents.list_agents()

  agent_options = [{"label": a.name, "value": str(a.id)} for a in all_agents]

  selected_index = 0 if test_cases else None

  if search:
    parsed = urllib.parse.parse_qs(search.lstrip("?"))
    q_id_str = parsed.get("test_case_id", [None])[0]

    target_id = newly_added_id
    if not target_id and q_id_str:
      try:
        target_id = int(q_id_str)
      except ValueError:
        pass

    if target_id:
      for i, q in enumerate(test_cases):
        if q["id"] == target_id:
          selected_index = i
          break

  suite_name = suite.name if suite else f"Suite {suite_id}"
  suite_href = f"/test_suites/view/{suite_id}"

  return test_cases, agent_options, selected_index, suite_name, suite_href


@typed_callback(
    (Ids.TC_LIST, CP.CHILDREN),
    inputs=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
)
def render_test_case_sidebar(
    test_cases: list[dict[str, Any]], selected_index: int | None
):
  """Renders the sidebar list of test cases.

  Not render_test_case_list: test_suite_callbacks has a different callback
  under that name, and handle_errors logs func.__name__, so a failure in
  either wrote the same line into the error toast's log entry.
  """
  if test_cases is None:
    return typed_callback.no_update

  items = []
  try:
    for i, q in enumerate(test_cases):
      dq = ui_state.TestCaseState(**q)
      active = i == selected_index
      items.append(
          test_case_components.render_test_case_nav_item(dq, i, active=active)
      )
  except Exception:  # pylint: disable=broad-exception-caught
    logger.exception("Failed to render the test case list")
    # Not the exception text. See the note in fetch_remote_config, in
    # agent_detail_callbacks.py.
    return [
        dmc.Alert(
            "Could not render the test cases. The details are in the server"
            " log.",
            color="red",
            variant="light",
        )
    ]
  return items


@typed_callback(
    [(Ids.TC_RUN_BTN, CP.DISABLED)],
    inputs=[(Ids.TC_AGENT_SELECT, CP.VALUE)],
    prevent_initial_call=False,
)
def toggle_run_button(agent_id):
  """Disables run button if no agent selected."""
  return [not bool(agent_id)]


@typed_callback(
    (Ids.TC_ASSERT_LIST, CP.CHILDREN),
    inputs=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
    ],
    prevent_initial_call=True,
)
def render_assertion_list(test_cases, selected_index, result_data):
  """Renders the list of assertions for the selected test case."""
  if test_cases is None or selected_index is None:
    return []

  if selected_index >= len(test_cases):
    return []

  tc = test_cases[selected_index]
  asserts = tc.get("asserts", [])

  results_map = {}
  if result_data:
    # The results come back in the order the assertions were run, so they are
    # matched up by position.
    a_results = result_data.get("assertion_results", [])
    for i, r in enumerate(a_results):
      results_map[i] = r

  return [
      assertion_components.render_assertion_card(
          a, i, result=results_map.get(i)
      )
      for i, a in enumerate(asserts)
  ]


@typed_callback(
    dash.Output("url", CP.SEARCH, allow_duplicate=True),
    inputs=[(Ids.STORE_SELECTED_INDEX, CP.DATA)],
    state=[(Ids.STORE_BUILDER, CP.DATA), ("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_url_on_test_case_select(selected_index, test_cases, current_search):
  """Updates URL search parameters when a test case is selected."""
  if (
      selected_index is None
      or not test_cases
      or selected_index >= len(test_cases)
  ):
    return typed_callback.no_update

  tc_id = test_cases[selected_index].get("id")
  if not tc_id:
    return typed_callback.no_update

  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )
  # action=add is a one-shot instruction, not page state. Carrying it through
  # here left it in the address bar, so every reload of that URL created
  # another empty test case.
  had_action = params.pop("action", None) is not None

  if not had_action and params.get("test_case_id") == [str(tc_id)]:
    return typed_callback.no_update

  params["test_case_id"] = [str(tc_id)]
  return f"?{urllib.parse.urlencode(params, doseq=True)}"


@typed_callback(
    [
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        # Both cleared whenever the selection moves. See the note on
        # handle_test_case_selection below.
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
    ],
    inputs=[("url", CP.SEARCH)],
    state=[(Ids.STORE_BUILDER, CP.DATA), (Ids.STORE_SELECTED_INDEX, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def sync_selection_from_url(search, test_cases, current_index):
  """Syncs selected test case from URL when navigating."""
  nothing = (
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
  )
  if not search or not test_cases:
    return nothing

  params = urllib.parse.parse_qs(search.lstrip("?"))
  q_id_str = params.get("test_case_id", [None])[0]
  if not q_id_str:
    return nothing

  try:
    tc_id = int(q_id_str)
    for i, tc in enumerate(test_cases):
      if tc.get("id") == tc_id:
        if i == current_index:
          return nothing
        return i, None, None
  except ValueError:
    pass

  return nothing


@typed_callback(
    [
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        # Both cleared on every selection change, for the same reason the
        # delete path clears them. render_assertion_list maps the playground
        # result onto the assertions by position and takes the selected index
        # as an Input, so clicking a second test case drew its first
        # assertions wearing the previous one's pass and fail badges and its
        # reasoning, with no run having happened for them. The suggestions
        # store is read by handle_inline_suggestion, which writes the accepted
        # suggestion onto whichever test case is selected now, so a suggestion
        # raised by one test case's run could be saved onto another.
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
    ],
    inputs=[
        dash.Input({"type": Ids.TC_LIST_ITEM, "index": dash.ALL}, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def handle_test_case_selection(list_clicks):
  """Updates selected index based on list click."""
  nothing = (
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
  )
  ctx = dash.callback_context
  if not ctx.triggered:
    return nothing

  # Untouched buttons come through with n_clicks None, so drop them.
  valid_clicks = [c for c in list_clicks if c]
  if not valid_clicks:
    return nothing

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

  # Trigger ID is a JSON string: {"index":0,"type":"..."}
  try:
    trigger_obj = json.loads(trigger_id)
    return trigger_obj["index"], None, None
  except Exception:  # pylint: disable=broad-exception-caught
    return nothing


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        # Adding a test case selects it, so both stores go stale here too.
        # sync_selection_from_url does not rescue this one: the new row has no
        # test_case_id in the URL, and when it lands on the index already
        # selected that callback returns no_update. See the note on
        # handle_test_case_selection.
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
    ],
    inputs=[
        (Ids.TC_PLAYGROUND_ADD_BTN, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def add_new_test_case(n_clicks, current_test_cases, pathname):
  """Adds a new empty test case and selects it (Persisted to DB)."""
  nothing = (
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
  )
  # There was a second Input here, an ALL over
  # {"type": TC_PLAYGROUND_ADD_BTN, "index": ...}. Nothing builds that id; the
  # button the page renders carries the plain string above.
  if not n_clicks:
    return nothing

  try:
    if not pathname or "/test_suites/edit/" not in pathname:
      return nothing
    parts = pathname.split("/")
    suite_id = int(parts[parts.index("edit") + 1])
  except (ValueError, IndexError):
    return nothing

  client = get_client()
  example = client.suites.add_example(
      suite_id=suite_id, question="New Test Case"
  )

  new_tc = {
      "id": example.id,
      "question": example.question,
      "asserts": [],
  }
  updated = (current_test_cases or []) + [new_tc]
  new_index = len(updated) - 1

  return updated, new_index, None, None


@typed_callback(
    [
        (Ids.TC_INPUT_TEST_CASE, CP.VALUE),
        (Ids.TC_ASSERT_TYPE, CP.VALUE),
        (Ids.TC_ASSERT_VALUE, CP.VALUE),
        (Ids.TC_ASSERT_YAML, CP.VALUE),
        (Ids.TC_EDITOR_CONTAINER, "style"),
        (Ids.TC_EDITOR_EMPTY, "style"),
        (Ids.TC_ASSERT_COUNT, CP.CHILDREN),
    ],
    inputs=[
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def sync_editor_selection(selected_index, test_cases):
  """Populates the editor inputs when the selection changes.

  Only the selection. The builder store is State here, so a builder update on
  its own cannot fire this. ``detect_test_case_changes`` is the callback that
  takes it as an Input.
  """
  if (
      selected_index is None
      or not test_cases
      or selected_index >= len(test_cases)
  ):
    return (
        "",
        None,
        "",
        "",
        {"display": "none"},
        {"display": "flex"},
        "0",
    )

  test_case_data = test_cases[selected_index]
  test_case = ui_state.TestCaseState(**test_case_data)

  # `render_assertion_list` owns the assertion list. This only fills in the
  # question text and clears the "Add Assertion" inputs.

  return (
      test_case.question,
      None,
      "",
      "",
      {
          "display": "flex",
          "height": "100%",
          "flexDirection": "column",
          "overflow": "hidden",
          "boxSizing": "border-box",
      },
      {"display": "none"},
      str(len(test_case.asserts)),
  )


@typed_callback(
    [
        (Ids.TC_ASSERT_VALUE, CP.STYLE),
        (Ids.TC_ASSERT_YAML, CP.STYLE),
        (Ids.ASSERT_GUIDE_CONTAINER, CP.STYLE),
        (Ids.ASSERT_GUIDE_TITLE, CP.CHILDREN),
        (Ids.ASSERT_GUIDE_DESC, CP.CHILDREN),
        (Ids.ASSERT_EXAMPLE_VALUE, CP.VALUE),
        (Ids.ASSERT_EXAMPLE_YAML, CP.VALUE),
        (Ids.ASSERT_EXAMPLE_VALUE, CP.STYLE),
        (Ids.ASSERT_EXAMPLE_YAML, CP.STYLE),
        (Ids.ASSERT_EXAMPLE_CONTAINER, CP.STYLE),
        (Ids.ASSERT_CHART_TYPE, CP.STYLE),
        (Ids.ASSERT_VAL_MSG, CP.STYLE),
        (Ids.TC_ASSERT_MODE, CP.STYLE),
        (Ids.TC_ASSERT_VALUE, "minRows"),
        (Ids.ASSERT_EXAMPLE_VALUE, "minRows"),
    ],
    inputs=[(Ids.TC_ASSERT_TYPE, CP.VALUE)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def update_assertion_ui(assert_type: str | None):
  """Updates visibility and description based on assertion type."""
  visible_style = {
      "display": "block",
      "backgroundColor": "#eff6ff",
      "borderColor": "#dbeafe",
  }
  hidden_style = {
      "display": "none",
      "backgroundColor": "#eff6ff",
      "borderColor": "#dbeafe",
  }

  guide = next(
      (g for g in constants.ASSERTS_GUIDE if g["name"] == assert_type), None
  )
  desc = guide["description"] if guide else ""
  title = guide["label"] if guide else ""
  example = guide["example"] if guide else ""

  style_to_use = visible_style if guide else hidden_style
  is_yaml = assert_type in ["looker-query-match", "data-check-row"]
  # Showing the example container clears the inline display so the Stack keeps
  # display:flex and its gap. Setting display:block broke flex and dropped the
  # gap, pushing the example box above the input box.
  container_style = {} if example else {"display": "none"}
  # Contains and regex are two readings of the same value, so the selector
  # only belongs to the types that take one.
  is_contains = assert_type in ["text-contains", "query-contains"]
  # Showing it means clearing the inline display, not setting one. A
  # SegmentedControl lays its options out with flex, and display:block stacked
  # them vertically with no pill behind them, tall enough to spill out of the
  # fixed-height row and over the value box below it.
  mode_style = {} if is_contains else {"display": "none"}
  # The value box is one Textarea shared by every type that takes a value, and
  # it rested at one row for all of them. An AI Judge prompt is a paragraph and
  # a query fragment runs long, so both were written through a slot showing one
  # line at a time. These three take a number, and a number does not need the
  # room.
  is_single_line = assert_type in _SINGLE_LINE_ASSERTS
  value_rows = 1 if is_single_line else _VALUE_ROWS

  if not guide:
    return (
        {"display": "block"},
        {"display": "none"},
        hidden_style,
        "",
        "",
        "",
        "",
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        value_rows,
        value_rows,
    )

  if is_yaml:
    return (
        {"display": "none"},
        {"display": "block"},
        style_to_use,
        title,
        desc,
        "",
        example,
        {"display": "none"},
        {"display": "block"},
        container_style,
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        value_rows,
        value_rows,
    )

  is_chart = assert_type == "chart-check-type"
  return (
      {"display": "none" if is_chart else "block"},
      {"display": "none"},
      style_to_use,
      title,
      desc,
      example if not is_chart else "",
      "",
      {"display": "block" if not is_chart else "none"},
      {"display": "none"},
      container_style if not is_chart else {"display": "none"},
      {"display": "block" if is_chart else "none"},
      {"display": "none"},
      mode_style,
      value_rows,
      value_rows,
  )


@typed_callback(
    [(Ids.TC_ASSERT_WEIGHT, CP.LABEL), (Ids.TC_ASSERT_WEIGHT, CP.COLOR)],
    inputs=[(Ids.TC_ASSERT_WEIGHT, CP.CHECKED)],
    prevent_initial_call=True,
)
def update_assertion_weight_ui(checked: bool):
  """Updates label and color based on checked state."""
  if checked:
    return "Accuracy", "green"
  return "Diagnostic", "gray"


@typed_callback(
    [
        (Ids.ASSERT_MODAL, CP.OPENED),
        (Ids.TC_ASSERT_TYPE, CP.VALUE),
        (Ids.TC_ASSERT_VALUE, CP.VALUE),
        (Ids.TC_ASSERT_YAML, CP.VALUE),
        (Ids.TC_ASSERT_MODE, CP.VALUE),
        (Ids.TC_ASSERT_WEIGHT, CP.CHECKED),
        (Ids.ASSERT_CHART_TYPE, CP.VALUE),
        (Ids.STORE_ASSERT_EDIT_INDEX, CP.DATA),
        (Ids.ASSERT_MODAL_TITLE_TEXT, CP.CHILDREN),
        (Ids.ASSERT_MODAL_DELETE_BTN, CP.STYLE),
        (Ids.ASSERT_VAL_MSG, CP.CHILDREN),
        (Ids.ASSERT_VAL_MSG, CP.STYLE),
    ],
    inputs=[
        (Ids.ASSERT_MODAL_OPEN_BTN, CP.N_CLICKS),
        ({"type": Ids.ASSERT_EDIT_BTN, "index": dash.ALL}, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def open_assertion_modal(_add_clicks, _edit_clicks, test_cases, selected_index):
  """Opens the assertion modal for adding or editing."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return typed_callback.no_update

  trigger_val = ctx.triggered[0]["value"]
  if not trigger_val:
    return typed_callback.no_update

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

  a_type = None
  a_val = ""
  a_yaml = ""
  a_mode = MatchMode.CONTAINS.value
  a_chart_type = None
  a_weight = True
  edit_idx = None
  title = "Add Assertion"
  display_delete = {"display": "none"}

  if Ids.ASSERT_EDIT_BTN in trigger_id:
    try:
      trigger_obj = json.loads(trigger_id)
      edit_idx = trigger_obj["index"]
      if test_cases and selected_index is not None:
        tc = test_cases[selected_index]
        if "asserts" in tc and len(tc["asserts"]) > edit_idx:
          a_dict = tc["asserts"][edit_idx]
          a_type = a_dict.get("type")
          a_weight = a_dict.get("weight", 1) > 0
          a_mode = a_dict.get("mode") or MatchMode.CONTAINS.value

          if a_type in ["data-check-row", "looker-query-match"]:
            val = (
                a_dict.get("columns")
                if a_type == "data-check-row"
                else a_dict.get("params")
            )
            if val:
              a_yaml = yaml.dump(clean_empty(val), default_flow_style=False)
            else:
              a_yaml = ""
          elif a_type == "chart-check-type":
            a_chart_type = str(a_dict.get("value", ""))
          else:
            a_val = str(a_dict.get("value", ""))

          title = "Edit Assertion"
          display_delete = {"display": "block"}
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception("Failed to load the assertion into the editor")
  elif Ids.ASSERT_MODAL_OPEN_BTN in trigger_id:
    # Defaults already set
    pass
  else:
    return typed_callback.no_update

  return (
      True,
      a_type,
      a_val,
      a_yaml,
      a_mode,
      a_weight,
      a_chart_type,
      edit_idx,
      title,
      display_delete,
      "",
      {"display": "none"},
  )


@typed_callback(
    (Ids.ASSERT_MODAL, CP.OPENED),
    inputs=[(Ids.ASSERT_MODAL_CANCEL_BTN_FOOTER, CP.N_CLICKS)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def close_assertion_modal(n_clicks):
  """Closes the assertion modal on Cancel."""
  if not n_clicks:
    return typed_callback.no_update
  return False


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.ASSERT_MODAL, CP.OPENED),
        (Ids.ASSERT_VAL_MSG, CP.CHILDREN),
        (Ids.ASSERT_VAL_MSG, CP.STYLE),
    ],
    inputs=[(Ids.ASSERT_MODAL_CONFIRM_BTN, CP.N_CLICKS)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.TC_ASSERT_TYPE, CP.VALUE),
        (Ids.TC_ASSERT_VALUE, CP.VALUE),
        (Ids.TC_ASSERT_YAML, CP.VALUE),
        (Ids.TC_ASSERT_MODE, CP.VALUE),
        (Ids.ASSERT_CHART_TYPE, CP.VALUE),
        (Ids.TC_ASSERT_WEIGHT, CP.CHECKED),
        (Ids.STORE_ASSERT_EDIT_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def save_assertion_from_modal(
    n_clicks,
    test_cases,
    selected_index,
    assert_type,
    assert_value,
    assert_yaml_str,
    assert_mode,
    assert_chart_type,
    assert_weight_checked,
    edit_index,
    pathname,
):
  """Saves assertion (new or updated) from modal."""
  if not n_clicks:
    return typed_callback.no_update

  if not assert_type:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        "Please select an assertion type.",
        {"display": "block"},
    )

  client = get_client()
  if assert_type in ["data-check-row", "looker-query-match"]:
    val, yaml_error = client.suites.parse_yaml_safely(assert_yaml_str)
    if yaml_error:
      return (
          typed_callback.no_update,
          True,
          yaml_error,
          {"display": "block"},
      )
  elif assert_type == "chart-check-type":
    val = assert_chart_type
  else:
    val = assert_value

  weight = 1.0 if assert_weight_checked else 0.0
  assertion_data = {"type": assert_type, "weight": weight}

  if assert_type == "data-check-row":
    assertion_data["columns"] = val
  elif assert_type == "looker-query-match":
    assertion_data["params"] = val
  else:
    # The inputs hand back strings, so coerce before pydantic sees them.
    if assert_type in ["latency-max-ms", "duration-max-ms"]:
      try:
        val = float(val)
      except (ValueError, TypeError):
        pass
    elif assert_type == "data-check-row-count":
      try:
        val = int(val)
      except (ValueError, TypeError):
        pass
    elif assert_type in ["text-contains", "query-contains"]:
      assertion_data["mode"] = assert_mode or MatchMode.CONTAINS.value
    assertion_data["value"] = val

  validation_error = client.suites.validate_assertion(assertion_data)
  if validation_error:
    return (
        typed_callback.no_update,
        True,
        validation_error,
        {"display": "block"},
    )

  test_cases = test_cases or []
  if selected_index is not None and len(test_cases) > selected_index:
    tc = test_cases[selected_index]
    if "asserts" not in tc:
      tc["asserts"] = []

    if edit_index is not None and 0 <= edit_index < len(tc["asserts"]):
      # Keep the id, so sync_suite updates that row instead of adding one.
      existing_a = tc["asserts"][edit_index]
      if "id" in existing_a:
        assertion_data["id"] = existing_a["id"]
      tc["asserts"][edit_index] = assertion_data
    else:
      tc["asserts"].append(assertion_data)

    tc_id = tc.get("id")
    if tc_id:
      test_cases = _sync_suite(pathname, test_cases)

  return test_cases, False, "", {"display": "none"}


@typed_callback(
    [
        (Ids.TC_CHANGE_ACTIONS_GROUP, CP.STYLE),
        (Ids.VAL_MSG + "-char-count", CP.CHILDREN),
        (Ids.TC_ASSERT_COUNT, CP.CHILDREN),
    ],
    inputs=[
        (Ids.TC_INPUT_TEST_CASE, CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
    ],
    state=[
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    prevent_initial_call=False,
)
def detect_test_case_changes(value, test_cases, selected_index):
  """Toggles Save/Revert buttons and updates char count."""
  if (
      selected_index is None
      or not test_cases
      or selected_index >= len(test_cases)
  ):
    return {"display": "none"}, "0 chars", "0"

  tc_data = test_cases[selected_index]
  original = tc_data.get("question", "")
  has_changed = value != original

  char_count = f"{len(value or '')} chars"
  style = {"display": "flex"} if has_changed else {"display": "none"}

  assert_count = str(len(tc_data.get("asserts", [])))

  return style, char_count, assert_count


@typed_callback(
    (Ids.STORE_BUILDER, CP.DATA),
    inputs=[(Ids.TC_SAVE_BTN, CP.N_CLICKS)],
    state=[
        (Ids.TC_INPUT_TEST_CASE, CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def save_test_case_text(
    n_clicks, question, current_test_cases, selected_index, pathname
):
  """Persists the test case text to DB and local store on Save click."""
  if not n_clicks or selected_index is None or not current_test_cases:
    return typed_callback.no_update

  if selected_index >= len(current_test_cases):
    return typed_callback.no_update

  current_test_cases[selected_index]["question"] = question

  current_test_cases = _sync_suite(pathname, current_test_cases)

  return current_test_cases


@typed_callback(
    (Ids.TC_INPUT_TEST_CASE, CP.VALUE),
    inputs=[(Ids.TC_REVERT_BTN, CP.N_CLICKS)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def revert_test_case_text(n_clicks, test_cases, selected_index):
  """Reverts the editor text to the last saved value."""
  if not n_clicks or selected_index is None or not test_cases:
    return typed_callback.no_update

  if selected_index >= len(test_cases):
    return typed_callback.no_update

  return test_cases[selected_index].get("question", "")


@typed_callback(
    [
        (Ids.MODAL_DELETE, CP.OPENED),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_DELETE_TEST_CASE_INDEX, CP.DATA),
        (Ids.STORE_DELETE_ASSERTION_INDEX, CP.DATA),
        (Ids.MODAL_DELETE_BODY, CP.CHILDREN),
        (Ids.ASSERT_MODAL, CP.OPENED),
    ],
    inputs=[
        ({"type": Ids.TC_REMOVE_TEST_CASE_BTN, "index": dash.ALL}, CP.N_CLICKS),
        (Ids.ASSERT_MODAL_DELETE_BTN, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_ASSERT_EDIT_INDEX, CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def open_delete_modal(
    _delete_q_clicks,
    _delete_m_clicks,
    selected_index,
    edit_index,
):
  """Opens the delete confirmation modal."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  trigger = ctx.triggered[0]
  trigger_id = trigger["prop_id"].split(".")[0]
  trigger_value = trigger["value"]

  # Dash fires these on init with a count of 0 or None, which is not a click.
  if not trigger_value:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  if "index" in trigger_id and Ids.TC_REMOVE_TEST_CASE_BTN in trigger_id:
    try:
      trigger_obj = json.loads(trigger_id)
      idx = trigger_obj["index"]
      if idx == "current":
        idx = selected_index
      # Sets the test case index and clears the assertion one.
      return (
          True,
          idx,
          idx,
          None,
          "Are you sure you want to delete this test case?",
          typed_callback.no_update,
      )
    except (json.JSONDecodeError, KeyError, IndexError, ValueError):
      pass

  if trigger_id == Ids.ASSERT_MODAL_DELETE_BTN:
    if edit_index is not None:
      return (
          True,
          typed_callback.no_update,
          None,
          edit_index,
          "Are you sure you want to delete this assertion?",
          False,
      )

  return (
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
  )


@typed_callback(
    (Ids.MODAL_DELETE, CP.OPENED),
    inputs=[(Ids.MODAL_DELETE_CANCEL_BTN, CP.N_CLICKS)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def close_delete_modal(_n_clicks):
  """Closes the delete confirmation modal."""
  return False


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.MODAL_DELETE, CP.OPENED),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_DELETE_TEST_CASE_INDEX, CP.DATA),
        (Ids.STORE_DELETE_ASSERTION_INDEX, CP.DATA),
        (Ids.MODAL_DELETE_BODY, CP.CHILDREN),
        # Both cleared on every delete. render_assertion_list maps the
        # playground result onto the assertions by position, so after a delete
        # the survivor below the gap wore the deleted assertion's pass badge.
        # The suggestions were raised against the assertions that were there
        # before, and deleting a test case moves the selection as well. See
        # the note on handle_test_case_selection.
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
    ],
    inputs=[(Ids.MODAL_CONFIRM_REMOVE_BTN, CP.N_CLICKS)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_DELETE_TEST_CASE_INDEX, CP.DATA),
        (Ids.STORE_DELETE_ASSERTION_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def confirm_delete_item(
    n_clicks,
    test_cases,
    selected_index,
    delete_tc_index,
    delete_a_index,
    pathname,
):
  """Deletes a test case or assertion based on which index is set."""
  nothing = (typed_callback.no_update,) * 8
  if not n_clicks or not test_cases:
    return nothing

  suite_id = None
  if pathname and "/test_suites/edit/" in pathname:
    parts = pathname.split("/")
    try:
      suite_id = int(parts[parts.index("edit") + 1])
    except (ValueError, IndexError):
      pass

  if not suite_id:
    logger.error("Could not determine suite_id from pathname: %s", pathname)
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        dmc.Alert(
            "Error: Could not determine suite ID for deletion.", color="red"
        ),
        typed_callback.no_update,
        typed_callback.no_update,
    )

  client = get_client()

  if delete_tc_index is not None:
    if delete_tc_index < len(test_cases):
      tc_id = test_cases[delete_tc_index].get("id")
      if tc_id:
        # Not caught. The pop below runs either way, so swallowing this took
        # the row off the page while it stayed in the database, and it came
        # back on the next load with no explanation.
        client.suites.delete_example(tc_id)
      test_cases.pop(delete_tc_index)
      # Reset the selection to a row that still exists.
      new_selected = None
      if test_cases:
        new_selected = max(0, min(delete_tc_index, len(test_cases) - 1))

      return (
          test_cases,
          False,  # Close Modal
          new_selected,
          None,  # Clear Q-Index
          None,  # Clear A-Index
          typed_callback.no_update,
          None,  # Clear the playground result
          None,  # Clear the suggestions
      )

  if delete_a_index is not None and selected_index is not None:
    if selected_index < len(test_cases):
      tc = test_cases[selected_index]
      if "asserts" in tc and delete_a_index < len(tc["asserts"]):
        tc["asserts"].pop(delete_a_index)

        test_cases = client.suites.sync_suite(suite_id, test_cases)

      return (
          test_cases,
          False,  # Close Modal
          typed_callback.no_update,
          None,  # Clear Q-Index
          None,  # Clear A-Index
          typed_callback.no_update,
          None,  # Clear the playground result
          None,  # Clear the suggestions
      )

  return nothing


@typed_callback(
    [
        (Ids.STORE_START_RUN, CP.DATA),
        (Ids.SIM_CONTEXT_CONTAINER, CP.CHILDREN),
        (Ids.TC_RUN_BTN, "loading"),
        (Ids.SUG_LIST, CP.CHILDREN),
        (Ids.SUG_ACCORDION, "style"),
    ],
    inputs=[(Ids.TC_RUN_BTN, CP.N_CLICKS)],
    prevent_initial_call=True,
)
def start_simulation_run(n_clicks):
  """Triggers the simulation run and shows skeleton UI."""
  if not n_clicks:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        False,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  ts = int(time.time() * 1000)

  context_skeleton = dmc.Stack(
      gap="xs",
      mt="md",
      children=[
          dmc.Skeleton(height=20, width="60%"),
          dmc.Skeleton(height=20, width="40%"),
      ],
  )

  suggestions_skeleton = dmc.Stack(
      gap="md",
      children=[
          dmc.Skeleton(height=80, radius="md"),
          dmc.Skeleton(height=80, radius="md"),
      ],
  )

  # The accordion ships hidden and only render_inline_suggestion_list used to
  # show it, which runs after the agent call returns. On the first run of a
  # page load the skeleton went into a display:none container, so the
  # suggestions area sat empty for the length of the call.
  return (
      {"ts": ts},
      context_skeleton,
      True,
      suggestions_skeleton,
      {"display": "block"},
  )


# Split off from start_simulation_run, and triggered by the store it writes, so
# the skeleton is on screen before the agent call blocks.
@typed_callback(
    [
        (Ids.SIM_CONTEXT_CONTAINER, CP.CHILDREN),
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
        (Ids.TC_RUN_BTN, "loading"),
    ],
    inputs=[(Ids.STORE_START_RUN, CP.DATA)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.TC_AGENT_SELECT, CP.VALUE),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def execute_simulation(
    trigger_data, test_cases_store, selected_index, agent_id
):
  """Runs the test case against the selected agent.

  Scores the assertions and generates suggestions from the result.
  """
  if not trigger_data:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        False,
    )

  example_id = None
  if test_cases_store and selected_index is not None:
    if selected_index < len(test_cases_store):
      example_id = test_cases_store[selected_index].get("id")

  try:
    client = get_client()
    sim_result = client.playground.run_simulation(
        agent_id=int(agent_id), example_id=example_id
    )

    result = sim_result.result_summary
    suggestions_data = sim_result.suggestions_ui
    # Counts only. result_summary carries the agent's response text, and this
    # log goes wherever the server's stdout goes.
    logger.info(
        "Simulation finished with %s assertion results and %s suggestions",
        len(result.get("assertion_results", [])),
        len(suggestions_data) if suggestions_data else 0,
    )

    assertion_results = result.get("assertion_results", [])
    total_assertions = len(assertion_results)
    passed_assertions = sum(1 for r in assertion_results if r.get("passed"))

    # Accuracy is the mean score of the non-diagnostic assertions, the ones
    # carrying a weight above zero.
    accuracy_results = [
        r
        for r in assertion_results
        if r.get("assertion", {}).get("weight", 0) > 0
    ]
    accuracy_score = (
        sum(r.get("score", 0.0) for r in accuracy_results)
        / len(accuracy_results)
        if accuracy_results
        else 0.0
    )
    accuracy_pct = f"{accuracy_score*100:.1f}%"

    # green, the pass colour everywhere else. Mantine has no emerald, so
    # c="emerald.7" fell through to the theme's black and the icon and the
    # background were left uncoloured.
    status_color = "green" if result["passed"] else "red"
    icon = (
        "material-symbols:check-circle"
        if result["passed"]
        else "material-symbols:cancel"
    )

    # Mantine CSS variables, not Tailwind class names. The app ships no
    # Tailwind, so bg-green.0 and border-green.1 matched nothing and the box
    # was flat white with no border whether the run passed or failed. The
    # round that replaced emerald with green fixed the c= prop below and left
    # these.
    context_ui = dmc.Box(
        mt="md",
        p="sm",
        style={
            "backgroundColor": f"var(--mantine-color-{status_color}-0)",
            "border": f"1px solid var(--mantine-color-{status_color}-1)",
            "borderRadius": "var(--mantine-radius-md)",
        },
        children=[
            dmc.Stack(
                gap="xs",
                children=[
                    dmc.Group(
                        justify="space-between",
                        children=[
                            dmc.Group(
                                gap="xs",
                                children=[
                                    DashIconify(
                                        icon=icon,
                                        color=(
                                            "var(--mantine-color-"
                                            f"{status_color}-6)"
                                        ),
                                        width=20,
                                    ),
                                    dmc.Text(
                                        f"{passed_assertions} of"
                                        f" {total_assertions} assertions"
                                        " passed",
                                        fw=700,
                                        c=f"{status_color}.7",
                                    ),
                                ],
                            ),
                            dmc.Group(
                                gap="xs",
                                children=[
                                    dmc.Text(
                                        "Duration:"
                                        f" {result.get('duration_ms', 0)}ms",
                                        size="sm",
                                        c="gray.6",
                                    ),
                                    dmc.Badge(
                                        f"Accuracy: {accuracy_pct}",
                                        color="blue",
                                        variant="light",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    dmc.Text(
                        "Note: Accuracy is the average score of all"
                        " non-diagnostic assertions.",
                        size="xs",
                        c="dimmed",
                        style={"fontStyle": "italic"},
                    ),
                ],
            )
        ],
    )

    return context_ui, result, suggestions_data, False

  except Exception:  # pylint: disable=broad-exception-caught
    logger.exception("Simulation failed")
    # Both stores are cleared, not left alone. Holding them kept the last
    # run's pass and fail badges on the assertions under the error, and left
    # the suggestion skeleton spinning for a list that will never arrive.
    return (
        dmc.Alert(
            "An error occurred during simulation execution. Please check the"
            " logs.",
            color="red",
            title="Simulation Error",
        ),
        None,
        None,
        False,
    )


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
    ],
    inputs=[
        ({"type": Ids.INLINE_SUG_ADD_BTN, "index": dash.ALL}, CP.N_CLICKS),
        ({"type": Ids.INLINE_SUG_REJECT_BTN, "index": dash.ALL}, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_SUGGESTIONS, CP.DATA),
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def handle_inline_suggestion(
    _accept_clicks,
    _reject_clicks,
    suggestions,
    test_cases,
    selected_index,
    pathname,
):
  """Handles accepting or rejecting an inline suggestion."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
    )

  trigger = ctx.triggered[0]
  trigger_id_str = trigger["prop_id"].split(".")[0]
  trigger_value = trigger.get("value")

  logger.debug(
      "handle_inline_suggestion triggered by: %s with value: %s",
      trigger_id_str,
      trigger_value,
  )

  if not trigger_value:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
    )

  try:
    trigger_obj = json.loads(trigger_id_str)
    sug_idx = trigger_obj["index"]
    action_type = trigger_obj["type"]
    logger.info("Action: %s, Index: %s", action_type, sug_idx)
  except (json.JSONDecodeError, KeyError, ValueError):
    logger.info("Failed to parse trigger_id_str: %s", trigger_id_str)
    return (
        typed_callback.no_update,
        typed_callback.no_update,
    )

  if not suggestions or sug_idx >= len(suggestions):
    return (
        typed_callback.no_update,
        typed_callback.no_update,
    )

  suggestion = suggestions[sug_idx]

  updated_test_cases = typed_callback.no_update
  accepted = False
  if action_type == Ids.INLINE_SUG_ADD_BTN:
    if (
        test_cases
        and selected_index is not None
        and selected_index < len(test_cases)
    ):
      tc = test_cases[selected_index]
      current_asserts = tc.get("asserts", [])

      new_assert = _clean_assertion_for_db(suggestion)
      new_assert["weight"] = 1

      updated_asserts = current_asserts + [new_assert]

      tc["asserts"] = updated_asserts
      updated_test_cases = list(test_cases)
      updated_test_cases[selected_index] = tc

      tc_id = tc.get("id")
      if tc_id:
        updated_test_cases = _sync_suite(pathname, updated_test_cases)
      accepted = True

  # Reject always drops the card. Accept only drops it once the assertion is
  # on the test case. This used to run unconditionally, so an Accept that hit
  # the guard above threw the suggestion away without saving it.
  if action_type != Ids.INLINE_SUG_ADD_BTN or accepted:
    new_suggestions = [s for i, s in enumerate(suggestions) if i != sug_idx]
  else:
    new_suggestions = typed_callback.no_update

  return updated_test_cases, new_suggestions


@typed_callback(
    (Ids.SUGGESTION_MODAL, CP.OPENED),
    inputs=[
        (Ids.TC_HISTORY_SUGGESTIONS_BTN, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
)
def open_suggestion_modal(history_clicks):
  """Opens the suggestion modal immediately on click."""
  if not history_clicks:
    return typed_callback.no_update
  return True


# Does not output SUGGESTION_MODAL.opened, even though it fires on the same
# click as open_suggestion_modal above. Two callbacks owning one prop from one
# Input is a race, and this one returned opened=False on its no-op branch,
# closing the modal the other had just opened. Opening is that callback's job.
# This one just fills the modal in.
@typed_callback(
    [
        # STORE_HISTORY_SUGGESTIONS, not STORE_SUGGESTIONS. The two panels used
        # to share one store, so opening this modal replaced the inline
        # accordion's contents with suggestions from other trials and other
        # agents, and the ones raised by the run just performed were gone short
        # of running it again.
        (Ids.STORE_HISTORY_SUGGESTIONS, "data"),
        (Ids.VAL_MSG, "children"),
    ],
    inputs=[
        (Ids.TC_HISTORY_SUGGESTIONS_BTN, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def show_history_suggestions(n_clicks, test_cases, selected_index):
  """Shows suggestions from historical trials."""
  if not n_clicks:
    return typed_callback.no_update, ""

  if (
      not test_cases
      or selected_index is None
      or selected_index >= len(test_cases)
  ):
    return (
        [],
        dmc.Alert("No test case selected.", color="red"),
    )

  tc_data = test_cases[selected_index]
  tc_id = tc_data.get("id")

  if not tc_id:
    return (
        [],
        dmc.Alert("Test case not saved yet.", color="orange"),
    )

  client = get_client()
  trials = client.trials.list_trials_with_suggestions(original_example_id=tc_id)

  if not trials:
    return (
        [],
        dmc.Alert(
            "No historical suggestions found for this test case.",
            color="blue",
            variant="light",
        ),
    )

  suggestions_data = []

  for t in trials:
    suggestions = t.suggested_asserts or []
    agent_name = t.agent_name or "Unknown"
    created_str = format_timestamp(t.created_at) if t.created_at else "Unknown"

    label = f"{created_str} - {agent_name} (Run {t.run_id} Trial {t.id})"

    for idx, s in enumerate(suggestions):
      # Trial.suggested_asserts is a list of Assertion models, never dicts. The
      # schema's validator flattens the ORM rows to dicts and pydantic parses
      # them straight back into the discriminated union. This used to test
      # isinstance(s, dict) and skip, which skipped every suggestion there has
      # ever been, so the modal has only ever said "No valid suggestions found."
      # mode="json", where the other writer of this store
      # (playground_client.run_simulation) uses a plain model_dump. The two
      # agree anyway: the only non-JSON values in an assertion are the enums,
      # and those are str subclasses, so they survive either way.
      s_dict = s.model_dump(mode="json")
      # ``id`` here is a suggested_assertions row id. Left in place, sync_suite
      # reads it as an id in the assertions table and updates whatever happens
      # to sit at that id instead of adding the suggestion.
      s_dict.pop("id", None)
      s_dict.pop("original_assertion_id", None)
      # The other writer keeps both keys. A playground suggestion has never
      # been saved, so its id is None either way.
      s_dict["_trial_id"] = t.id
      s_dict["_backend_index"] = idx
      s_dict["_group_label"] = label
      s_dict["_checked"] = False
      suggestions_data.append(s_dict)

  if not suggestions_data:
    return [], dmc.Text("No valid suggestions found.", c="dimmed")

  return suggestions_data, ""


@typed_callback(
    [
        (Ids.SUGGESTION_MODAL, CP.OPENED),
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_HISTORY_SUGGESTIONS, CP.DATA),
    ],
    inputs=[(Ids.SUGGESTION_ADD_BTN, CP.N_CLICKS)],
    state=[
        (Ids.SUGGESTION_LIST + "-group", CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def confirm_suggestions(
    n_clicks, selected_jsons, test_cases, selected_index, pathname
):
  """Adds selected suggestions to the test case."""
  logger.info(
      "confirm_suggestions called with %s clicks, %s selected",
      n_clicks,
      len(selected_jsons) if selected_jsons else 0,
  )
  if not n_clicks or not selected_jsons:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  new_asserts = [_clean_assertion_for_db(json.loads(s)) for s in selected_jsons]

  # No try/except. It swallowed the _sync_suite raise before @handle_errors
  # could reach it, so a failed write closed the modal with nothing saved and
  # no toast. See the note on _sync_suite.
  if (
      test_cases
      and selected_index is not None
      and selected_index < len(test_cases)
  ):
    tc = test_cases[selected_index]
    current_asserts = tc.get("asserts", [])
    updated_asserts = current_asserts + new_asserts
    tc["asserts"] = updated_asserts

    tc_id = tc.get("id")
    if tc_id:
      test_cases = _sync_suite(pathname, test_cases)

  # Emptied, so the added suggestions are gone from the modal list too.
  # Nothing used to clear the store, so reopening the modal offered the same
  # suggestions again, still ticked, and adding them a second time wrote the
  # same assertion onto the test case twice.
  return False, test_cases, []


@typed_callback(
    (Ids.STORE_BUILDER, CP.DATA),
    inputs=[
        dash.Input(
            {"type": Ids.ASSERT_TOGGLE_ACCURACY, "index": dash.ALL}, CP.CHECKED
        )
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,  # Because other methods update Store
)
def toggle_assertion_weight(
    checked_values, current_test_cases, selected_index, pathname
):
  """Toggles assertion weight when switch is clicked."""
  # checked_values holds every switch on the page, so the new value has to
  # come off the trigger.
  del checked_values
  ctx = dash.callback_context
  if not ctx.triggered:
    return typed_callback.no_update

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
  try:
    trigger_obj = json.loads(trigger_id)
    assert_index = trigger_obj["index"]
  except (json.JSONDecodeError, KeyError, ValueError, TypeError):
    return typed_callback.no_update

  if selected_index is None or not current_test_cases:
    return typed_callback.no_update

  is_checked = ctx.triggered[0]["value"]
  new_weight = 1 if is_checked else 0

  try:
    tc = current_test_cases[selected_index]
    if "asserts" in tc and len(tc["asserts"]) > assert_index:
      tc["asserts"][assert_index]["weight"] = new_weight

      tc_id = tc.get("id")
      if tc_id:
        current_test_cases = _sync_suite(pathname, current_test_cases)

      return current_test_cases
  except (IndexError, KeyError, TypeError):
    # Was a bare pass. The switch stays flipped and the weight is unchanged,
    # which is silent on screen either way, so the log is the only trace.
    logger.exception(
        "Could not set the weight of assertion %s on test case %s",
        assert_index,
        selected_index,
    )

  return typed_callback.no_update


@typed_callback(
    (Ids.MODAL_BULK_ADD, CP.OPENED),
    inputs=[
        (Ids.TC_BULK_ADD_BTN, CP.N_CLICKS),
        (Ids.BTN_BULK_ADD_CANCEL, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_bulk_add_modal(open_clicks, close_clicks):
  """Toggles the bulk add modal."""
  trigger_id = typed_callback.triggered_id()
  logger.debug(
      "toggle_bulk_add_modal triggered by %s. open=%s, close=%s",
      trigger_id,
      open_clicks,
      close_clicks,
  )

  if trigger_id == Ids.TC_BULK_ADD_BTN:
    return True
  if trigger_id == Ids.BTN_BULK_ADD_CANCEL:
    return False

  return dash.no_update


@typed_callback(
    [
        (Ids.BULK_ADD_INPUT_TITLE, CP.CHILDREN),
        (Ids.INPUT_BULK_TEXT, "placeholder"),
        (Ids.BULK_ADD_GUIDE_WRAPPER, CP.STYLE),
        (Ids.BTN_BULK_FIX_AI, CP.STYLE),
    ],
    inputs=[(Ids.TC_BULK_MODE, CP.VALUE)],
    prevent_initial_call=False,
)
def switch_bulk_add_mode(mode: str):
  """Updates the bulk add inputs for the Simple or Advanced mode."""
  if mode == "simple":
    return (
        "Question List (One per line)",
        (
            "Enter questions, one per line...\nExample:\nWhat is the capital of"
            " France?\nHow do I boil an egg?"
        ),
        {"display": "none"},
        {"display": "none"},
    )
  else:
    return (
        "Structured YAML Input",
        (
            "- question: Why is it raining?\n  assertions:\n    - type:"
            " text-contains\n      value: water"
        ),
        {"display": "block"},
        {"display": "inline-flex"},
    )


@typed_callback(
    [
        (Ids.VAL_MSG + "-bulk-count", CP.CHILDREN),
        (Ids.PREVIEW_BULK_ADD, CP.CHILDREN),
        (Ids.BTN_BULK_ADD_CONFIRM, CP.DISABLED),
    ],
    inputs=[
        (Ids.INPUT_BULK_TEXT, CP.VALUE),
        (Ids.TC_BULK_MODE, CP.VALUE),
    ],
    prevent_initial_call=True,
)
def update_bulk_preview(text_value: str | None, mode: str):
  """Updates the preview of test cases to be added."""
  if not text_value or not text_value.strip():
    return (
        "",
        dmc.Text(
            "No valid test cases found.",
            c="dimmed",
            size="sm",
            mt="md",
            ta="center",
        ),
        True,
    )

  try:
    if mode == "simple":
      lines = [line.strip() for line in text_value.split("\n") if line.strip()]
      test_cases = [
          TestCaseInput(question=line, assertions=[]) for line in lines
      ]
    else:
      client = get_client()
      test_cases = client.suites.parse_bulk_import_yaml(text_value)

    count_text = f"{len(test_cases)} test cases found"

    preview_items = []
    for tc in test_cases:
      badges = []
      if tc.assertions:
        badges.append(
            dmc.Badge(
                f"{len(tc.assertions)} assertions",
                variant="light",
                size="xs",
            )
        )

      preview_items.append(
          dmc.Paper(
              p="xs",
              withBorder=True,
              mb="xs",
              children=[
                  dmc.Text(tc.question, fw=500, size="sm"),
                  dmc.Group(gap="xs", children=badges),
              ],
          )
      )

    return count_text, dmc.Stack(preview_items, gap="xs"), False
  except Exception as e:  # pylint: disable=broad-exception-caught
    fields = _validation_fields(e)
    problem = _yaml_syntax_problem(e)
    if fields is not None:
      # Not str(e). See _validation_fields.
      title = "Input Error"
      message = "Invalid test case structure."
      if fields:
        message += f" Check these fields: {fields}"
    elif problem is not None:
      title = "Input Error"
      message = f"This is not valid YAML: {problem}."
    else:
      # Not an input error. Everything that reached here was reported as one,
      # so a call that never got to the parser read as bad YAML.
      logger.exception("Bulk import preview failed")
      title = "Preview Failed"
      message = (
          "Could not build a preview of this text. The details are in the"
          " server log."
      )

    return (
        dmc.Text("Parsing Error", c="red", size="sm"),
        dmc.Alert(
            message,
            title=title,
            color="red",
            variant="light",
            icon=DashIconify(icon="bi:exclamation-triangle"),
        ),
        True,
    )


@typed_callback(
    [
        (Ids.INPUT_BULK_TEXT, CP.VALUE),
        (NOTIFICATION_CONTAINER, "sendNotifications"),
    ],
    inputs=[(Ids.BTN_BULK_FIX_AI, CP.N_CLICKS)],
    state=[(Ids.INPUT_BULK_TEXT, CP.VALUE)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def fix_bulk_import_with_ai(n_clicks, text_value):
  """Uses AI to fix and reformat the bulk import text into structured YAML."""
  if not n_clicks or not text_value or not text_value.strip():
    return typed_callback.no_update, typed_callback.no_update

  client = get_client()
  try:
    fixed_yaml = client.suites.format_bulk_import_with_ai(text_value)
    return fixed_yaml, typed_callback.no_update
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("AI Fix failed: %s", e)
    # The textarea is left as the user typed it, so nothing on screen moves.
    # Without the toast the button reads as dead.
    return typed_callback.no_update, [{
        "action": "show",
        "title": "AI Fix Failed",
        "message": (
            "Could not reformat this text. The details are in the server log."
        ),
        "color": "red",
    }]


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.MODAL_BULK_ADD, CP.OPENED),
        (Ids.INPUT_BULK_TEXT, CP.VALUE),
        (NOTIFICATION_CONTAINER, "sendNotifications"),
    ],
    inputs=[(Ids.BTN_BULK_ADD_CONFIRM, CP.N_CLICKS)],
    state=[
        (Ids.INPUT_BULK_TEXT, CP.VALUE),
        (Ids.TC_BULK_MODE, CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def confirm_bulk_add(n_clicks, text_value, mode, current_test_cases, pathname):
  """Adds the bulk test cases to the list (Strict YAML version)."""
  nothing = (
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
  )

  if not n_clicks or not text_value:
    return nothing

  client = get_client()
  try:
    if mode == "simple":
      lines = [line.strip() for line in text_value.split("\n") if line.strip()]
      test_cases = [
          TestCaseInput(question=line, assertions=[]) for line in lines
      ]
    else:
      test_cases = client.suites.parse_bulk_import_yaml(text_value)
  except Exception:  # pylint: disable=broad-exception-caught
    # update_bulk_preview parses the same text and disables the confirm
    # button when it cannot, so the error is already on screen next to the
    # input. This branch is the race where it has not run yet.
    logger.exception("Bulk import parse failed on confirm")
    return nothing

  if not test_cases:
    return nothing

  current_test_cases = current_test_cases or []

  suite_id = None
  if pathname and "/test_suites/edit/" in pathname:
    try:
      # Split on the segment, like the other four parsers here. Taking
      # everything after "/test_suites/edit/" kept the trailing slash, so
      # bulk add on /test_suites/edit/3/ found no suite and refused.
      parts = pathname.split("/")
      suite_id = int(parts[parts.index("edit") + 1])
    except (ValueError, IndexError):
      pass

  if not suite_id:
    # Everything the user typed is still in the modal, and closing it loses
    # the lot. Say why nothing happened.
    logger.error("Bulk add has no suite to add to, pathname is %s", pathname)
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        [{
            "action": "show",
            "title": "Nothing Added",
            "message": (
                "Could not tell which test suite to add these to. Open the"
                " suite from the Test Suites page and try again."
            ),
            "color": "red",
        }],
    )

  new_tc_dicts = []
  for tc in test_cases:
    example = client.suites.add_example(
        suite_id=suite_id,
        question=tc.question,
        asserts=tc.assertions,
    )
    new_tc_dicts.append({
        "id": example.id,
        "question": example.question,
        "asserts": [a.model_dump() for a in example.asserts or []],
    })

  updated_test_cases = current_test_cases + new_tc_dicts
  return updated_test_cases, False, "", typed_callback.no_update


@typed_callback(
    (Ids.SUGGESTION_LIST, CP.CHILDREN),
    inputs=[(Ids.STORE_HISTORY_SUGGESTIONS, CP.DATA)],
    prevent_initial_call=True,
)
def render_suggestion_list(suggestions):
  """Renders the list of suggestions."""
  if not suggestions:
    # show_history_suggestions is what emptied the store, and it writes why to
    # Ids.VAL_MSG directly above this list. A generic line here would sit under
    # the specific one and bury it.
    return []

  items = []
  for s in suggestions:
    # The store holds plain dicts, not Assertion models. See
    # show_history_suggestions.
    s_type = s.get("type", "Unknown")
    s_val = s.get("value", "")
    if "params" in s:
      s_val = str(s["params"])
    elif "columns" in s:
      s_val = str(s["columns"])

    label = s_type.replace("-", " ").title()
    if s_val:
      label += f": {s_val}"
    if len(label) > 60:
      label = label[:60] + "..."

    # confirm_suggestions expects JSON strings.
    s_json = json.dumps(s)

    items.append(
        dmc.Checkbox(
            label=label,
            value=s_json,
            mb="xs",
        )
    )

  return dmc.CheckboxGroup(
      id=Ids.SUGGESTION_LIST + "-group",
      children=dmc.Stack(items, gap=0),
      value=[json.dumps(s) for s in suggestions if s.get("_checked")],
  )


@typed_callback(
    [
        (Ids.SUG_LIST, CP.CHILDREN),
        (Ids.SUG_ACCORDION, "style"),
        (Ids.SUG_ACCORDION_HEADER, CP.CHILDREN),
    ],
    inputs=[(Ids.STORE_SUGGESTIONS, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def render_inline_suggestion_list(suggestions):
  """Renders the inline suggested assertions and shows the accordion."""
  if not suggestions:
    return [], {"display": "none"}, typed_callback.no_update

  cards = [
      assertion_components.render_suggested_assertion_card(s, i)
      for i, s in enumerate(suggestions)
  ]

  # No count in the header, to match the trial page.
  header_children = [
      DashIconify(
          icon="bi:lightbulb",
          width=20,
          color="var(--mantine-color-grape-6)",
      ),
      dmc.Text("Suggested Assertions", size="lg", fw=700),
  ]

  return cards, {"display": "block"}, header_children
