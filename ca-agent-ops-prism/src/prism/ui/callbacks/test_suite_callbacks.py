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

"""Callbacks for the Test Suites UI."""

import traceback
from typing import Any
import urllib.parse

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas import agent as agent_schemas
from prism.ui import ids as test_suite_ids
from prism.ui.components import empty_states
from prism.ui.components import tables
from prism.ui.components import test_case_components
from prism.ui.components.agent_components import render_agent_card
from prism.ui.constants import CP
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
from prism.ui.ids import TestSuiteHomeIds
from prism.ui.models import ui_state
from prism.ui.utils import typed_callback


@typed_callback(
    (EvaluationIds.MODAL_RUN_EVAL, "opened"),
    inputs=[
        (EvaluationIds.BTN_OPEN_RUN_MODAL, CP.N_CLICKS),
        (EvaluationIds.BTN_CANCEL_RUN, CP.N_CLICKS),
        (EvaluationIds.BTN_CANCEL_RUN + "-x", CP.N_CLICKS),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_run_eval_modal(open_clicks, cancel_clicks, x_clicks):
  """Toggles the Run Evaluation modal."""
  del open_clicks, cancel_clicks, x_clicks
  ctx = dash.callback_context
  if not ctx.triggered:
    return typed_callback.no_update

  trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
  if trigger_id == EvaluationIds.BTN_OPEN_RUN_MODAL:
    return True
  return False


@typed_callback(
    (EvaluationIds.AGENT_SELECT, CP.DATA),
    inputs=[(EvaluationIds.MODAL_RUN_EVAL, "opened")],
    state=[("url", CP.PATHNAME)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def populate_eval_agents(is_open, _):
  """Populates agent options filtering by compatible datasource."""
  if not is_open:
    return typed_callback.no_update

  client = get_client()
  all_agents = client.agents.list_agents()

  return [{"label": agent.name, "value": str(agent.id)} for agent in all_agents]


@typed_callback(
    (EvaluationIds.AGENT_DETAILS, CP.CHILDREN),
    inputs=[(EvaluationIds.AGENT_SELECT, CP.VALUE)],
    prevent_initial_call=True,
)
def render_eval_agent_details(agent_id):
  """Renders the selected agent details."""
  if not agent_id:
    return dmc.Alert(
        "Select an agent to view details.",
        color="blue",
        variant="light",
    )

  client = get_client()
  agent = client.agents.get_agent(int(agent_id))

  if not agent:
    return dmc.Alert("Agent not found", color="red")

  warning = None
  if agent.config and isinstance(
      agent.config.datasource, agent_schemas.LookerConfig
  ):
    if (
        not agent.config.looker_client_id
        or not agent.config.looker_client_secret
    ):
      warning = dmc.Alert(
          "This Looker agent is missing credentials. You will not be able to"
          " start evaluations until they are provided.",
          title="Missing Credentials",
          color="red",
          radius="md",
          icon=DashIconify(icon="material-symbols:warning-rounded"),
          mb="md",
      )

  return html.Div([warning, render_agent_card(agent)])


@typed_callback(
    [
        (TestSuiteHomeIds.TEST_SUITES_LIST, CP.CHILDREN),
        (TestSuiteHomeIds.LOADING, CP.VISIBLE),
    ],
    inputs=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
)
def update_test_suites_list(pathname: str, search: str):
  """Renders the list of test suites on the dashboard."""

  if pathname != "/test_suites":
    return typed_callback.no_update, typed_callback.no_update

  # Parse Filters from URL
  parsed_qs = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
  coverage = parsed_qs.get("coverage", [None])[0]

  client = get_client()
  include_archived = parsed_qs.get("archived", ["false"])[0] == "true"
  suites_with_stats = client.suites.get_suites_with_stats(
      coverage=coverage,
      include_archived=include_archived,
  )

  if not suites_with_stats:
    return (
        empty_states.render_empty_state(
            title="No Test Suites Found",
            description=(
                "Create your first test suite to start defining evaluation"
                " criteria."
            ),
            button_label="Create Test Suite",
            href="/test_suites/new",
            icon="bi:collection",
        ),
        False,
    )

  table = tables.render_test_suite_table(suites_with_stats)

  return table, False


@typed_callback(
    dash.Output("url", "search", allow_duplicate=True),
    inputs=[
        (TestSuiteHomeIds.FILTER_COVERAGE, CP.VALUE),
    ],
    state=[("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_test_suite_url_from_filters(
    coverage: str | None, current_search: str
):
  """Update URL search params from Test Suites Home filters."""
  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )

  if coverage:
    params["coverage"] = [coverage]
  else:
    params.pop("coverage", None)

  return f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""


@typed_callback(
    dash.Output("url", "search", allow_duplicate=True),
    inputs=[
        (TestSuiteHomeIds.SWITCH_ARCHIVED, CP.CHECKED),
    ],
    state=[("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_test_suite_url_from_archived_switch(
    include_archived: bool, current_search: str
):
  """Update URL search params from Test Suites Home archived switch."""
  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )

  if include_archived:
    params["archived"] = ["true"]
  else:
    params.pop("archived", None)

  return f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""


@typed_callback(
    [
        (TestSuiteHomeIds.FILTER_COVERAGE, CP.VALUE),
        (TestSuiteHomeIds.SWITCH_ARCHIVED, CP.CHECKED),
    ],
    inputs=[("url", CP.SEARCH)],
)
def sync_test_suite_filters_to_url(search: str):
  """Sync Test Suites Home filters to URL search params."""
  if not search:
    return None, False

  params = urllib.parse.parse_qs(search.lstrip("?"))
  coverage = params.get("coverage", [None])[0]
  include_archived = params.get("archived", ["false"])[0] == "true"
  return coverage, include_archived


@typed_callback(
    (REDIRECT_HANDLER, CP.HREF),
    inputs=[
        (test_suite_ids.TestSuiteIds.BTN_ARCHIVE, CP.N_CLICKS),
        (test_suite_ids.TestSuiteIds.BTN_RESTORE, CP.N_CLICKS),
    ],
    state=[("url", CP.PATHNAME)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_suite_archive(archive_clicks, restore_clicks, pathname):
  """Toggles archiving for a test suite."""
  if not archive_clicks and not restore_clicks:
    return dash.no_update

  trigger_id = typed_callback.triggered_id()
  if trigger_id not in [
      test_suite_ids.TestSuiteIds.BTN_ARCHIVE,
      test_suite_ids.TestSuiteIds.BTN_RESTORE,
  ]:
    return dash.no_update

  try:
    suite_id = int(pathname.split("/")[-1])
  except (ValueError, IndexError):
    return dash.no_update

  client = get_client()

  if trigger_id == test_suite_ids.TestSuiteIds.BTN_ARCHIVE:
    client.suites.archive_suite(suite_id)
  else:
    client.suites.unarchive_suite(suite_id)

  return pathname


@typed_callback(
    [
        (test_suite_ids.TestSuiteIds.NAME, CP.VALUE),
        (test_suite_ids.TestSuiteIds.DESC, CP.VALUE),
        (test_suite_ids.TestSuiteIds.STORE_BUILDER, CP.DATA),
    ],
    inputs=[(test_suite_ids.TestSuiteIds.NAME, "id")],
    state=[("url", CP.PATHNAME)],
)
def load_test_suite_data(_, pathname: str):
  """Loads existing test suite data if editing or viewing."""
  if pathname == "/test_suites/new":
    return "", "", []

  if not pathname.startswith("/test_suites/view/") and not pathname.startswith(
      "/test_suites/edit/"
  ):
    return typed_callback.no_update

  try:
    suite_id = int(pathname.split("/")[-1])
  except ValueError:
    return typed_callback.no_update

  client = get_client()
  s = client.suites.get_suite(suite_id)
  if not s:
    return "", "", []

  test_cases_data = client.suites.list_examples(suite_id)
  test_cases = []
  for tc in test_cases_data:
    q_asserts = []
    for a in tc.asserts:
      # Map Model to AssertItem structure
      if hasattr(a, "model_dump"):
        a_dict = a.model_dump()
        # id and type are top-level.
        q_asserts.append(a_dict)
      else:
        q_asserts.append({
            "id": getattr(a, "id", None),
            "type": a.type.value if hasattr(a.type, "value") else a.type,
            "params": getattr(a, "params", {}),
        })
    test_cases.append({
        "id": tc.id,
        "question": tc.question,
        "asserts": q_asserts,
    })

  return (
      s.name,
      s.description,
      test_cases,
  )


@typed_callback(
    (REDIRECT_HANDLER, CP.HREF),
    inputs=[
        (test_suite_ids.TestSuiteIds.SAVE_NEW_BTN, CP.N_CLICKS),
    ],
    state=[
        (test_suite_ids.TestSuiteIds.NAME, CP.VALUE),
        (test_suite_ids.TestSuiteIds.DESC, CP.VALUE),
    ],
    allow_duplicate=True,
    prevent_initial_call=True,
)
def create_test_suite(
    save_clicks: int | None,
    name: str | None,
    desc: str | None,
):
  """Handles creation of a new test suite."""
  if not save_clicks:
    return typed_callback.no_update

  if not name:
    return typed_callback.no_update

  try:
    client = get_client()
    # Create suite
    ds = client.suites.create_suite(
        name=name,
        description=desc,
    )
    # Redirect to view page
    return f"/test_suites/view/{ds.id}"
  except Exception:  # pylint: disable=broad-exception-caught
    traceback.print_exc()
    return typed_callback.no_update


@typed_callback(
    (REDIRECT_HANDLER, CP.HREF),
    inputs=[
        (test_suite_ids.TestSuiteIds.SAVE_EDIT_BTN, CP.N_CLICKS),
    ],
    state=[
        ("url", CP.PATHNAME),
        (test_suite_ids.TestSuiteIds.NAME, CP.VALUE),
        (test_suite_ids.TestSuiteIds.DESC, CP.VALUE),
        (test_suite_ids.TestSuiteIds.STORE_BUILDER, CP.DATA),
    ],
    allow_duplicate=True,
    prevent_initial_call=True,
)
def update_test_suite(
    save_clicks: int | None,
    pathname: str,
    name: str | None,
    desc: str | None,
    test_cases: list[dict[str, Any]] | None,
):
  """Handles updating an existing test suite."""
  if not save_clicks:
    return typed_callback.no_update

  if not name:
    return typed_callback.no_update

  try:
    suite_id = int(pathname.split("/")[-1])
    client = get_client()
    client.suites.update_suite(
        suite_id=suite_id,
        name=name,
        description=desc,
    )
    # Sync test cases
    if test_cases:
      client.suites.sync_suite(suite_id, test_cases)

    return f"/test_suites/view/{suite_id}"
  except Exception:  # pylint: disable=broad-exception-caught
    traceback.print_exc()
    return typed_callback.no_update


@typed_callback(
    (test_suite_ids.TestSuiteIds.TEST_CASE_LIST, CP.CHILDREN),
    inputs=[
        (test_suite_ids.TestSuiteIds.STORE_BUILDER, CP.DATA),
    ],
    state=[
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
)
def render_test_case_list(test_cases: list[dict[str, Any]], pathname: str):
  """Renders the list of test cases in the inventory."""
  if not test_cases:
    try:
      suite_id = pathname.rstrip("/").split("/")[-1]
    except (IndexError, AttributeError):
      suite_id = "new"

    return empty_states.render_empty_state(
        title="No test cases added yet",
        description=(
            "Start building your evaluation test suite by adding test cases to"
            " the inventory."
        ),
        button_label="Create First Test Case",
        href=f"/test_suites/edit/{suite_id}?action=add",
        icon="bi:playlist-add",
    )

  read_only = "/view/" in pathname
  if read_only:
    try:
      suite_id = int(pathname.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
      suite_id = 0

    return [
        dmc.Anchor(
            test_case_components.render_test_case_card(
                ui_state.TestCaseState(**tc), i, read_only=True
            ),
            href=f"/test_suites/edit/{suite_id}?test_case_id={tc.get('id')}",
            underline=False,
            c="inherit",
            style={"display": "block", "textDecoration": "none"},
        )
        for i, tc in enumerate(test_cases)
    ]

  return [
      test_case_components.render_test_case_card(
          ui_state.TestCaseState(**tc), i, read_only=False
      )
      for i, tc in enumerate(test_cases)
  ]


@typed_callback(
    [
        (test_suite_ids.TestSuiteIds.MODAL_CONFIG_EDIT, "opened"),
        (test_suite_ids.TestSuiteIds.NAME, CP.VALUE),
        (test_suite_ids.TestSuiteIds.DESC, CP.VALUE),
    ],
    inputs=[
        (test_suite_ids.TestSuiteIds.BTN_CONFIG_EDIT, CP.N_CLICKS),
        (test_suite_ids.TestSuiteIds.MODAL_CONFIG_CANCEL_BTN, CP.N_CLICKS),
        (test_suite_ids.TestSuiteIds.MODAL_CONFIG_CLOSE_BTN_X, CP.N_CLICKS),
        (test_suite_ids.TestSuiteIds.MODAL_CONFIG_SAVE_BTN, CP.N_CLICKS),
    ],
    state=[
        (test_suite_ids.TestSuiteIds.NAME, CP.VALUE),
        (test_suite_ids.TestSuiteIds.DESC, CP.VALUE),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_edit_config_modal(
    edit_clicks,
    cancel_clicks,
    x_clicks,
    save_clicks,
    current_name,
    current_desc,
):
  """Toggles the Edit Configuration modal."""
  del edit_clicks, cancel_clicks, x_clicks, save_clicks
  trigger = typed_callback.triggered_id()
  # If edit was clicked, open. If cancel, close.
  if trigger == test_suite_ids.TestSuiteIds.BTN_CONFIG_EDIT:
    # Open and Populate
    return (
        True,
        current_name,
        current_desc,
    )
  # Close
  return (
      False,
      typed_callback.no_update,
      typed_callback.no_update,
  )


@typed_callback(
    (REDIRECT_HANDLER, CP.HREF),
    inputs=[
        (test_suite_ids.TestSuiteIds.MODAL_CONFIG_SAVE_BTN, CP.N_CLICKS),
    ],
    state=[
        ("url", CP.PATHNAME),
        (test_suite_ids.TestSuiteIds.NAME, CP.VALUE),
        (test_suite_ids.TestSuiteIds.DESC, CP.VALUE),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def save_edit_config(
    save_clicks,
    pathname,
    name,
    desc,
):
  """Saves the test suite configuration from the modal."""
  if not save_clicks:
    return typed_callback.no_update

  # Reuse the update logic from `update_test_suite` but for config only
  return update_test_suite(
      save_clicks=save_clicks,
      pathname=pathname,
      name=name,
      desc=desc,
      test_cases=None,
  )
