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

"""Callbacks for Evaluation pages."""

import logging
import time
import traceback
from typing import Any
import urllib.parse

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import flask
from prism.client import get_client
from prism.common.schemas import agent as agent_schemas
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.execution import Trial
from prism.ui import constants
from prism.ui.components import assertion_components
from prism.ui.components import cards
from prism.ui.components import run_components
from prism.ui.components import tables
from prism.ui.components import test_case_components as test_case_components
from prism.ui.components import timeline
from prism.ui.constants import CP
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
from prism.ui.models.ui_state import AssertionMetric
from prism.ui.models.ui_state import AssertionSummary
from prism.ui.models.ui_state import RunDetailPageState
from prism.ui.utils import handle_errors
from prism.ui.utils import typed_callback


logger = logging.getLogger(__name__)


# --- List Page ---


@typed_callback(
    (EvaluationIds.RUN_LIST_CONTAINER, CP.CHILDREN),
    inputs=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
    ],
)
def render_run_list(pathname: str, search: str):
  """Renders the evaluations list, filtered by URL search parameters."""
  if pathname != "/evaluations":
    return dash.no_update

  # Parse Filters from URL
  parsed_qs = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
  agent_id = parsed_qs.get("agent_id", [None])[0]
  suite_id = parsed_qs.get("suite_id", [None])[0]
  status = parsed_qs.get("status", [None])[0]

  # Convert types
  agent_id = int(agent_id) if agent_id else None
  suite_id = int(suite_id) if suite_id else None
  status_enum = RunStatus(status) if status else None

  client = get_client()
  runs = client.runs.list_runs(
      agent_id=agent_id,
      original_suite_id=suite_id,
      status=status_enum,
  )

  # Fetch metadata for display
  # (Denormalized in schema usually, but let's be sure)
  # Actually RunSchema has agent_name and suite_name

  if not runs:
    return dmc.Text("No evaluations found.", c="dimmed", ta="center", py="xl")

  return tables.render_run_table(
      runs,
      agent_names={},  # Handled by schema denormalization if available
      suite_names={},
      table_id=None,
  )


@typed_callback(
    dash.Output("url", "search", allow_duplicate=True),
    inputs=[
        (EvaluationIds.FILTER_AGENT, CP.VALUE),
        (EvaluationIds.FILTER_SUITE, CP.VALUE),
        (EvaluationIds.FILTER_STATUS, CP.VALUE),
    ],
    state=[("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_eval_url_from_filters(
    agent_id: str | None,
    suite_id: str | None,
    status: str | None,
    current_search: str,
):
  """Update URL search params from UI filters."""
  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )

  # Update params
  if agent_id:
    params["agent_id"] = [agent_id]
  else:
    params.pop("agent_id", None)

  if suite_id:
    params["suite_id"] = [suite_id]
  else:
    params.pop("suite_id", None)

  if status:
    params["status"] = [status]
  else:
    params.pop("status", None)

  new_search = (
      f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""
  )
  return new_search


@typed_callback(
    output=[
        (EvaluationIds.FILTER_AGENT, CP.VALUE),
        (EvaluationIds.FILTER_SUITE, CP.VALUE),
        (EvaluationIds.FILTER_STATUS, CP.VALUE),
    ],
    inputs=[("url", CP.SEARCH)],
)
def sync_eval_filters_to_url(search: str):
  """Sync UI filters to URL search params on load/change."""
  if not search:
    return None, None, None

  params = urllib.parse.parse_qs(search.lstrip("?"))
  agent_id = params.get("agent_id", [None])[0]
  suite_id = params.get("suite_id", [None])[0]
  status = params.get("status", [None])[0]

  return agent_id, suite_id, status


@typed_callback(
    output=[
        (EvaluationIds.FILTER_AGENT, CP.DATA),
        (EvaluationIds.FILTER_SUITE, CP.DATA),
    ],
    inputs=[("url", CP.PATHNAME)],
)
def populate_eval_filter_options(pathname: str):
  """Populate Agent and Test Suite filter options."""

  if pathname != "/evaluations":
    return typed_callback.no_update, dash.no_update

  client = get_client()
  agents = client.agents.list_agents()
  agent_data = [{"label": a.name, "value": str(a.id)} for a in agents]

  # Get unique test suites based on original_suite_id from snapshots
  suites = client.runs.get_unique_suites_from_snapshots()
  suite_data = [
      {"label": s["name"], "value": str(s["original_suite_id"])} for s in suites
  ]

  return agent_data, suite_data


# --- Comparison Modal ---


@typed_callback(
    output=[
        dash.Output(EvaluationIds.MODAL_COMPARE_RUNS, "opened"),
        dash.Output(EvaluationIds.COMPARE_BASE_SELECT, "data"),
        dash.Output(
            EvaluationIds.COMPARE_CHALLENGE_SELECT,
            "data",
            allow_duplicate=True,
        ),
        dash.Output(EvaluationIds.COMPARE_BASE_SELECT, "value"),
        dash.Output(EvaluationIds.COMPARE_CHALLENGE_SELECT, "value"),
    ],
    inputs=[
        dash.Input(
            {"type": EvaluationIds.BTN_OPEN_COMPARE_MODAL, "index": dash.ALL},
            "n_clicks",
        ),
        dash.Input(EvaluationIds.BTN_CANCEL_COMPARE, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def toggle_compare_modal(n_clicks_all, n_cancel):
  """Opens/Closes the comparison modal and populates run data."""
  del n_clicks_all, n_cancel
  ctx = dash.callback_context
  triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]

  # Check if closed
  if triggered_id == EvaluationIds.BTN_CANCEL_COMPARE:
    return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update

  # Guard: Check for actual clicks if opening
  # If triggered by components loading (dynamic), values might be None
  is_open_click = False
  for t in ctx.triggered:
    # If the value is truthy (int > 0), it was a click
    # If None, it might be just initial rendering
    if t["value"]:
      is_open_click = True
      break

  if not is_open_click:
    return (
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  # Open
  # Determine if specific run button clicked (index != "list")
  preselect_run_id = None
  t_id: Any = getattr(ctx, "triggered_id", None)
  # Handle the case where triggered_id might be a dict (pattern-matching)
  if t_id and isinstance(t_id, dict):
    idx = str(t_id.get("index", ""))
    if idx != "list":
      preselect_run_id = idx

  # Fetch Data
  client = get_client()

  # If we have a preselect_run_id, we only want to show compatible runs
  # (same test suite)
  filter_suite_id = None
  if preselect_run_id:
    current_run = client.runs.get_run(int(preselect_run_id))
    if current_run:
      filter_suite_id = current_run.original_suite_id

  runs = client.runs.list_runs(original_suite_id=filter_suite_id)
  data = []
  for r in runs:
    agent_name = r.agent_name or "Unknown Agent"
    date_str = (
        r.created_at.strftime("%Y-%m-%d %H:%M")
        if r.created_at
        else "Unknown Date"
    )
    accuracy = r.accuracy
    acc_str = f"{accuracy*100:.1f}%" if accuracy is not None else "N/A"

    label = f"Run #{r.id} • {agent_name} • {date_str} • Acc: {acc_str}"
    data.append({"value": str(r.id), "label": label})

  # Preselect
  base_val = preselect_run_id if preselect_run_id else None
  chal_val = None  # Default empty

  return True, data, data, base_val, chal_val


@typed_callback(
    output=[
        dash.Output(REDIRECT_HANDLER, "href", allow_duplicate=True),
        dash.Output(
            EvaluationIds.MODAL_COMPARE_RUNS, "opened", allow_duplicate=True
        ),
    ],
    inputs=[
        dash.Input(EvaluationIds.BTN_GO_COMPARE, "n_clicks"),
    ],
    state=[
        dash.State(EvaluationIds.COMPARE_BASE_SELECT, "value"),
        dash.State(EvaluationIds.COMPARE_CHALLENGE_SELECT, "value"),
    ],
    prevent_initial_call=True,
)
def navigate_to_comparison(n_clicks, base_id, chal_id):
  """Navigates to the comparison page for two selected runs."""
  if not n_clicks or not base_id or not chal_id:
    return dash.no_update, dash.no_update

  # Use query params
  # params = {
  #     EvaluationIds.COMPARE_BASE_SELECT: base_id,
  #     EvaluationIds.COMPARE_CHALLENGE_SELECT: chal_id,
  # }
  href = f"/compare?base_run_id={base_id}&challenger_run_id={chal_id}"
  return href, False


@typed_callback(
    output=[
        dash.Output(
            EvaluationIds.COMPARE_BASE_SELECT, "value", allow_duplicate=True
        ),
        dash.Output(
            EvaluationIds.COMPARE_CHALLENGE_SELECT,
            "value",
            allow_duplicate=True,
        ),
    ],
    inputs=[dash.Input(EvaluationIds.BTN_SWAP_COMPARE_MODAL, "n_clicks")],
    state=[
        dash.State(EvaluationIds.COMPARE_BASE_SELECT, "value"),
        dash.State(EvaluationIds.COMPARE_CHALLENGE_SELECT, "value"),
    ],
    prevent_initial_call=True,
)
def swap_modal_runs(n_clicks: int, base_id: str | int, chal_id: str | int):
  """Swaps the base and challenger runs in the comparison modal."""
  if not n_clicks:
    return dash.no_update, dash.no_update
  return chal_id, base_id


@typed_callback(
    output=dash.Output(
        EvaluationIds.COMPARE_CHALLENGE_SELECT,
        "data",
        allow_duplicate=True,
    ),
    inputs=[dash.Input(EvaluationIds.COMPARE_BASE_SELECT, "value")],
    prevent_initial_call=True,
)
def filter_challenger_runs(base_run_id: str | None) -> list[dict[str, str]]:
  """Filters challenger runs to match the test suite of the selected base run."""
  if not base_run_id:
    return dash.no_update

  client = get_client()
  base_run = client.runs.get_run(int(base_run_id))
  if not base_run:
    return dash.no_update

  runs = client.runs.list_runs(original_suite_id=base_run.original_suite_id)
  data = []
  for r in runs:
    agent_name = r.agent_name or "Unknown Agent"
    date_str = (
        r.created_at.strftime("%Y-%m-%d %H:%M")
        if r.created_at
        else "Unknown Date"
    )
    accuracy = r.accuracy
    acc_str = f"{accuracy*100:.1f}%" if accuracy is not None else "N/A"

    label = f"Run #{r.id} • {agent_name} • {date_str} • Acc: {acc_str}"
    data.append({"value": str(r.id), "label": label})

  return data


def render_assertion_performance(trials: list[Trial]) -> dmc.Paper | None:
  """Renders a horizontal bar chart of pass rates by assertion type."""
  # Map assertion type to [passed_count, total_count]
  counts: dict[str, list[int]] = {}

  # Map to human readable names
  name_map = {
      "data-check-row": "Data Check Row",
      "data-check-row-count": "Data Check Row Count",
      "query-contains": "Query Contains",
      "text-contains": "Text Contains",
      "chart-check-type": "Chart Check Type",
      "duration-max-ms": "Duration Max Ms",
      "looker-query-match": "Looker Query Match",
  }

  for t in trials:
    for ar in t.assertion_results:
      type_val = ar.assertion.type
      # Use readable name if available, else fall back to title case replacement
      type_name = name_map.get(type_val, type_val.replace("-", " ").title())

      if type_name not in counts:
        counts[type_name] = [0, 0]
      counts[type_name][1] += 1
      if ar.passed:
        counts[type_name][0] += 1

  # Transform to chart data
  chart_data = []
  for type_name, vals in counts.items():
    pass_rate = (vals[0] / vals[1] * 100) if vals[1] > 0 else 0
    chart_data.append({
        "type": type_name,
        "pass_rate": round(pass_rate, 1),
        "total": vals[1],
        "label": f"{type_name} ({vals[0]}/{vals[1]})",
    })

  # Sort by pass rate ascending to show problem areas at top/bottom
  chart_data.sort(key=lambda x: x["pass_rate"])

  if not chart_data:
    return None

  return cards.render_detail_card(
      title="Assertion Performance by Type",
      description=(
          "Pass rate for each assertion type across all trials in this run."
      ),
      children=[
          dmc.BarChart(
              h=max(200, len(chart_data) * 40),
              data=chart_data,
              dataKey="type",
              orientation="vertical",
              yAxisProps={"width": 120},
              series=[{
                  "name": "pass_rate",
                  "color": "blue.6",
                  "label": "Pass Rate %",
              }],
              xAxisLabel="Pass Rate (%)",
              withTooltip=True,
              gridAxis="x",
              tickLine="none",
          ),
      ],
  )


# --- Detail Page ---


@typed_callback(
    output=dash.Output(EvaluationIds.RUN_DATA_STORE, CP.DATA),
    inputs=[
        ("url", CP.PATHNAME),
        (EvaluationIds.RUN_POLLING_INTERVAL, "n_intervals"),
        (EvaluationIds.RUN_UPDATE_SIGNAL, CP.DATA),
    ],
)
@handle_errors
def fetch_run_detail_data(
    pathname: str, unused_n_intervals: int, unused_update_signal: Any
):
  """Fetches and stores data for the Run Detail page."""
  logger.info("fetch_run_detail_data started: %s", pathname)
  if not pathname or not pathname.startswith("/evaluations/runs/"):
    return dash.no_update

  try:
    run_id = int(pathname.rstrip("/").split("/")[-1])
  except ValueError:
    return dash.no_update

  client = get_client()
  run = client.runs.get_run(run_id)
  if not run:
    return dash.no_update

  trials = client.runs.list_trials(run_id)

  state = RunDetailPageState(run=run, trials=trials)
  return state.model_dump(mode="json")


@typed_callback(
    output=[
        (EvaluationIds.RUN_BREADCRUMBS_CONTAINER, CP.CHILDREN),
        (EvaluationIds.RUN_DETAIL_STATS, CP.CHILDREN),
        (EvaluationIds.RUN_CHARTS_CONTAINER, CP.CHILDREN),
        (EvaluationIds.RUN_TRIALS_CONTAINER, CP.CHILDREN),
        (EvaluationIds.RUN_STATUS_BADGE, CP.CHILDREN),
        (EvaluationIds.RUN_STATUS_BADGE, CP.COLOR),
        (EvaluationIds.BTN_PAUSE_RUN, CP.STYLE),
        (EvaluationIds.BTN_RESUME_RUN, CP.STYLE),
        (EvaluationIds.BTN_CANCEL_RUN_EXEC, CP.STYLE),
        (EvaluationIds.RUN_POLLING_INTERVAL, CP.DISABLED),
        (EvaluationIds.RUN_CONTEXT_TRIGGER, CP.DATA),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_DATA_STORE, CP.DATA)],
    state=[dash.State(EvaluationIds.RUN_CONTEXT_TRIGGER, CP.DATA)],
)
@handle_errors
def render_run_detail_components(
    run_data: dict[str, Any], current_trigger_id: int | None
):
  """Renders the components for the Run Detail page."""
  logger.info("render_run_detail_components triggered")
  if not run_data:
    return [dash.no_update] * 11

  state = RunDetailPageState.model_validate(run_data)

  run = state.run
  trials = state.trials
  run_id = run.id

  # Only trigger context update if run_id changed or not yet triggered
  context_trigger = run_id if current_trigger_id != run_id else dash.no_update

  # Calculate Stats
  total_trials = len(trials)
  completed_trials = 0
  scored_trials = [t for t in trials if t.score is not None]
  total_score = sum(t.score for t in scored_trials)
  avg_accuracy = (
      (total_score / len(scored_trials) * 100) if scored_trials else None
  )

  durations = []
  for t in trials:
    durations.append(t.duration_ms or 0)
    if t.status in (RunStatus.COMPLETED, RunStatus.FAILED):
      completed_trials += 1

  # Badge/Buttons/Polling Logic
  badge_color = "gray"
  show_pause = {"display": "none"}
  show_resume = {"display": "none"}
  show_cancel = {"display": "none"}
  polling_disabled = True

  if run.status in (
      RunStatus.RUNNING,
      RunStatus.PENDING,
      RunStatus.EXECUTING,
      RunStatus.EVALUATING,
  ):
    badge_color = "blue"
    show_pause = {"display": "block"}
    show_cancel = {"display": "block"}
    polling_disabled = False
  elif run.status == RunStatus.PAUSED:
    badge_color = "orange"
    show_resume = {"display": "block"}
    show_cancel = {"display": "block"}
    polling_disabled = False
  elif run.status == RunStatus.COMPLETED:
    badge_color = "green"
  elif run.status == RunStatus.FAILED:
    badge_color = "red"
  elif run.status == RunStatus.CANCELLED:
    badge_color = "gray"

  # Breadcrumbs
  breadcrumbs = dmc.Breadcrumbs(
      separator="/",
      mb="lg",
      children=[
          dmc.Anchor("Evaluations", href="/evaluations", size="sm", fw=500),
          dmc.Text(f"Run #{run_id}", size="sm", fw=500, c="dimmed"),
      ],
  )

  # Stats Cards
  avg_duration = (sum(durations) / total_trials) if total_trials > 0 else 0.0
  stats = [
      cards.render_stat_card(
          "Agent",
          run.agent_name or "N/A",
          icon="bi:robot",
          color="blue",
          value_href=f"/agents/view/{run.agent_id}",
      ),
      cards.render_stat_card(
          "Test Suite",
          run.suite_name or "N/A",
          icon="material-symbols:folder-open",
          color="blue",
          value_href=(
              f"/test_suites/view/{run.original_suite_id}"
              if run.original_suite_id
              else None
          ),
      ),
      cards.render_stat_card(
          "Avg Accuracy",
          f"{avg_accuracy:.1f}%" if avg_accuracy is not None else "N/A",
          icon="bi:trophy-fill",
          color="yellow",
      ),
      cards.render_stat_card(
          "Avg Trial Duration",
          f"{avg_duration / 1000:.2f}s",
          icon="material-symbols:timer",
          color="blue",
      ),
  ]

  # Trials Table
  trials_update = dmc.Stack(
      gap="md",
      children=[
          dmc.Text("Trials", fw=700, size="lg"),
          dmc.Paper(
              withBorder=True,
              radius="md",
              p=0,
              shadow="sm",
              style={"overflow": "hidden"},
              children=[
                  tables.render_trial_table(trials),
              ],
          ),
      ],
  )

  assertion_update = render_assertion_performance(trials)

  # Agent Context Card
  context_card = run_components.render_run_context(
      run.agent_context_snapshot, loading=False
  )

  charts_grid = dmc.SimpleGrid(
      cols={"base": 1, "lg": 2},
      spacing="xl",
      children=[
          context_card,
          assertion_update
          or dmc.Alert(
              "No assertion data available for this run.",
              color="gray",
              variant="light",
          ),
      ],
  )

  return (
      breadcrumbs,
      stats,
      [charts_grid],
      trials_update,
      run.status.value,
      badge_color,
      show_pause,
      show_resume,
      show_cancel,
      polling_disabled,
      context_trigger,
  )


@typed_callback(
    output=[
        (EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_CONTEXT_TRIGGER, CP.DATA)],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True,
)
def fetch_run_context(run_id: int):
  """Fetches run snapshot and initializes the context store."""
  logger.info("fetch_run_context triggered for run %s", run_id)
  if not run_id:
    return (dash.no_update,)

  client = get_client()
  run = client.runs.get_run(run_id)
  if not run:
    return (dash.no_update,)

  # Delay live fetch to avoid blocking the initial page load
  snapshot_data = run.agent_context_snapshot or {}
  diff_data = {
      "snapshot": snapshot_data,
      "live": None,
      "agent_id": run.agent_id,
      "is_fetching": False,
  }

  logger.info("fetch_run_context initialized snapshot for run %s", run_id)
  return (diff_data,)


@typed_callback(
    output=[
        (EvaluationIds.RUN_CONTEXT_DIFF_CONTENT, CP.CHILDREN),
        (EvaluationIds.RUN_CONTEXT_DIFF_MODAL, "opened"),
        (EvaluationIds.RUN_CONTEXT_DIFF_TITLE, CP.CHILDREN),
        (EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_CONTEXT_DIFF_BTN, CP.N_CLICKS)],
    state=[dash.State(EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_config_diff_modal(n_clicks: int, diff_data: dict[str, Any]):
  """Opens the config diff modal and triggers fetch if live config is missing."""
  if not n_clicks or not diff_data:
    return dash.no_update, False, dash.no_update, dash.no_update

  # 1. If live config is already fetched, just render it
  if diff_data.get("live"):
    diff_table, change_count = run_components.render_modern_context_diff(
        diff_data.get("snapshot", {}), diff_data.get("live", {})
    )
    # Re-render title with badge
    title_children = [
        dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
        (
            dmc.Badge(
                "Changes detected",
                color="orange",
                variant="light",
                radius="sm",
                size="xs",
                fw=700,
            )
            if change_count > 0
            else dmc.Badge(
                "No changes detected",
                color="gray",
                variant="light",
                radius="sm",
                size="xs",
            )
        ),
    ]
    return diff_table, True, title_children, dash.no_update

  # 2. Otherwise: Show skeleton and trigger fetch by updating store
  # Trigger fetch by updating store state
  new_state = diff_data.copy()
  new_state["is_fetching"] = True

  skeleton = dmc.Stack(
      gap="xs",
      children=[
          dmc.Skeleton(height=15, width="100%"),
          dmc.Skeleton(height=15, width="80%"),
          dmc.Skeleton(height=15, width="95%"),
          dmc.Skeleton(height=15, width="75%"),
      ],
  )

  title_loading = [
      dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
      dmc.Skeleton(height=20, width=120, radius="sm"),
  ]

  return skeleton, True, title_loading, new_state


@typed_callback(
    output=[
        (EvaluationIds.RUN_CONTEXT_DIFF_CONTENT, CP.CHILDREN),
        (EvaluationIds.RUN_CONTEXT_DIFF_TITLE, CP.CHILDREN),
        (EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def fetch_live_config_for_diff(diff_data: dict[str, Any]):
  """Fetches live agent configuration when is_fetching is True."""
  if not diff_data or not diff_data.get("is_fetching"):
    return dash.no_update, dash.no_update, dash.no_update

  agent_id = diff_data.get("agent_id")
  logger.info("fetch_live_config_for_diff started for agent %s", agent_id)
  if not agent_id:
    return dash.no_update, dash.no_update, dash.no_update

  client = get_client()
  live_context = None
  try:
    # This is the slow GDA API call
    live_context = client.agents.get_published_context(agent_id)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logging.error("Failed to fetch live context for agent %s: %s", agent_id, e)

  snapshot_data = diff_data.get("snapshot", {})
  # Fallback to snapshot if live fetch fails
  live_data = live_context if live_context else snapshot_data

  diff_table, change_count = run_components.render_modern_context_diff(
      snapshot_data, live_data
  )

  new_state = diff_data.copy()
  new_state["live"] = live_data
  new_state["is_fetching"] = False

  # Re-render title with badge
  title_children = [
      dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
      (
          dmc.Badge(
              "Changes detected",
              color="orange",
              variant="light",
              radius="sm",
              size="xs",
              fw=700,
          )
          if change_count > 0
          else dmc.Badge(
              "No changes detected",
              color="gray",
              variant="light",
              radius="sm",
              size="xs",
          )
      ),
  ]

  return diff_table, title_children, new_state


# --- Trial Detail Page ---


def _calculate_assertion_summary(
    assertion_details: list[dict[str, Any]],
) -> AssertionSummary:
  """Calculates pass/fail metrics for a list of assertion details."""
  overall = {"total": 0, "passed": 0}
  accuracy = {"total": 0, "passed": 0}
  diagnostic = {"total": 0, "passed": 0}

  for a in assertion_details:
    passed = a.get("passed", False)
    weight = a.get("weight", 0)

    overall["total"] += 1
    if passed:
      overall["passed"] += 1

    if weight > 0:
      accuracy["total"] += 1
      if passed:
        accuracy["passed"] += 1
    else:
      diagnostic["total"] += 1
      if passed:
        diagnostic["passed"] += 1

  def _to_metric(counts: dict[str, int]) -> AssertionMetric:
    total = counts["total"]
    passed = counts["passed"]
    failed = total - passed
    rate = (passed / total * 100) if total > 0 else None
    return AssertionMetric(
        total=total, passed=passed, failed=failed, pass_rate=rate
    )

  return AssertionSummary(
      overall=_to_metric(overall),
      accuracy=_to_metric(accuracy),
      diagnostic=_to_metric(diagnostic),
  )


@typed_callback(
    [
        (EvaluationIds.TRIAL_BREADCRUMBS_CONTAINER, CP.CHILDREN),
        (EvaluationIds.TRIAL_TITLE, CP.CHILDREN),
        (EvaluationIds.TRIAL_DESCRIPTION, CP.CHILDREN),
        (EvaluationIds.TRIAL_ACTIONS, CP.CHILDREN),
        (EvaluationIds.TRIAL_DETAIL_CONTAINER, CP.CHILDREN),
        (EvaluationIds.TRIAL_SUGGESTIONS_CONTENT, CP.CHILDREN),
        (EvaluationIds.TRIAL_SUG_ACCORDION, "style"),
    ],
    inputs=[
        ("url", CP.PATHNAME),
        ("url", CP.SEARCH),
        (EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL, CP.DATA),
    ],
    state=[(EvaluationIds.TRIAL_SUG_LOADING_STORE, CP.DATA)],
)
def render_trial_detail(
    pathname: str,
    search: str,
    update_signal: Any = None,
    sug_loading: bool = False,
):
  """Renders the Trial Detail page."""
  # pylint: disable=unused-argument
  if not pathname or not pathname.startswith("/evaluations/trials/"):
    return [dash.no_update] * 5

  try:
    trial_id = int(pathname.split("/")[-1])
  except ValueError:
    return [dash.no_update] * 5

  logging.info(
      "Rendering trial detail pathname=%s loading=%s",
      pathname,
      sug_loading,
  )

  client = get_client()
  try:
    trial = client.runs.get_trial(trial_id)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logging.error("Failed to load trial %s: %s", trial_id, e)
    return [dmc.Alert(f"Error loading trial: {str(e)}", color="red")] + [
        dash.no_update
    ] * 4

  if not trial:
    return [dmc.Alert("Trial not found", color="red")] + [dash.no_update] * 4

  # Fetch parent run to get original_suite_id
  run = client.runs.get_run(trial.run_id)
  run_link = "#"
  if run and run.original_suite_id:
    run_link = f"/test_suites/view/{run.original_suite_id}"

  # Unified Breadcrumbs: Evaluations / Run #<run_id> / Trial #<trial_id>
  breadcrumbs = dmc.Breadcrumbs(
      separator="/",
      mb="lg",
      children=[
          dmc.Anchor("Evaluations", href="/evaluations", size="sm", fw=500),
          dmc.Anchor(
              f"Run #{trial.run_id}",
              href=f"/evaluations/runs/{trial.run_id}",
              size="sm",
              fw=500,
          ),
          dmc.Text(f"Trial #{trial.id}", size="sm", fw=500, c="dimmed"),
      ],
  )

  # Mapping for assertion cards
  assertion_details = []
  if trial.assertion_results:
    for ar in trial.assertion_results:
      details = {
          "type": ar.assertion.type,
          "weight": ar.assertion.weight,
          "passed": ar.passed,
          "reasoning": ar.reasoning,
          "error_message": ar.error_message,
      }
      # Extract specific parameters from the flattened schema
      assertion_data = ar.assertion.model_dump()
      for k, v in assertion_data.items():
        if k not in ["type", "weight", "id", "reasoning"]:
          details[k] = v
      assertion_details.append(details)

  # Check Filter
  parsed_qs = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
  filter_cat = parsed_qs.get("assertion_category", ["all"])[0] or "all"
  filter_stat = parsed_qs.get("assertion_status", ["all"])[0] or "all"
  filter_type = parsed_qs.get("assertion_type", ["all"])[0] or "all"

  # Latency & TTFR
  duration_ms = trial.duration_ms or 0
  ttfr_ms = trial.ttfr_ms or 0

  # If ttfr_ms is missing but we have trace results, we might want a fallback
  # but the client should have already handled this.
  # However, render_trial_detail recalculates timeline_obj which is fine.
  trace_results = trial.trace_results or []
  timeline_obj = client.runs.parse_timeline(
      trace_results, ttfr_ms=ttfr_ms, total_duration_ms=duration_ms
  )

  # --- Stats Cards ---
  failed_at_text = None
  if trial.status == RunStatus.FAILED:
    failed_at_text = dmc.Text(
        f"Failed at: {trial.failed_stage}" if trial.failed_stage else "",
        c="red",
        size="xs",
    )
  status_color = "gray"
  if trial.status == RunStatus.COMPLETED:
    status_color = "green"
  elif trial.status == RunStatus.FAILED:
    status_color = "red"
  elif trial.status in [RunStatus.EXECUTING, RunStatus.EVALUATING]:
    status_color = "blue"

  if trial.status == RunStatus.FAILED:
    error_card = cards.render_error_card(
        message=trial.error_message or "Unknown error",
        traceback_str=trial.error_traceback,
        stage=trial.failed_stage,
    )
  else:
    error_card = None

  stats_cards = dmc.Group(
      grow=True,
      children=[
          dmc.Paper(
              p="md",
              radius="md",
              withBorder=True,
              children=[
                  dmc.Group([
                      dmc.ThemeIcon(
                          DashIconify(icon="bi:activity"),
                          variant="light",
                          color=status_color,
                      ),
                      dmc.Text(
                          "Status",
                          c="dimmed",
                          size="xs",
                          tt="uppercase",
                          fw=700,
                      ),
                  ]),
                  dmc.Text(trial.status.value, fw=700, size="lg", mt="sm"),
                  failed_at_text,
              ],
          ),
          dmc.Paper(
              p="md",
              radius="md",
              withBorder=True,
              children=[
                  dmc.Group([
                      dmc.ThemeIcon(
                          DashIconify(icon="bi:stopwatch"),
                          variant="light",
                          color="blue",
                      ),
                      dmc.Text(
                          "Duration",
                          c="dimmed",
                          size="xs",
                          tt="uppercase",
                          fw=700,
                      ),
                  ]),
                  dmc.Text(f"{duration_ms} ms", fw=700, size="lg", mt="sm"),
              ],
          ),
          dmc.Paper(
              p="md",
              radius="md",
              withBorder=True,
              children=[
                  dmc.Group([
                      dmc.ThemeIcon(
                          DashIconify(icon="bi:lightning-charge"),
                          variant="light",
                          color="cyan",
                      ),
                      dmc.Text(
                          "TTFR",
                          c="dimmed",
                          size="xs",
                          tt="uppercase",
                          fw=700,
                      ),
                  ]),
                  dmc.Text(f"{ttfr_ms} ms", fw=700, size="lg", mt="sm"),
              ],
          ),
          dmc.Paper(
              p="md",
              radius="md",
              withBorder=True,
              children=[
                  dmc.Group([
                      dmc.ThemeIcon(
                          DashIconify(icon="bi:trophy-fill", width=18),
                          variant="light",
                          color="yellow",
                      ),
                      dmc.Text(
                          "Accuracy",
                          c="dimmed",
                          size="xs",
                          tt="uppercase",
                          fw=700,
                      ),
                  ]),
                  dmc.Text(
                      f"{trial.score * 100:.1f}%"
                      if trial.score is not None
                      else "N/A",
                      fw=700,
                      size="lg",
                      mt="sm",
                  ),
              ],
          ),
      ],
      mb="xl",
  )

  # --- Assertion Cards ---
  # Get all possible types for the filter
  unique_types = sorted(list({item["type"] for item in assertion_details}))
  type_options = [{"label": "All Types", "value": "all"}]
  for ut in unique_types:
    style = test_case_components.get_assertion_style(ut)
    type_options.append({"label": style["label"], "value": ut})

  # --- Assertions Section ---
  if trial.status == RunStatus.FAILED:
    render_assertions = dmc.Alert(
        "Assertions were not evaluated because the trial failed.",
        color="gray",
        variant="light",
        radius="md",
        icon=DashIconify(icon="bi:info-circle"),
    )
    assertions_header = dmc.Group(
        [
            dmc.Text("Assertions", fw=700, size="xl"),
            dmc.Badge(
                "Not Evaluated",
                variant="light",
                color="gray",
                size="xs",
                radius="sm",
            ),
        ],
        gap="sm",
        mb="md",
    )
  else:
    # Get all possible types for the filter
    unique_types = sorted(list({item["type"] for item in assertion_details}))
    type_options = [{"label": "All Types", "value": "all"}]
    for ut in unique_types:
      style = test_case_components.get_assertion_style(ut)
      type_options.append({"label": style["label"], "value": ut})

    assertion_cards = []
    for item in assertion_details:
      weight = item["weight"]
      category = "Accuracy" if weight > 0 else "Diagnostic"
      a_type = item["type"]

      if filter_cat != "all" and category.lower() != filter_cat:
        continue
      if filter_stat != "all":
        item_passed = item.get("passed", False)
        if filter_stat == "passed" and not item_passed:
          continue
        if filter_stat == "failed" and item_passed:
          continue
      if filter_type != "all" and a_type != filter_type:
        continue

      assertion_cards.append(item)

    render_assertions = (
        assertion_components.render_assertion_results_table(assertion_cards)
        if assertion_cards
        else assertion_components.render_assertion_empty()
    )

    assertions_header = dmc.Group(
        [
            dmc.Group(
                [
                    dmc.Text(
                        "Assertions",
                        fw=700,
                        size="xl",
                    ),
                    dmc.Badge(
                        f"{len(assertion_details)} Total",
                        variant="light",
                        color="gray",
                        size="xs",
                        radius="sm",
                    ),
                    dmc.Group(
                        gap="xs",
                        children=test_case_components.render_assertion_badges(
                            [ar.assertion for ar in trial.assertion_results]
                            if trial.assertion_results
                            else []
                        ),
                    ),
                ],
                gap="sm",
            ),
            dmc.Group(
                gap="xs",
                children=[
                    dmc.Select(
                        id=(EvaluationIds.ASSERT_FILTER_STATUS),
                        value=filter_stat,
                        data=[
                            {
                                "label": "All Statuses",
                                "value": "all",
                            },
                            {
                                "label": "Passed",
                                "value": "passed",
                            },
                            {
                                "label": "Failed",
                                "value": "failed",
                            },
                        ],
                        size="xs",
                        w=120,
                    ),
                    dmc.Select(
                        id=(EvaluationIds.ASSERT_FILTER_CATEGORY),
                        value=filter_cat,
                        data=[
                            {
                                "label": "All Categories",
                                "value": "all",
                            },
                            {
                                "label": "Accuracy",
                                "value": "accuracy",
                            },
                            {
                                "label": "Diagnostic",
                                "value": "diagnostic",
                            },
                        ],
                        size="xs",
                        w=130,
                    ),
                    dmc.Select(
                        id=EvaluationIds.ASSERT_FILTER_TYPE,
                        value=filter_type,
                        data=type_options,
                        size="xs",
                        w=160,
                    ),
                ],
            ),
        ],
        justify="space-between",
        mb="md",
    )

  # --- Suggestions Section ---
  accordion_style = {}
  if trial.status == RunStatus.FAILED:
    accordion_style = {"display": "none"}
    suggestions_content = dash.no_update
  elif sug_loading:
    logging.warning("!!! CALLBACK: sug_loading is True, returning skeleton")
    suggestions_content = assertion_components.render_suggestion_skeleton()
  else:
    suggestion_cards = []
    if trial.suggested_asserts:
      for i, sa in enumerate(trial.suggested_asserts):
        try:
          item = sa.model_dump()
          card = assertion_components.render_suggested_assertion_card(
              item, item.get("id") or i, ids_class=EvaluationIds
          )
          suggestion_cards.append(card)
        except Exception as e:  # pylint: disable=broad-exception-caught
          logging.error("Failed to render suggestion card %d: %s", i, e)
          logging.error(traceback.format_exc())

    if not suggestion_cards:
      logging.warning("!!! CALLBACK: No suggestion cards rendered")
      suggestions_content = assertion_components.render_empty_suggestions(
          {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": "empty"}
      )
    else:
      logging.warning(
          "!!! CALLBACK: Returning %d suggestion cards", len(suggestion_cards)
      )
      suggestions_content = dmc.SimpleGrid(
          cols=2, spacing="lg", children=suggestion_cards
      )

  # Layout
  header_actions = [
      dmc.Anchor(
          dmc.Button(
              "View Trace",
              leftSection=DashIconify(icon="bi:receipt"),
              variant="default",
              radius="md",
              fw=600,
          ),
          href=f"/evaluations/trials/{trial.id}/trace",
      ),
  ]

  description = [
      "Execution results for agent ",
      html.Span(
          run.agent_name or "Unknown Agent",
          style={"fontWeight": 600},
          className="text-dark",
      ),
      " on test suite ",
      html.Span(
          run.suite_name or "Unknown Suite",
          style={"fontWeight": 600},
          className="text-dark",
      ),
  ]

  return [
      breadcrumbs,
      f"Trial #{trial.id}",
      description,
      header_actions,
      dmc.Stack([
          # Summary Stats
          stats_cards,
          # Error Card (Visible only if FAILED)
          error_card,
          # Trial Results Card with Integrated Charts
          run_components.render_trial_card(
              trial,
              show_details_link=False,
              suite_link=run_link,
              chart_section=timeline.render_chart_carousel(
                  timeline_obj.model_dump(), minimal=True
              ),
          ),
          # Two-column layout: Assertions+Suggestions (Left) vs Timeline (Right)
          dmc.Grid(
              gutter="md",
              mt="md",
              children=[
                  # Left Column: Assertions & Suggestions
                  dmc.GridCol(
                      span=12,
                      children=dmc.Stack([
                          # Assertions Section
                          dmc.Box([
                              assertions_header,
                              # Assertion Metrics Visualizations
                              (
                                  assertion_components.render_assertion_summary(
                                      _calculate_assertion_summary(
                                          assertion_details
                                      )
                                  )
                                  if trial.status != RunStatus.FAILED
                                  else None
                              ),
                              dmc.Space(h="lg"),
                              render_assertions,
                          ]),
                      ]),
                  ),
              ],
          ),
      ]),
      suggestions_content,
      accordion_style,
  ]


@typed_callback(
    dash.Output("url", "search", allow_duplicate=True),
    inputs=[
        dash.Input(EvaluationIds.ASSERT_FILTER_CATEGORY, "value"),
        dash.Input(EvaluationIds.ASSERT_FILTER_TYPE, "value"),
        dash.Input(EvaluationIds.ASSERT_FILTER_STATUS, "value"),
    ],
    state=[dash.State("url", "search")],
    prevent_initial_call=True,
)
def sync_assertion_filter_to_url(cat_val, type_val, stat_val, current_search):
  """Syncs assertion filters back to the URL."""
  params = (
      urllib.parse.parse_qs(current_search.lstrip("?"))
      if current_search
      else {}
  )

  new_cat = cat_val or "all"
  new_type = type_val or "all"
  new_stat = stat_val or "all"

  # Avoid redundant updates causing loops
  if (
      params.get("assertion_category") == [new_cat]
      and params.get("assertion_type") == [new_type]
      and params.get("assertion_status") == [new_stat]
  ):
    return dash.no_update

  params["assertion_category"] = [new_cat]
  params["assertion_type"] = [new_type]
  params["assertion_status"] = [new_stat]
  return "?" + urllib.parse.urlencode(params, doseq=True)


@typed_callback(
    [
        dash.Output(EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL, CP.DATA),
        dash.Output(
            "notification-container", "sendNotifications", allow_duplicate=True
        ),
    ],
    inputs=[
        (
            {"type": EvaluationIds.INLINE_SUG_ADD_BTN, "index": dash.ALL},
            CP.N_CLICKS,
        ),
        (
            {"type": EvaluationIds.INLINE_SUG_REJECT_BTN, "index": dash.ALL},
            CP.N_CLICKS,
        ),
    ],
    prevent_initial_call=True,
)
@handle_errors
def curate_trial_suggestion(accept_clicks, reject_clicks):
  """Handles accepting or rejecting a suggested assertion."""
  # pylint: disable=unused-argument
  ctx = dash.callback_context
  if not ctx.triggered:
    return dash.no_update, dash.no_update

  # Guard: Ensure it was an actual click (n_clicks > 0), not just registration
  trigger_val = ctx.triggered[0].get("value")
  if not trigger_val:
    return dash.no_update, dash.no_update

  trigger = typed_callback.triggered_id()
  if not trigger or not isinstance(trigger, dict):
    logging.warning("Invalid trigger for curate_trial_suggestion: %s", trigger)
    return dash.no_update, dash.no_update

  sug_id = trigger.get("index")
  if sug_id is None:
    return dash.no_update, dash.no_update

  action = (
      "accept"
      if trigger["type"] == EvaluationIds.INLINE_SUG_ADD_BTN
      else "reject"
  )

  client = get_client()
  client.runs.curate_suggestion(int(sug_id), action)

  return time.time(), [{
      "action": "show",
      "title": "Suggestion Updated",
      "message": f"The suggested assertion was {action}ed.",
      "color": "grape" if action == "accept" else "gray",
      "icon": DashIconify(
          icon="bi:check" if action == "accept" else "bi:x-circle"
      ),
  }]


@typed_callback(
    dash.Output(
        EvaluationIds.TRIAL_SUG_LOADING_STORE, CP.DATA, allow_duplicate=True
    ),
    inputs=[dash.Input("url", CP.PATHNAME)],
    prevent_initial_call=True,
)
def reset_trial_suggestions_state(pathname):
  """Resets the loading state when navigating to a new trial."""
  logging.warning(
      "!!! CALLBACK: reset_trial_suggestions_state pathname=%s", pathname
  )
  return False


dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && n_clicks.some(c => c > 0)) {
            return [n_clicks.map(() => true), true];
        }
        return [window.dash_clientside.no_update, window.dash_clientside.no_update];
    }
    """,
    [
        dash.Output(
            {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": dash.ALL},
            "loading",
        ),
        dash.Output(EvaluationIds.TRIAL_SUG_LOADING_STORE, "data"),
    ],
    [
        dash.Input(
            {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": dash.ALL},
            CP.N_CLICKS,
        ),
    ],
    prevent_initial_call=True,
)


@typed_callback(
    [
        dash.Output(
            EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL, CP.DATA, allow_duplicate=True
        ),
        dash.Output(
            {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": dash.ALL},
            "loading",
            allow_duplicate=True,
        ),
        dash.Output(
            EvaluationIds.TRIAL_SUG_LOADING_STORE, "data", allow_duplicate=True
        ),
        dash.Output(
            EvaluationIds.TRIAL_SUG_POLLING_INTERVAL,
            "disabled",
            allow_duplicate=True,
        ),
    ],
    inputs=[
        dash.Input(
            {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": dash.ALL},
            CP.N_CLICKS,
        ),
    ],
    state=[
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
)
@handle_errors
def trigger_suggestion_generation(
    n_clicks_list: list[int | None], pathname: str
):
  """Triggers regeneration of suggested assertions."""
  if (
      not n_clicks_list
      or not any(n_clicks_list)
      or not pathname
      or not pathname.startswith("/evaluations/trials/")
  ):
    return dash.no_update

  try:
    trial_id = int(pathname.split("/")[-1])
  except ValueError:
    return dash.no_update

  logging.info("Starting suggestion regeneration for trial %s", trial_id)
  app = flask.current_app._get_current_object()  # pylint: disable=protected-access,no-member
  client = get_client()
  client.runs.regenerate_suggestions_async(trial_id, app)
  logging.info("Triggered suggestion regeneration for trial %s", trial_id)

  return time.time(), [True] * len(n_clicks_list), True, False


@typed_callback(
    [
        dash.Output(
            EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL, CP.DATA, allow_duplicate=True
        ),
        dash.Output(
            {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": dash.ALL},
            "loading",
            allow_duplicate=True,
        ),
        dash.Output(
            EvaluationIds.TRIAL_SUG_LOADING_STORE, "data", allow_duplicate=True
        ),
        dash.Output(
            EvaluationIds.TRIAL_SUG_POLLING_INTERVAL,
            "disabled",
            allow_duplicate=True,
        ),
    ],
    inputs=[
        dash.Input(EvaluationIds.TRIAL_SUG_POLLING_INTERVAL, "n_intervals")
    ],
    state=[
        dash.State("url", CP.PATHNAME),
        dash.State(
            {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": dash.ALL}, "id"
        ),
    ],
    prevent_initial_call=True,
)
@handle_errors
def poll_suggestion_results(
    n_intervals, pathname, btn_ids: list[dict[str, Any]]
):
  """Polls for suggestion results and updates the UI when ready."""
  if (
      not n_intervals
      or not pathname
      or not pathname.startswith("/evaluations/trials/")
  ):
    return dash.no_update

  try:
    trial_id = int(pathname.split("/")[-1])
  except ValueError:
    return dash.no_update

  client = get_client()
  try:
    trial = client.runs.get_trial(trial_id)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logging.error("Polling failed for trial %s: %s", trial_id, e)
    # Stop polling on error to avoid infinite loop of crashes
    return typed_callback.no_update, [False] * len(btn_ids), False, True

  sug_count = (
      len(trial.suggested_asserts) if trial and trial.suggested_asserts else 0
  )
  logging.info(
      "Polling suggestions for trial %s: count=%s", trial_id, sug_count
  )

  # If suggestions arrived, stop polling and refresh
  if trial and trial.suggested_asserts:
    logging.info(
        "Suggestions arrived for trial %s, stopping polling with signal",
        trial_id,
    )
    return time.time(), [False] * len(btn_ids), False, True

  # Stop polling after ~60 seconds (20 intervals * 3s)
  if n_intervals >= 20:
    logging.info("Suggestions polling timed out for trial %s", trial_id)
    return typed_callback.no_update, [False] * len(btn_ids), False, True

  return (
      typed_callback.no_update,
      [dash.no_update] * len(btn_ids),
      dash.no_update,
      dash.no_update,
  )


# --- Test Suite View Run Modal ---


@typed_callback(
    [
        (EvaluationIds.MODAL_RUN_EVAL, "opened"),
        (EvaluationIds.AGENT_SELECT, "data"),
    ],
    inputs=[
        (EvaluationIds.BTN_OPEN_RUN_MODAL, "n_clicks"),
        (EvaluationIds.BTN_CANCEL_RUN, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def toggle_run_eval_modal(open_clicks, cancel_clicks):
  """Toggles the Run Evaluation modal and populates Agent Select."""
  del open_clicks, cancel_clicks
  trigger = typed_callback.triggered_id()

  if trigger == EvaluationIds.BTN_OPEN_RUN_MODAL:
    client = get_client()
    agents = client.agents.list_agents()
    options = [
        {"label": a.name or f"Agent {a.id}", "value": str(a.id)} for a in agents
    ]
    return True, options

  return False, dash.no_update


@typed_callback(
    [
        dash.Output(REDIRECT_HANDLER, CP.HREF),
        dash.Output(
            "notification-container", "sendNotifications", allow_duplicate=True
        ),
    ],
    inputs=[(EvaluationIds.BTN_START_RUN, "n_clicks")],
    state=[
        (EvaluationIds.AGENT_SELECT, "value"),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def start_run_eval(n_clicks, agent_id, pathname):
  """Starts a new evaluation run from the Test Suite View."""
  if not n_clicks or not agent_id:
    return dash.no_update

  # Extract Test Suite ID from URL
  if not pathname or "/test_suites/view/" not in pathname:
    return dash.no_update

  try:
    suite_id = int(pathname.split("/")[-1])
  except ValueError:
    return dash.no_update

  client = get_client()
  agent = client.agents.get_agent(int(agent_id))

  # Prevent if missing Looker credentials
  if (
      agent
      and agent.config
      and isinstance(agent.config.datasource, agent_schemas.LookerConfig)
  ):
    if (
        not agent.config.looker_client_id
        or not agent.config.looker_client_secret
    ):
      return dash.no_update, [{
          "action": "show",
          "title": "Cannot Start Evaluation",
          "message": (
              f"Agent '{agent.name}' is a Looker agent, but it is missing"
              " credentials. Please provide them in the Edit Agent modal"
              " before starting evaluations."
          ),
          "color": "red",
          "icon": DashIconify(icon="material-symbols:error-outline"),
      }]

  # Captures real app for thread
  app = flask.current_app._get_current_object()  # pylint: disable=protected-access,no-member

  run = client.runs.create_run(
      agent_id=int(agent_id),
      test_suite_id=suite_id,
  )
  run_id = run.id

  # Start Background Thread
  client.runs.execute_run_async(run_id, app)

  # Redirect
  return f"/evaluations/runs/{run_id}", dash.no_update


# --- Global New Evaluation (from List Page) ---


@typed_callback(
    output=[
        dash.Output(EvaluationIds.MODAL_NEW_EVAL, "opened"),
        dash.Output(EvaluationIds.NEW_EVAL_AGENT_SELECT, "data"),
        dash.Output(EvaluationIds.NEW_EVAL_SUITE_SELECT, "data"),
    ],
    inputs=[
        dash.Input(EvaluationIds.BTN_NEW_EVAL, "n_clicks"),
        dash.Input(EvaluationIds.BTN_CANCEL_NEW_EVAL, "n_clicks"),
    ],
    prevent_initial_call=True,
)
def toggle_new_eval_modal(open_clicks, cancel_clicks):
  """Toggles the 'New Evaluation' modal and populates selects."""
  del open_clicks, cancel_clicks
  trigger = typed_callback.triggered_id()

  if trigger != EvaluationIds.BTN_NEW_EVAL:
    return False, typed_callback.no_update, dash.no_update

  client = get_client()
  agents = client.agents.list_agents()
  agent_opts = [
      {"label": a.name or f"Agent {a.id}", "value": str(a.id)} for a in agents
  ]

  suites = client.suites.list_suites()
  suite_opts = [{"label": s.name, "value": str(s.id)} for s in suites]

  return True, agent_opts, suite_opts


@typed_callback(
    output=[
        dash.Output(REDIRECT_HANDLER, "href", allow_duplicate=True),
        dash.Output(
            "notification-container", "sendNotifications", allow_duplicate=True
        ),
    ],
    inputs=[dash.Input(EvaluationIds.BTN_START_NEW_EVAL, "n_clicks")],
    state=[
        dash.State(EvaluationIds.NEW_EVAL_AGENT_SELECT, "value"),
        dash.State(EvaluationIds.NEW_EVAL_SUITE_SELECT, "value"),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def start_new_eval(n_clicks, agent_id, suite_id):
  """Starts a new evaluation run from the Global Modal."""
  if not n_clicks or not agent_id or not suite_id:
    return dash.no_update

  client = get_client()
  agent = client.agents.get_agent(int(agent_id))

  # Prevent if missing Looker credentials
  if (
      agent
      and agent.config
      and isinstance(agent.config.datasource, agent_schemas.LookerConfig)
  ):
    if (
        not agent.config.looker_client_id
        or not agent.config.looker_client_secret
    ):
      return dash.no_update, [{
          "action": "show",
          "title": "Cannot Start Evaluation",
          "message": (
              f"Agent '{agent.name}' is a Looker agent, but it is missing"
              " credentials. Please provide them in the Edit Agent modal"
              " before starting evaluations."
          ),
          "color": "red",
          "icon": DashIconify(icon="material-symbols:error-outline"),
      }]

  # Captures real app for thread
  app = flask.current_app._get_current_object()  # pylint: disable=protected-access,no-member

  run = client.runs.create_run(
      agent_id=int(agent_id),
      test_suite_id=int(suite_id),
  )
  run_id = run.id

  # Start Background Thread via Client
  client.runs.execute_run_async(run_id, app)

  # Redirect
  return f"/evaluations/runs/{run_id}", dash.no_update


@typed_callback(
    [
        (EvaluationIds.TRIAL_SUG_EDIT_VALUE, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_EDIT_YAML, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_EDIT_GUIDE_CONTAINER, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_EDIT_GUIDE_TITLE, CP.CHILDREN),
        (EvaluationIds.TRIAL_SUG_EDIT_GUIDE_DESC, CP.CHILDREN),
        (EvaluationIds.TRIAL_SUG_EDIT_EXAMPLE_VALUE, CP.VALUE),
        (EvaluationIds.TRIAL_SUG_EDIT_EXAMPLE_YAML, CP.VALUE),
        (EvaluationIds.TRIAL_SUG_EDIT_EXAMPLE_VALUE, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_EDIT_EXAMPLE_YAML, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_EDIT_EXAMPLE_CONTAINER, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_EDIT_CHART_TYPE, CP.STYLE),
        (EvaluationIds.TRIAL_SUG_VAL_MSG, CP.STYLE),
    ],
    inputs=[(EvaluationIds.TRIAL_SUG_EDIT_TYPE, CP.VALUE)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def update_trial_suggestion_edit_ui(assert_type: str | None):
  """Updates visibility and description for Trial Suggestion Edit Modal."""
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
        {"display": "none"},
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
  )


@typed_callback(
    dash.Output(EvaluationIds.RUN_UPDATE_SIGNAL, CP.DATA),
    inputs=[
        (EvaluationIds.BTN_PAUSE_RUN, CP.N_CLICKS),
        (EvaluationIds.BTN_RESUME_RUN, CP.N_CLICKS),
        (EvaluationIds.BTN_CANCEL_RUN_EXEC, CP.N_CLICKS),
    ],
    state=[("url", CP.PATHNAME)],
    prevent_initial_call=True,
)
@handle_errors
def handle_run_controls(pause_clicks, resume_clicks, cancel_clicks, pathname):
  """Handles Pause/Resume/Cancel button clicks."""
  # pylint: disable=unused-argument
  if not pathname or not pathname.startswith("/evaluations/runs/"):
    return dash.no_update

  try:
    run_id = int(pathname.rstrip("/").split("/")[-1])
  except ValueError:
    return dash.no_update

  trigger = typed_callback.triggered_id()
  client = get_client()

  if trigger == EvaluationIds.BTN_PAUSE_RUN:
    client.runs.pause_run(run_id)
  elif trigger == EvaluationIds.BTN_RESUME_RUN:
    client.runs.resume_run(run_id)
  elif trigger == EvaluationIds.BTN_CANCEL_RUN_EXEC:
    client.runs.cancel_run(run_id)

  return time.time()


@typed_callback(
    output=dash.Output(EvaluationIds.DOWNLOAD_DIFF_COMPONENT, "data"),
    inputs=[dash.Input(EvaluationIds.BTN_DOWNLOAD_DIFF, "n_clicks")],
    state=[
        dash.State(EvaluationIds.RUN_CONTEXT_DIFF_STORE, "data"),
        dash.State(EvaluationIds.RUN_DATA_STORE, "data"),
    ],
    prevent_initial_call=True,
)
def download_diff_context(
    n_clicks: int, diff_data: dict[str, Any], run_data: dict[str, Any]
):
  """Downloads the unified diff as a text file."""
  if not n_clicks or not diff_data or not diff_data.get("live"):
    return dash.no_update

  diff_text = run_components.generate_text_diff(
      diff_data.get("snapshot", {}), diff_data.get("live", {})
  )

  run_id = run_data.get("run", {}).get("id", "unknown")
  filename = f"context_diff_run_{run_id}.txt"

  return dash.dcc.send_string(diff_text, filename=filename)
