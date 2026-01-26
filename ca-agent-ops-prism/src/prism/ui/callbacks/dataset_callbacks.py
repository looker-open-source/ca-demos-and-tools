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

"""Callbacks for the Datasets UI."""

import traceback
from typing import Any
import urllib.parse

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas import agent as agent_schemas
from prism.ui.components import dataset_components
from prism.ui.components import empty_states
from prism.ui.components import tables
from prism.ui.components.agent_components import render_agent_card
from prism.ui.constants import CP
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.models import ui_state
from prism.ui.pages import dataset_ids
from prism.ui.pages.dataset_ids import DatasetHomeIds
from prism.ui.pages.evaluation_ids import EvaluationIds
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
        (DatasetHomeIds.DATASETS_LIST, CP.CHILDREN),
        (DatasetHomeIds.LOADING, CP.VISIBLE),
    ],
    inputs=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
)
def update_datasets_list(pathname: str, search: str):
  """Renders the list of datasets on the dashboard."""
  if pathname != "/test_suites":
    return typed_callback.no_update, typed_callback.no_update

  # Parse Filters from URL
  parsed_qs = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
  coverage = parsed_qs.get("coverage", [None])[0]

  client = get_client()
  suites_with_stats = client.suites.get_suites_with_stats(
      coverage=coverage,
  )

  if not suites_with_stats:
    return (
        empty_states.render_empty_state(
            title="No Test Suites Found",
            description=(
                "Create your first dataset to start defining evaluation"
                " criteria."
            ),
            button_label="Create Test Suite",
            href="/test_suites/new",
            icon="bi:collection",
        ),
        False,
    )

  table = tables.render_dataset_table(suites_with_stats)

  return table, False


@typed_callback(
    dash.Output("url", "search", allow_duplicate=True),
    inputs=[
        (DatasetHomeIds.FILTER_COVERAGE, CP.VALUE),
    ],
    state=[("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_dataset_url_from_filters(coverage: str | None, current_search: str):
  """Update URL search params from Datasets Home filters."""
  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )

  if coverage:
    params["coverage"] = [coverage]
  else:
    params.pop("coverage", None)

  new_search = (
      f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
  )
  return new_search


@typed_callback(
    (DatasetHomeIds.FILTER_COVERAGE, CP.VALUE),
    inputs=[("url", CP.SEARCH)],
)
def sync_dataset_filters_to_url(search: str):
  """Sync Datasets Home filters to URL search params."""
  if not search:
    return None

  params = urllib.parse.parse_qs(search.lstrip("?"))
  return params.get("coverage", [None])[0]


@typed_callback(
    [
        (dataset_ids.DatasetIds.NAME, CP.VALUE),
        (dataset_ids.DatasetIds.DESC, CP.VALUE),
        (dataset_ids.DatasetIds.STORE_BUILDER, CP.DATA),
    ],
    inputs=[(dataset_ids.DatasetIds.NAME, "id")],
    state=[("url", CP.PATHNAME)],
)
def load_dataset_data(_, pathname: str):
  """Loads existing dataset data if editing or viewing."""
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

  examples = client.suites.list_examples(suite_id)
  questions = []
  for e in examples:
    q_asserts = []
    for a in e.asserts:
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
    questions.append({
        "id": e.id,
        "question": e.question,
        "asserts": q_asserts,
    })

  return (
      s.name,
      s.description,
      questions,
  )


@typed_callback(
    (REDIRECT_HANDLER, CP.HREF),
    inputs=[
        (dataset_ids.DatasetIds.SAVE_NEW_BTN, CP.N_CLICKS),
    ],
    state=[
        (dataset_ids.DatasetIds.NAME, CP.VALUE),
        (dataset_ids.DatasetIds.DESC, CP.VALUE),
    ],
    allow_duplicate=True,
    prevent_initial_call=True,
)
def create_dataset(
    save_clicks: int | None,
    name: str | None,
    desc: str | None,
):
  """Handles creation of a new dataset."""
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
        (dataset_ids.DatasetIds.SAVE_EDIT_BTN, CP.N_CLICKS),
    ],
    state=[
        ("url", CP.PATHNAME),
        (dataset_ids.DatasetIds.NAME, CP.VALUE),
        (dataset_ids.DatasetIds.DESC, CP.VALUE),
        (dataset_ids.DatasetIds.STORE_BUILDER, CP.DATA),
    ],
    allow_duplicate=True,
    prevent_initial_call=True,
)
def update_dataset(
    save_clicks: int | None,
    pathname: str,
    name: str | None,
    desc: str | None,
    questions: list[dict[str, Any]] | None,
):
  """Handles updating an existing dataset."""
  if not save_clicks:
    return typed_callback.no_update

  if not name:
    return typed_callback.no_update

  try:
    ds_id = int(pathname.split("/")[-1])
    client = get_client()
    client.suites.update_suite(
        suite_id=ds_id,
        name=name,
        description=desc,
    )
    # Sync questions
    if questions:
      client.suites.sync_suite(ds_id, questions)

    return f"/test_suites/view/{ds_id}"
  except Exception:  # pylint: disable=broad-exception-caught
    traceback.print_exc()
    return typed_callback.no_update


@typed_callback(
    (dataset_ids.DatasetIds.QUESTION_LIST, CP.CHILDREN),
    inputs=[
        (dataset_ids.DatasetIds.STORE_BUILDER, CP.DATA),
    ],
    state=[
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
)
def render_question_list(questions: list[dict[str, Any]], pathname: str):
  """Renders the list of questions in the inventory."""
  if not questions:
    try:
      dataset_id = pathname.rstrip("/").split("/")[-1]
    except (IndexError, AttributeError):
      dataset_id = "new"

    return empty_states.render_empty_state(
        title="No questions added yet",
        description=(
            "Start building your evaluation dataset by adding questions to the"
            " inventory."
        ),
        button_label="Create First Question",
        href=f"/test_suites/edit/{dataset_id}?action=add",
        icon="bi:playlist-add",
    )

  read_only = "/view/" in pathname
  if read_only:
    try:
      dataset_id = int(pathname.rstrip("/").split("/")[-1])
    except (ValueError, IndexError):
      dataset_id = 0

    return [
        dmc.Anchor(
            dataset_components.render_question_card(
                ui_state.SuiteQuestion(**q), i, read_only=True
            ),
            href=f"/test_suites/edit/{dataset_id}?test_case_id={q.get('id')}",
            underline=False,
            c="inherit",
            style={"display": "block", "textDecoration": "none"},
        )
        for i, q in enumerate(questions)
    ]

  return [
      dataset_components.render_question_card(
          ui_state.SuiteQuestion(**q), i, read_only=False
      )
      for i, q in enumerate(questions)
  ]


@typed_callback(
    [
        (dataset_ids.DatasetIds.MODAL_CONFIG_EDIT, "opened"),
        (dataset_ids.DatasetIds.NAME, CP.VALUE),
        (dataset_ids.DatasetIds.DESC, CP.VALUE),
    ],
    inputs=[
        (dataset_ids.DatasetIds.BTN_CONFIG_EDIT, CP.N_CLICKS),
        (dataset_ids.DatasetIds.MODAL_CONFIG_CANCEL_BTN, CP.N_CLICKS),
        (dataset_ids.DatasetIds.MODAL_CONFIG_CLOSE_BTN_X, CP.N_CLICKS),
        (dataset_ids.DatasetIds.MODAL_CONFIG_SAVE_BTN, CP.N_CLICKS),
    ],
    state=[
        (dataset_ids.DatasetIds.NAME, CP.VALUE),
        (dataset_ids.DatasetIds.DESC, CP.VALUE),
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
  if trigger == dataset_ids.DatasetIds.BTN_CONFIG_EDIT:
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
        (dataset_ids.DatasetIds.MODAL_CONFIG_SAVE_BTN, CP.N_CLICKS),
    ],
    state=[
        ("url", CP.PATHNAME),
        (dataset_ids.DatasetIds.NAME, CP.VALUE),
        (dataset_ids.DatasetIds.DESC, CP.VALUE),
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
  """Saves the dataset configuration from the modal."""
  if not save_clicks:
    return typed_callback.no_update

  # Reuse the update logic from `update_dataset` but for config only
  return update_dataset(
      save_clicks=save_clicks,
      pathname=pathname,
      name=name,
      desc=desc,
      questions=None,
  )
