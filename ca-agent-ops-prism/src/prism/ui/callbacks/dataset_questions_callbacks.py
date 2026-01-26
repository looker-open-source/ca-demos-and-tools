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

"""Callbacks for the Question Playground."""

import json
import logging
import time
import traceback
from typing import Any
import urllib.parse

import dash
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.ui import constants
from prism.ui.components import assertion_components
from prism.ui.components import dataset_components
from prism.ui.constants import CP
from prism.ui.models import ui_state
from prism.ui.pages.dataset_ids import DatasetIds as Ids
from prism.ui.utils import typed_callback
import yaml


def _clean_assertion_for_db(a: dict[str, Any]) -> dict[str, Any]:
  """Removes UI-only metadata fields (starting with _) from assertion dict."""
  return {k: v for k, v in a.items() if not k.startswith("_")}


def render_suggestion_card(
    s_dict: dict[str, Any],
    value_json: str,
    index: int,
    trial_id: int | None = None,
    checked: bool = True,
):
  """Renders a single suggestion card with checkbox and edit button."""
  label_text = s_dict.get("type", "Unknown")
  for guide in constants.ASSERTS_GUIDE:
    if guide["name"] == s_dict.get("type"):
      label_text = guide["label"]
      break

  val_str = str(s_dict.get("value", ""))
  if s_dict.get("type") == "data-check-row":
    val_str = str(s_dict.get("columns", ""))
  elif s_dict.get("type") == "looker-query-match":
    val_str = str(s_dict.get("params", ""))

  weight = s_dict.get("weight", 0)
  is_accuracy = weight > 0
  badge = dmc.Badge(
      "Accuracy" if is_accuracy else "Diagnostic",
      color="green" if is_accuracy else "gray",
      variant="light",
      size="xs",
      ml="xs",
  )

  return dmc.Group(
      [
          dmc.Checkbox(
              value=value_json,
              mb=0,
              checked=checked,
              mt=2,
          ),
          dmc.Stack(
              [
                  dmc.Group(
                      [
                          dmc.Text(label_text, fw=500, size="sm"),
                          badge,
                      ],
                      gap=0,
                  ),
                  dmc.Text(
                      val_str,
                      size="xs",
                      c="dimmed",
                      lineClamp=3,
                      style={"wordBreak": "break-word"},
                  ),
              ],
              gap=0,
              style={"flex": 1, "minWidth": 0},
          ),
          dmc.ActionIcon(
              DashIconify(icon="bi:pencil", width=16),
              id={
                  "type": Ids.SUGGESTION_EDIT_BTN,
                  "index": index,
                  "trial_id": trial_id if trial_id is not None else -1,
              },
              variant="subtle",
              size="sm",
              color="gray",
          ),
      ],
      align="flex-start",
      mb="xs",
      wrap="nowrap",
  )


# 1. Initialization & Loading
@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.Q_AGENT_SELECT, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.Q_BREADCRUMB_SUITE_NAME, CP.CHILDREN),
        (Ids.Q_BREADCRUMB_SUITE_NAME, CP.HREF),
    ],
    inputs=[
        (Ids.Q_AGENT_SELECT, "id"),  # Trigger on component mount
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
    # pathname format: /test_suites/edit/<id>
    parts = pathname.split("/")
    if "edit" not in parts:
      return (
          typed_callback.no_update,
          typed_callback.no_update,
          typed_callback.no_update,
          typed_callback.no_update,
          typed_callback.no_update,
      )
    dataset_id_idx = parts.index("edit") + 1
    dataset_id = int(parts[dataset_id_idx])
  except (ValueError, IndexError):
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  client = get_client()

  # Handle action=add from URL
  newly_added_id = None
  if search:
    parsed_search = urllib.parse.parse_qs(search.lstrip("?"))
    if parsed_search.get("action") == ["add"]:
      # Add to DB
      new_example = client.suites.add_example(
          suite_id=dataset_id, question="New Test Case"
      )
      newly_added_id = new_example.id

  suite = client.suites.get_suite(dataset_id)
  examples = client.suites.list_examples(dataset_id)
  questions = [
      {
          "id": e.id,
          "question": e.question,
          "asserts": [
              (a.model_dump() if hasattr(a, "model_dump") else a)
              for a in e.asserts or []
          ],
      }
      for e in examples
  ]

  # Load Agents for Runner
  all_agents = client.agents.list_agents()

  agent_options = [{"label": a.name, "value": str(a.id)} for a in all_agents]

  selected_index = 0 if questions else None

  # Check for deep link via ?test_case_id=...
  if search:
    parsed = urllib.parse.parse_qs(search.lstrip("?"))
    q_id_str = parsed.get("test_case_id", [None])[0]

    # Use newly added ID if we just created one
    target_id = newly_added_id
    if not target_id and q_id_str:
      try:
        target_id = int(q_id_str)
      except ValueError:
        pass

    if target_id:
      for i, q in enumerate(questions):
        if q["id"] == target_id:
          selected_index = i
          break

  suite_name = suite.name if suite else f"Suite {dataset_id}"
  suite_href = f"/test_suites/view/{dataset_id}"

  return questions, agent_options, selected_index, suite_name, suite_href


# 2. Render List
@typed_callback(
    (Ids.Q_LIST, CP.CHILDREN),
    inputs=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
)
def render_question_list(
    questions: list[dict[str, Any]], selected_index: int | None
):
  """Renders the sidebar list of test cases."""
  if questions is None:
    return typed_callback.no_update

  items = []
  try:
    for i, q in enumerate(questions):
      dq = ui_state.SuiteQuestion(**q)
      active = i == selected_index
      items.append(
          dataset_components.render_question_nav_item(dq, i, active=active)
      )
  except Exception as e:
    traceback.print_exc()
    return [dmc.Alert(f"Render Error: {e}", color="red", variant="light")]
  return items


# 2b. Render Assertion List (New)
@typed_callback(
    [(Ids.Q_RUN_BTN, CP.DISABLED)],
    inputs=[(Ids.Q_AGENT_SELECT, CP.VALUE)],
    prevent_initial_call=False,
)
def toggle_run_button(agent_id):
  """Disables run button if no agent selected."""
  return [not bool(agent_id)]


@typed_callback(
    (Ids.Q_ASSERT_LIST, CP.CHILDREN),
    inputs=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
    ],
    prevent_initial_call=True,
)
def render_assertion_list(questions, selected_index, result_data):
  """Renders the list of assertions for the selected test case."""
  if questions is None or selected_index is None:
    return []

  if selected_index >= len(questions):
    return []

  q = questions[selected_index]
  asserts = q.get("asserts", [])

  # Map results if available
  results_map = {}
  if result_data:
    # Assume positional mapping for playground
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
def update_url_on_question_select(selected_index, questions, current_search):
  """Updates URL search parameters when a test case is selected."""
  if (
      selected_index is None
      or not questions
      or selected_index >= len(questions)
  ):
    return typed_callback.no_update

  q_id = questions[selected_index].get("id")
  if not q_id:
    return typed_callback.no_update

  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )
  if params.get("test_case_id") == [str(q_id)]:
    return typed_callback.no_update

  params["test_case_id"] = [str(q_id)]
  return f"?{urllib.parse.urlencode(params, doseq=True)}"


@typed_callback(
    (Ids.STORE_SELECTED_INDEX, CP.DATA),
    inputs=[("url", CP.SEARCH)],
    state=[(Ids.STORE_BUILDER, CP.DATA), (Ids.STORE_SELECTED_INDEX, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def sync_selection_from_url(search, questions, current_index):
  """Syncs selected test case from URL when navigating."""
  if not search or not questions:
    return typed_callback.no_update

  params = urllib.parse.parse_qs(search.lstrip("?"))
  q_id_str = params.get("test_case_id", [None])[0]
  if not q_id_str:
    return typed_callback.no_update

  try:
    q_id = int(q_id_str)
    for i, q in enumerate(questions):
      if q.get("id") == q_id:
        if i == current_index:
          return typed_callback.no_update
        return i
  except ValueError:
    pass

  return typed_callback.no_update


# 3. Handle Selection & Add
@typed_callback(
    (Ids.STORE_SELECTED_INDEX, CP.DATA),
    inputs=[
        dash.Input({"type": Ids.Q_LIST_ITEM, "index": dash.ALL}, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def handle_question_selection(list_clicks):
  """Updates selected index based on list click."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return typed_callback.no_update

  # Check if ANY button was actually clicked (n_clicks > 0)
  # The Input is list of n_clicks.
  # Filter out Nones
  valid_clicks = [c for c in list_clicks if c]
  if not valid_clicks:
    return typed_callback.no_update

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

  # List Item Click
  # Trigger ID is a JSON string: {"index":0,"type":"..."}
  try:
    trigger_obj = json.loads(trigger_id)
    return trigger_obj["index"]
  except Exception:  # pylint: disable=broad-exception-caught
    return typed_callback.no_update


# 3b. Add Question Action
@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    inputs=[
        (Ids.Q_ADD_BTN, CP.N_CLICKS),
        ({"type": Ids.Q_ADD_BTN, "index": dash.ALL}, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def add_new_question(n_clicks, empty_add_clicks, current_questions, pathname):
  """Adds a new empty test case and selects it (Persisted to DB)."""
  # Combine clicks logic - if any triggered
  if not n_clicks and not any(empty_add_clicks or []):
    return typed_callback.no_update, typed_callback.no_update

  # Parse Suite ID
  try:
    if not pathname or "/test_suites/edit/" not in pathname:
      return typed_callback.no_update, typed_callback.no_update
    parts = pathname.split("/")
    dataset_id = int(parts[parts.index("edit") + 1])
  except (ValueError, IndexError):
    return typed_callback.no_update, typed_callback.no_update

  client = get_client()
  # Add to DB
  example = client.suites.add_example(
      suite_id=dataset_id, question="New Test Case"
  )

  # Update Local State
  new_q = {
      "id": example.id,
      "question": example.question,
      "asserts": [],  # Empty initially
  }
  updated = (current_questions or []) + [new_q]
  new_index = len(updated) - 1

  return updated, new_index


# 4. Populate Editor
# 4. Sync Editor Fields (Selection Change Only)
@typed_callback(
    [
        (Ids.Q_INPUT_QUESTION, CP.VALUE),
        (Ids.Q_ASSERT_TYPE, CP.VALUE),
        (Ids.Q_ASSERT_VALUE, CP.VALUE),
        (Ids.Q_ASSERT_YAML, CP.VALUE),
        (Ids.Q_EDITOR_CONTAINER, "style"),
        (Ids.Q_EDITOR_EMPTY, "style"),
        (Ids.Q_ASSERT_COUNT, CP.CHILDREN),
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
def sync_editor_selection(selected_index, questions):
  """Populates editor inputs when selection changes or builder updates."""
  if (
      selected_index is None
      or not questions
      or selected_index >= len(questions)
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

  q_data = questions[selected_index]
  q = ui_state.SuiteQuestion(**q_data)

  # Note: Assertion List is now handled by `render_assertion_list`
  # We just reset the "Add Assertion" inputs and populate Question Text

  return (
      q.question,
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
      str(len(q.asserts)),
  )


# 5. Handle Assertion UI Updates (Type Change)
@typed_callback(
    [
        (Ids.Q_ASSERT_VALUE, CP.STYLE),
        (Ids.Q_ASSERT_YAML, CP.STYLE),
        (Ids.ASSERT_GUIDE_CONTAINER, CP.STYLE),
        (Ids.ASSERT_GUIDE_TITLE, CP.CHILDREN),
        (Ids.ASSERT_GUIDE_DESC, CP.CHILDREN),
        (Ids.ASSERT_EXAMPLE_VALUE, CP.VALUE),
        (Ids.ASSERT_EXAMPLE_YAML, CP.VALUE),
        (Ids.ASSERT_EXAMPLE_VALUE, CP.STYLE),
        (Ids.ASSERT_EXAMPLE_YAML, CP.STYLE),
        (Ids.ASSERT_EXAMPLE_CONTAINER, CP.STYLE),
        (Ids.ASSERT_VAL_MSG, CP.STYLE),
    ],
    inputs=[(Ids.Q_ASSERT_TYPE, CP.VALUE)],
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
  is_yaml = assert_type in [
      "custom",
      "json_valid",
      "looker-query-match",
      "data-check-row",
  ]
  container_style = {"display": "block"} if example else {"display": "none"}

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
    )
  return (
      {"display": "block"},
      {"display": "none"},
      style_to_use,
      title,
      desc,
      example,
      "",
      {"display": "block"},
      {"display": "none"},
      container_style,
      {"display": "none"},
  )


@typed_callback(
    [
        (Ids.SUG_EDIT_VALUE, CP.STYLE),
        (Ids.SUG_EDIT_YAML, CP.STYLE),
        # (Ids.SUG_EDIT_DESC, CP.CHILDREN),
        (Ids.SUG_EDIT_GUIDE_CONTAINER, CP.STYLE),
        (Ids.SUG_EDIT_GUIDE_TITLE, CP.CHILDREN),
        (Ids.SUG_EDIT_GUIDE_DESC, CP.CHILDREN),
        (Ids.SUG_EDIT_EXAMPLE_VALUE, CP.VALUE),
        (Ids.SUG_EDIT_EXAMPLE_YAML, CP.VALUE),
        (Ids.SUG_EDIT_EXAMPLE_VALUE, CP.STYLE),
        (Ids.SUG_EDIT_EXAMPLE_YAML, CP.STYLE),
        (Ids.SUG_EDIT_EXAMPLE_CONTAINER, CP.STYLE),
        (Ids.ASSERT_VAL_MSG, CP.STYLE),
    ],
    inputs=[(Ids.SUG_EDIT_TYPE, CP.VALUE)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def update_suggestion_edit_ui(assert_type: str | None):
  """Updates visibility and description for Suggestion Edit Modal."""
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
  is_yaml = assert_type in [
      "custom",
      "json_valid",
      "looker-query-match",
      "data-check-row",
  ]
  container_style = {"display": "block"} if example else {"display": "none"}

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
    )
  return (
      {"display": "block"},
      {"display": "none"},
      style_to_use,
      title,
      desc,
      example,
      "",
      {"display": "block"},
      {"display": "none"},
      container_style,
      {"display": "none"},
  )


# 5b. Update Assertion Weight UI
@typed_callback(
    [(Ids.Q_ASSERT_WEIGHT, CP.LABEL), (Ids.Q_ASSERT_WEIGHT, CP.COLOR)],
    inputs=[(Ids.Q_ASSERT_WEIGHT, CP.CHECKED)],
    prevent_initial_call=True,
)
def update_assertion_weight_ui(checked: bool):
  """Updates label and color based on checked state."""
  if checked:
    return "Accuracy", "green"
  return "Diagnostic", "gray"


@typed_callback(
    [(Ids.SUG_EDIT_WEIGHT, CP.LABEL), (Ids.SUG_EDIT_WEIGHT, CP.COLOR)],
    inputs=[(Ids.SUG_EDIT_WEIGHT, CP.CHECKED)],
    prevent_initial_call=True,
)
def update_suggestion_edit_weight_ui(checked: bool):
  """Updates label and color based on checked state (Suggestion Modal)."""
  if checked:
    return "Accuracy", "green"
  return "Diagnostic", "gray"


# 6. Open Assertion Modal
@typed_callback(
    [
        (Ids.ASSERT_MODAL, CP.OPENED),
        (Ids.Q_ASSERT_TYPE, CP.VALUE),
        (Ids.Q_ASSERT_VALUE, CP.VALUE),
        (Ids.Q_ASSERT_YAML, CP.VALUE),
        (Ids.Q_ASSERT_WEIGHT, CP.CHECKED),
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
def open_assertion_modal(
    _add_clicks, _edit_clicks, questions, selected_q_index
):
  """Opens the assertion modal for adding or editing."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return typed_callback.no_update

  trigger_val = ctx.triggered[0]["value"]
  if not trigger_val:
    return typed_callback.no_update

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

  # Defaults for Adding
  a_type = None
  a_val = ""
  a_yaml = ""
  a_weight = True
  edit_idx = None
  title = "Add Assertion"
  display_delete = {"display": "none"}

  # Check if Edit was clicked
  if Ids.ASSERT_EDIT_BTN in trigger_id:
    try:
      trigger_obj = json.loads(trigger_id)
      edit_idx = trigger_obj["index"]
      if questions and selected_q_index is not None:
        q = questions[selected_q_index]
        if "asserts" in q and len(q["asserts"]) > edit_idx:
          a = q["asserts"][edit_idx]
          # 'a' could be AssertItem or dict
          a_dict = a.model_dump() if hasattr(a, "model_dump") else a
          a_type = a_dict.get("type")
          a_weight = a_dict.get("weight", 1) > 0

          # Populate Value/YAML based on type
          if a_type in ["data-check-row", "looker-query-match"]:
            val = (
                a_dict.get("columns")
                if a_type == "data-check-row"
                else a_dict.get("params")
            )
            a_yaml = yaml.dump(val, default_flow_style=False) if val else ""
          else:
            a_val = str(a_dict.get("value", ""))

          title = "Edit Assertion"
          display_delete = {"display": "block"}
    except Exception:  # pylint: disable=broad-exception-caught
      traceback.print_exc()
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
      a_weight,
      edit_idx,
      title,
      display_delete,
      "",
      {"display": "none"},
  )


# 7. Save Assertion (Add or Update)
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
        (Ids.Q_ASSERT_TYPE, CP.VALUE),
        (Ids.Q_ASSERT_VALUE, CP.VALUE),
        (Ids.Q_ASSERT_YAML, CP.VALUE),
        (Ids.Q_ASSERT_WEIGHT, CP.CHECKED),
        (Ids.STORE_ASSERT_EDIT_INDEX, CP.DATA),
        ("url", CP.PATHNAME),  # Added pathname to state
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def save_assertion_from_modal(
    n_clicks,
    questions,
    selected_index,
    assert_type,
    assert_value,
    assert_yaml_str,
    assert_weight_checked,
    edit_index,
    pathname,  # Added pathname to signature
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

  # 1. Parse Value based on type
  client = get_client()
  if assert_type in [
      "data-check-row",
      "looker-query-match",
      "custom",
      "json_valid",
  ]:
    val, yaml_error = client.suites.parse_yaml_safely(assert_yaml_str)
    if yaml_error:
      return (
          typed_callback.no_update,
          True,
          yaml_error,
          {"display": "block"},
      )
  else:
    val = assert_value

  # 2. Construct assertion dict for validation
  weight = 1.0 if assert_weight_checked else 0.0
  assertion_data = {"type": assert_type, "weight": weight}

  if assert_type == "data-check-row":
    assertion_data["columns"] = val
  elif assert_type == "looker-query-match":
    assertion_data["params"] = val
  else:
    # Numeric conversion logic for validation
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
    assertion_data["value"] = val

  # 3. Validate with Pydantic via service
  validation_error = client.suites.validate_assertion(assertion_data)
  if validation_error:
    return (
        typed_callback.no_update,
        True,
        validation_error,
        {"display": "block"},
    )

  # 4. Add to Question
  questions = questions or []
  if selected_index is not None and len(questions) > selected_index:
    q = questions[selected_index]
    if "asserts" not in q:
      q["asserts"] = []

    if edit_index is not None and 0 <= edit_index < len(q["asserts"]):
      q["asserts"][edit_index] = assertion_data
    else:
      q["asserts"].append(assertion_data)

    # Persist to DB
    q_id = q.get("id")
    if q_id:
      try:
        # Get dataset_id from URL: /test_suites/edit/<dataset_id>
        dataset_id = None
        if pathname and "/test_suites/edit/" in pathname:
          parts = pathname.split("/")
          try:
            dataset_id = int(parts[parts.index("edit") + 1])
          except (ValueError, IndexError):
            pass

        if dataset_id:
          client = get_client()
          # Sync the entire suite and update with returned IDs
          questions = client.suites.sync_suite(dataset_id, questions)
        else:
          print(
              "Warning: Could not determine dataset_id from pathname:"
              f" {pathname}"
          )
      except Exception:
        traceback.print_exc()

  return questions, False, "", {"display": "none"}


# 7b. Toggle Assertion Weight (Auto-save)
# Duplicate removed


# 7. Delete Assertion
# Removed delete_assertion as it is now handled by confirm_delete_question
# def delete_assertion... (removed)


# 8. Update Question Text
@typed_callback(
    [
        (Ids.Q_CHANGE_ACTIONS_GROUP, CP.STYLE),
        (Ids.VAL_MSG + "-char-count", CP.CHILDREN),
        (
            Ids.Q_ASSERT_COUNT,
            CP.CHILDREN,
        ),  # Also update count here as it depends on builder
    ],
    inputs=[
        (Ids.Q_INPUT_QUESTION, CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
    ],
    state=[
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    prevent_initial_call=False,
)
def detect_question_changes(value, questions, selected_index):
  """Toggles Save/Revert buttons and updates char count."""
  if (
      selected_index is None
      or not questions
      or selected_index >= len(questions)
  ):
    return {"display": "none"}, "0 chars", "0"

  q_data = questions[selected_index]
  original = q_data.get("question", "")
  has_changed = value != original

  char_count = f"{len(value or '')} chars"
  style = {"display": "flex"} if has_changed else {"display": "none"}

  # Assert count from builder
  assert_count = str(len(q_data.get("asserts", [])))

  return style, char_count, assert_count


@typed_callback(
    (Ids.STORE_BUILDER, CP.DATA),
    inputs=[(Ids.Q_SAVE_BTN, CP.N_CLICKS)],
    state=[
        (Ids.Q_INPUT_QUESTION, CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def save_question_text(
    n_clicks, question, current_questions, selected_index, pathname
):
  """Persists the question text to DB and local store on Save click."""
  if not n_clicks or selected_index is None or not current_questions:
    return typed_callback.no_update

  if selected_index >= len(current_questions):
    return typed_callback.no_update

  # Update Local
  current_questions[selected_index]["question"] = question

  # Update DB
  try:
    if pathname and "/test_suites/edit/" in pathname:
      parts = pathname.split("/")
      dataset_id = int(parts[parts.index("edit") + 1])
      client = get_client()
      current_questions = client.suites.sync_suite(
          dataset_id, current_questions
      )
  except Exception:
    traceback.print_exc()

  return current_questions


@typed_callback(
    (Ids.Q_INPUT_QUESTION, CP.VALUE),
    inputs=[(Ids.Q_REVERT_BTN, CP.N_CLICKS)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def revert_question_text(n_clicks, questions, selected_index):
  """Reverts the editor text to the last saved value."""
  if not n_clicks or selected_index is None or not questions:
    return typed_callback.no_update

  if selected_index >= len(questions):
    return typed_callback.no_update

  return questions[selected_index].get("question", "")


# 6. Delete Question (Modal & Action)
@typed_callback(
    [
        (Ids.MODAL_DELETE, CP.OPENED),
        (Ids.STORE_SELECTED_INDEX, CP.DATA),
        (Ids.STORE_DELETE_QUESTION_INDEX, CP.DATA),
        (Ids.STORE_DELETE_ASSERTION_INDEX, CP.DATA),
        (Ids.MODAL_DELETE_BODY, CP.CHILDREN),
    ],
    inputs=[
        ({"type": Ids.Q_REMOVE_QUESTION_BTN, "index": dash.ALL}, CP.N_CLICKS),
        ({"type": Ids.Q_REMOVE_ASSERTION_BTN, "index": dash.ALL}, CP.N_CLICKS),
    ],
    state=[
        ("selected-question-index", CP.DATA),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def open_delete_modal(_delete_q_clicks, _delete_a_clicks, selected_index):
  """Opens the delete confirmation modal."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  trigger = ctx.triggered[0]
  trigger_id = trigger["prop_id"].split(".")[0]
  trigger_value = trigger["value"]

  # Ignore valid triggers with no actual clicks (e.g. initialization to 0 or None)
  if not trigger_value:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  # Check if it was a QUESTION delete button click
  if "index" in trigger_id and Ids.Q_REMOVE_QUESTION_BTN in trigger_id:
    try:
      trigger_obj = json.loads(trigger_id)
      idx = trigger_obj["index"]
      if idx == "current":
        idx = selected_index
      # Set QUESTION index, Clear ASSERTION index
      return (
          True,
          idx,
          idx,
          None,
          "Are you sure you want to delete this question?",
      )
    except (json.JSONDecodeError, KeyError, IndexError, ValueError):
      pass

  # Check if it was an ASSAERTION delete button click
  if "index" in trigger_id and Ids.Q_REMOVE_ASSERTION_BTN in trigger_id:
    try:
      trigger_obj = json.loads(trigger_id)
      idx = trigger_obj["index"]
      # Set ASSERTION index, Clear QUESTION index
      return (
          True,
          typed_callback.no_update,
          None,
          idx,
          "Are you sure you want to delete this assertion?",
      )
    except (json.JSONDecodeError, KeyError, IndexError, ValueError):
      pass

  return (
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
        ("selected-question-index", CP.DATA),
        (Ids.STORE_DELETE_QUESTION_INDEX, CP.DATA),
        (Ids.STORE_DELETE_ASSERTION_INDEX, CP.DATA),
        (Ids.MODAL_DELETE_BODY, CP.CHILDREN),
    ],
    inputs=[(Ids.MODAL_CONFIRM_REMOVE_BTN, CP.N_CLICKS)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        ("selected-question-index", CP.DATA),
        (Ids.STORE_DELETE_QUESTION_INDEX, CP.DATA),
        (Ids.STORE_DELETE_ASSERTION_INDEX, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def confirm_delete_item(
    n_clicks,
    questions,
    selected_q_index,
    delete_q_index,
    delete_a_index,
    pathname,
):
  """Deletes a question or assertion based on which index is set."""
  if not n_clicks or not questions:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  # Get dataset_id from URL: /test_suites/edit/<dataset_id>
  dataset_id = None
  if pathname and "/test_suites/edit/" in pathname:
    parts = pathname.split("/")
    try:
      dataset_id = int(parts[parts.index("edit") + 1])
    except (ValueError, IndexError):
      pass

  if not dataset_id:
    print(f"Error: Could not determine dataset_id from pathname: {pathname}")
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        dmc.Alert(
            "Error: Could not determine suite ID for deletion.", color="red"
        ),
    )

  client = get_client()

  # Case 1: Delete Question
  if delete_q_index is not None:
    # 1. Delete from DB
    if delete_q_index < len(questions):
      q_id = questions[delete_q_index].get("id")
      if q_id:
        try:
          client.suites.delete_example(q_id)
        except Exception:
          traceback.print_exc()
      # 2. Delete from Local Store
      questions.pop(delete_q_index)
      # 3. Reset Selection if needed
      new_selected = None
      if questions:
        new_selected = max(0, min(delete_q_index, len(questions) - 1))

      return (
          questions,
          False,  # Close Modal
          new_selected,
          None,  # Clear Q-Index
          None,  # Clear A-Index
          typed_callback.no_update,
      )

  # Case 2: Delete Assertion
  if delete_a_index is not None and selected_q_index is not None:
    if selected_q_index < len(questions):
      q = questions[selected_q_index]
      if "asserts" in q and delete_a_index < len(q["asserts"]):
        q["asserts"].pop(delete_a_index)

        # DB Persist (sync the entire suite after assertion change)
        try:
          questions = client.suites.sync_suite(dataset_id, questions)
        except Exception:
          traceback.print_exc()

      return (
          questions,
          False,  # Close Modal
          typed_callback.no_update,
          None,  # Clear Q-Index
          None,  # Clear A-Index
          typed_callback.no_update,
      )

  return (
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
      typed_callback.no_update,
  )


def _render_simulation_skeleton():
  """Renders the skeleton loading state for simulation."""
  # Left Column: Assertion Results
  left_col = dmc.Stack(
      gap="sm",
      children=[
          dmc.Skeleton(height=15, width="40%", mb="xs"),  # Header
          dmc.Stack(
              gap="xs",
              children=[dmc.Skeleton(height=50, radius="md") for _ in range(3)],
          ),
      ],
  )

  # Right Column: Suggestions
  right_col = dmc.Stack(
      gap="sm",
      children=[
          dmc.Skeleton(height=15, width="50%", mb="xs"),  # Header
          dmc.Stack(
              gap="md",
              children=[
                  dmc.Skeleton(height=80, radius="md"),
                  dmc.Skeleton(height=80, radius="md"),
              ],
          ),
      ],
  )

  return dmc.Box(
      children=[
          dmc.Divider(my="lg", color="gray.2"),
          dmc.SimpleGrid(
              cols={"base": 1, "lg": 2},
              spacing="xl",
              children=[left_col, right_col],
          ),
      ]
  )


# 1. Start Simulation (Immediate Skeleton)
@typed_callback(
    [
        (Ids.STORE_START_RUN, CP.DATA),
        (Ids.SIM_CONTEXT_CONTAINER, CP.CHILDREN),
        (Ids.Q_RUN_BTN, "loading"),
        (Ids.SUG_LIST, CP.CHILDREN),
    ],
    inputs=[(Ids.Q_RUN_BTN, CP.N_CLICKS)],
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
    )

  ts = int(time.time() * 1000)

  # Skeleton for Context
  context_skeleton = dmc.Stack(
      gap="xs",
      mt="md",
      children=[
          dmc.Skeleton(height=20, width="60%"),
          dmc.Skeleton(height=20, width="40%"),
      ],
  )

  # Skeleton for Suggestions
  suggestions_skeleton = dmc.Stack(
      gap="md",
      children=[
          dmc.Skeleton(height=80, radius="md"),
          dmc.Skeleton(height=80, radius="md"),
      ],
  )

  return ({"ts": ts}, context_skeleton, True, suggestions_skeleton)


# 2. Execute Simulation (Heavy Computation)
@typed_callback(
    [
        (Ids.SIM_CONTEXT_CONTAINER, CP.CHILDREN),
        (Ids.STORE_PLAYGROUND_RESULT, CP.DATA),
        (Ids.STORE_SUGGESTIONS, CP.DATA),
        (Ids.Q_RUN_BTN, "loading"),
    ],
    inputs=[(Ids.STORE_START_RUN, CP.DATA)],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        ("selected-question-index", CP.DATA),
        (Ids.Q_AGENT_SELECT, CP.VALUE),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def execute_simulation(trigger_data, questions_store, selected_index, agent_id):
  """Executes the question against the selected agent, scores assertions, and generates suggestions."""
  if not trigger_data:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
        False,
    )

  # Extract example_id
  example_id = None
  if questions_store and selected_index is not None:
    if selected_index < len(questions_store):
      example_id = questions_store[selected_index].get("id")

  try:
    client = get_client()
    # Encapsulated Business Logic: single call using IDs
    sim_result = client.playground.run_simulation(
        agent_id=int(agent_id), example_id=example_id
    )

    result = sim_result.result_summary
    suggestions_data = sim_result.suggestions_ui
    logging.info("Simulation finished. Result: %s", result)
    logging.info(
        "Suggestions Generated: %s",
        len(suggestions_data) if suggestions_data else 0,
    )

    # --- Render Simulation Context Summary ---
    assertion_results = result.get("assertion_results", [])
    total_assertions = len(assertion_results)
    passed_assertions = sum(1 for r in assertion_results if r.get("passed"))

    # Calculate Accuracy: average score of non-diagnostic (weight > 0) assertions
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

    status_color = "emerald" if result["passed"] else "red"
    icon = (
        "material-symbols:check-circle"
        if result["passed"]
        else "material-symbols:cancel"
    )

    context_ui = dmc.Box(
        mt="md",
        p="sm",
        className=(
            f"bg-{status_color}.0 border border-{status_color}.1 rounded-md"
        ),
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
                                        className=f"text-{status_color}.6",
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

  except Exception:
    logging.exception("Simulation failed")
    return (
        dmc.Alert(
            "An error occurred during simulation execution. Please check the"
            " logs.",
            color="red",
            title="Simulation Error",
        ),
        typed_callback.no_update,
        typed_callback.no_update,
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
        ("selected-question-index", CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def handle_inline_suggestion(
    _accept_clicks,
    _reject_clicks,
    suggestions,
    questions,
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

  logging.info(
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
    logging.info("Action: %s, Index: %s", action_type, sug_idx)
  except (json.JSONDecodeError, KeyError, ValueError):
    logging.info("Failed to parse trigger_id_str: %s", trigger_id_str)
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

  # If Accepted, add to Question
  updated_questions = typed_callback.no_update
  if action_type == Ids.INLINE_SUG_ADD_BTN:
    if (
        questions
        and selected_index is not None
        and selected_index < len(questions)
    ):
      q = questions[selected_index]
      current_asserts = q.get("asserts", [])

      # Convert simple suggestion to assertion dict
      new_assert = _clean_assertion_for_db(suggestion)
      new_assert["weight"] = 1

      # Add to list
      updated_asserts = current_asserts + [new_assert]

      # Update question props
      q["asserts"] = updated_asserts
      updated_questions = list(questions)
      updated_questions[selected_index] = q

      # Persist to DB immediately
      q_id = q.get("id")
      if q_id:
        try:
          # Get dataset_id from URL: /test_suites/edit/<dataset_id>
          dataset_id = None
          if pathname and "/test_suites/edit/" in pathname:
            parts = pathname.split("/")
            try:
              dataset_id = int(parts[parts.index("edit") + 1])
            except (ValueError, IndexError):
              pass

          if dataset_id:
            client = get_client()
            # Sync the entire suite and update with returned IDs
            updated_questions = client.suites.sync_suite(
                dataset_id, updated_questions
            )
          else:
            print(
                "Warning: Could not determine dataset_id from pathname:"
                f" {pathname}"
            )
        except Exception:
          traceback.print_exc()

  # Remove from Suggestions Store
  new_suggestions = [s for i, s in enumerate(suggestions) if i != sug_idx]

  return updated_questions, new_suggestions


# 5a. Open Suggestion Modal (Immediate)
@typed_callback(
    (Ids.SUGGESTION_MODAL, CP.OPENED),
    inputs=[
        (Ids.Q_HISTORY_SUGGESTIONS_BTN, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
)
def open_suggestion_modal(history_clicks):
  """Opens the suggestion modal immediately on click."""
  if not history_clicks:
    return typed_callback.no_update
  return True


@typed_callback(
    [
        (Ids.STORE_SUGGESTIONS, "data"),
        (Ids.SUGGESTION_MODAL, "opened"),
        (Ids.VAL_MSG, "children"),
    ],
    inputs=[
        (Ids.Q_HISTORY_SUGGESTIONS_BTN, CP.N_CLICKS),
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        ("selected-question-index", CP.DATA),
        ("url", CP.PATHNAME),  # Added pathname to state
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def show_history_suggestions(n_clicks, questions, selected_index):
  """Shows suggestions from historical trials."""
  if not n_clicks:
    return typed_callback.no_update, False, ""

  if (
      not questions
      or selected_index is None
      or selected_index >= len(questions)
  ):
    return (
        [],
        True,
        dmc.Alert("No question selected.", color="red"),
    )

  q_data = questions[selected_index]
  q_id = q_data.get("id")

  if not q_id:
    return (
        [],
        True,
        dmc.Alert("Question not saved yet.", color="orange"),
    )

  client = get_client()
  trials = client.trials.list_trials_with_suggestions(original_example_id=q_id)

  if not trials:
    return (
        [],
        True,
        dmc.Alert(
            "No historical suggestions found for this question.",
            color="blue",
            variant="light",
        ),
    )

  suggestions_data = []

  for t in trials:
    suggestions = t.suggested_asserts or []
    agent_name = t.agent_name or "Unknown"
    created_str = (
        t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "Unknown"
    )

    label = f"{created_str} - {agent_name} (Run {t.run_id} Trial {t.id})"

    for idx, s in enumerate(suggestions):
      if not isinstance(s, dict):
        continue

      s_dict = s.copy()
      s_dict["_trial_id"] = t.id
      s_dict["_backend_index"] = idx
      s_dict["_group_label"] = label
      s_dict["_checked"] = False
      suggestions_data.append(s_dict)

  if not suggestions_data:
    return [], True, dmc.Text("No valid suggestions found.", c="dimmed")

  return suggestions_data, True, ""


# 5b. Suggestion Logic (Background) - REMOVED (Merged into Run)
# @typed_callback(...)
# def generate_suggestions(...):
#   pass


@typed_callback(
    [
        (Ids.SUGGESTION_MODAL, CP.OPENED),
        (Ids.STORE_BUILDER, CP.DATA),
    ],
    inputs=[(Ids.SUGGESTION_ADD_BTN, CP.N_CLICKS)],
    state=[
        (Ids.SUGGESTION_LIST + "-group", CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
        ("selected-question-index", CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def confirm_suggestions(
    n_clicks, selected_jsons, questions, selected_index, pathname
):
  """Adds selected suggestions to the question."""
  logging.info(
      "confirm_suggestions called with %s clicks, %s selected",
      n_clicks,
      len(selected_jsons) if selected_jsons else 0,
  )
  if not n_clicks or not selected_jsons:
    return typed_callback.no_update, typed_callback.no_update

  try:
    new_asserts = [
        _clean_assertion_for_db(json.loads(s)) for s in selected_jsons
    ]

    # Update Store
    if (
        questions
        and selected_index is not None
        and selected_index < len(questions)
    ):
      q = questions[selected_index]
      current_asserts = q.get("asserts", [])
      # Append new ones
      updated_asserts = current_asserts + new_asserts
      q["asserts"] = updated_asserts

      # Persist to DB
      q_id = q.get("id")
      if q_id:
        try:
          # Get dataset_id from URL: /test_suites/edit/<dataset_id>
          dataset_id = None
          if pathname and "/test_suites/edit/" in pathname:
            parts = pathname.split("/")
            try:
              dataset_id = int(parts[parts.index("edit") + 1])
            except (ValueError, IndexError):
              pass

          if dataset_id:
            client = get_client()
            # Sync the entire suite and update with returned IDs
            questions = client.suites.sync_suite(dataset_id, questions)
          else:
            print(
                "Warning: Could not determine dataset_id from pathname:"
                f" {pathname}"
            )
        except Exception:
          traceback.print_exc()

    return False, questions  # Close Modal and Update Store

  except Exception:
    traceback.print_exc()
    return typed_callback.no_update, typed_callback.no_update


# Update confirm_suggestions to output STORE_BUILDER


# 4c. Toggle Assertion Weight
@typed_callback(
    (Ids.STORE_BUILDER, CP.DATA),
    inputs=[
        dash.Input(
            {"type": Ids.ASSERT_TOGGLE_ACCURACY, "index": dash.ALL}, CP.CHECKED
        )
    ],
    state=[
        (Ids.STORE_BUILDER, CP.DATA),
        ("selected-question-index", CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,  # Because other methods update Store
)
def toggle_assertion_weight(
    checked_values, current_questions, selected_index, pathname
):
  """Toggles assertion weight when switch is clicked."""
  del checked_values  # Unused
  ctx = dash.callback_context
  if not ctx.triggered:
    return typed_callback.no_update

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
  try:
    trigger_obj = json.loads(trigger_id)
    assert_index = trigger_obj["index"]
  except (json.JSONDecodeError, KeyError, ValueError, TypeError):
    return typed_callback.no_update

  if selected_index is None or not current_questions:
    return typed_callback.no_update

  # Get the value
  # checked_values is a list of all switches. standard Dash ALL pattern.
  # But we only care about the TRIGGERED one.
  # However, ctx.triggered[0]["value"] gives the value of the trigger.

  is_checked = ctx.triggered[0]["value"]
  new_weight = 1 if is_checked else 0

  # Update Store
  # Logic: update current_questions -> selected_index -> asserts -> assert_index
  try:
    q = current_questions[selected_index]
    if "asserts" in q and len(q["asserts"]) > assert_index:
      q["asserts"][assert_index]["weight"] = new_weight

      # Persist to DB
      q_id = q.get("id")
      if q_id:
        try:
          # Get dataset_id from URL: /test_suites/edit/<dataset_id>
          dataset_id = None
          if pathname and "/test_suites/edit/" in pathname:
            parts = pathname.split("/")
            try:
              dataset_id = int(parts[parts.index("edit") + 1])
            except (ValueError, IndexError):
              pass

          if dataset_id:
            client = get_client()
            # Sync the entire suite and update with returned IDs
            current_questions = client.suites.sync_suite(
                dataset_id, current_questions
            )
          else:
            print(
                "Warning: Could not determine dataset_id from pathname:"
                f" {pathname}"
            )
        except Exception:
          traceback.print_exc()

      return current_questions
  except (IndexError, KeyError, TypeError):
    pass

  return typed_callback.no_update


@typed_callback(
    (Ids.MODAL_BULK_ADD, CP.OPENED),
    inputs=[
        (Ids.Q_BULK_ADD_BTN, CP.N_CLICKS),
        (Ids.BTN_BULK_ADD_CANCEL, CP.N_CLICKS),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_bulk_add_modal(open_clicks, close_clicks):
  """Toggles the bulk add modal."""
  trigger_id = typed_callback.triggered_id()
  logging.info(
      "DEBUG: toggle_bulk_add_modal triggered by %s. open=%s, close=%s",
      trigger_id,
      open_clicks,
      close_clicks,
  )

  if trigger_id == Ids.Q_BULK_ADD_BTN:
    return True
  if trigger_id == Ids.BTN_BULK_ADD_CANCEL:
    return False

  return dash.no_update


@typed_callback(
    [
        (Ids.VAL_MSG + "-bulk-count", CP.CHILDREN),
        (Ids.PREVIEW_BULK_ADD, CP.CHILDREN),
    ],
    inputs=[(Ids.INPUT_BULK_TEXT, CP.VALUE)],
    prevent_initial_call=True,
)
def update_bulk_preview(text_value):
  """Updates the preview of questions to be added."""
  if not text_value:
    return "", dmc.Text("No questions to preview", c="dimmed", size="sm")

  questions = [line.strip() for line in text_value.split("\n") if line.strip()]

  if not questions:
    return "", dmc.Text("No valid questions found", c="dimmed", size="sm")

  count_text = f"{len(questions)} questions found"
  list_items = dmc.List(
      [dmc.ListItem(q) for q in questions],
      size="sm",
      spacing="xs",
  )

  return count_text, list_items


@typed_callback(
    [
        (Ids.STORE_BUILDER, CP.DATA),
        (Ids.MODAL_BULK_ADD, CP.OPENED),
        (Ids.INPUT_BULK_TEXT, CP.VALUE),
    ],
    inputs=[(Ids.BTN_BULK_ADD_CONFIRM, CP.N_CLICKS)],
    state=[
        (Ids.INPUT_BULK_TEXT, CP.VALUE),
        (Ids.STORE_BUILDER, CP.DATA),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def confirm_bulk_add(n_clicks, text_value, current_questions, pathname):
  """Adds the bulk questions to the list."""
  if not n_clicks or not text_value:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  new_questions_text = [
      line.strip() for line in text_value.split("\n") if line.strip()
  ]

  if not new_questions_text:
    return (
        typed_callback.no_update,
        typed_callback.no_update,
        typed_callback.no_update,
    )

  current_questions = current_questions or []

  # 1. Add to DB
  # Get suite_id from URL: /test_suites/edit/<dataset_id>
  suite_id = None
  if pathname and "/test_suites/edit/" in pathname:
    try:
      suite_id = int(pathname.split("/test_suites/edit/")[-1].split("?")[0])
    except (ValueError, IndexError):
      pass

  if not suite_id and current_questions:
    # Fallback to existing questions if URL parsing fails (unlikely)
    suite_id = current_questions[0].get("suite_id")

  new_q_dicts = []

  if suite_id:
    client = get_client()
    for q_text in new_questions_text:
      # Create in DB
      example = client.suites.add_example(
          suite_id=int(suite_id), question=q_text
      )
      new_q_dicts.append(example.model_dump())
  else:
    # Fallback: Just append dicts (unsaved)
    # This matches `add_question` behavior where `id=None` until saved/refreshed?
    # WARNING: If suite_id is missing, `update_question_text` won't save it either.
    # But we assume `current_questions` is populated if we are in this view.
    for q_text in new_questions_text:
      new_q_dicts.append({
          "id": None,
          "question": q_text,
          "asserts": [],
      })

  updated_questions = current_questions + new_q_dicts

  return updated_questions, False, ""


# --- Suggestion Rendering ---


@typed_callback(
    (Ids.SUGGESTION_LIST, CP.CHILDREN),
    inputs=[(Ids.STORE_SUGGESTIONS, CP.DATA)],
    prevent_initial_call=True,
)
def render_suggestion_list(suggestions):
  """Renders the list of suggestions."""
  if not suggestions:
    return dmc.Text("No suggestions available.", c="dimmed", fs="italic")

  items = []
  for _, s in enumerate(suggestions):
    # s is dict
    s_type = s.get("type", "Unknown")
    s_val = s.get("value", "")
    if "params" in s:
      s_val = str(s["params"])
    elif "columns" in s:
      s_val = str(s["columns"])

    label = s_type.replace("-", " ").title()
    if s_val:
      label += f": {s_val}"
    # Truncate
    if len(label) > 60:
      label = label[:60] + "..."

    # Checkbox value is usually the JSON string or index.
    # confirm_suggestions expects JSON strings.
    s_json = json.dumps(s)

    # Item Layout: Checkbox only (Edit removed as per request)
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
  """Renders the list of suggested assertions (Inline) and toggles visibility."""
  if not suggestions:
    return [], {"display": "none"}, typed_callback.no_update

  cards = [
      assertion_components.render_suggested_assertion_card(s, i)
      for i, s in enumerate(suggestions)
  ]

  # Header without count (matching trial page)
  header_children = [
      DashIconify(
          icon="bi:lightbulb",
          width=20,
          color="var(--mantine-color-grape-6)",
      ),
      dmc.Text("Suggested Assertions", size="lg", fw=700),
  ]

  # Show the accordion
  return cards, {"display": "block"}, header_children
