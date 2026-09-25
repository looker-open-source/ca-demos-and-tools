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
from prism.ui.components import assertion_components
from prism.ui.components import cards
from prism.ui.components import charts
from prism.ui.components import run_components
from prism.ui.components import tables
from prism.ui.components import test_case_components
from prism.ui.components import timeline
from prism.ui.constants import CP
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
from prism.ui.models.ui_state import AssertionMetric
from prism.ui.models.ui_state import AssertionSummary
from prism.ui.models.ui_state import RunDetailPageState
from prism.ui.utils import format_duration
from prism.ui.utils import format_timestamp
from prism.ui.utils import format_ttfr
from prism.ui.utils import id_from_pathname
from prism.ui.utils import run_status_display
from prism.ui.utils import typed_callback

logger = logging.getLogger(__name__)

# How many runs /evaluations shows. There is no pager, so past this the older
# runs are only reachable through the filters. One row more than this is
# fetched, which is how the page knows whether to say it is truncated.
_RUN_LIST_LIMIT = 50


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

  parsed_qs = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
  agent_id = parsed_qs.get("agent_id", [None])[0]
  suite_id = parsed_qs.get("suite_id", [None])[0]
  status = parsed_qs.get("status", [None])[0]

  agent_id = int(agent_id) if agent_id else None
  suite_id = int(suite_id) if suite_id else None
  status_enum = RunStatus(status) if status else None

  client = get_client()
  include_archived = parsed_qs.get("archived", ["false"])[0] == "true"
  runs = client.runs.list_runs(
      agent_id=agent_id,
      original_suite_id=suite_id,
      status=status_enum,
      include_archived=include_archived,
      limit=_RUN_LIST_LIMIT + 1,
  )

  if not runs:
    return dmc.Text("No evaluations found.", c="dimmed", ta="center", py="xl")

  truncated = len(runs) > _RUN_LIST_LIMIT
  table = tables.render_run_table(runs[:_RUN_LIST_LIMIT], table_id=None)
  if not truncated:
    return table

  # Say so. The list used to stop at 50 with nothing on the page admitting it,
  # so the 51st run read as a run that did not exist.
  return html.Div([
      table,
      dmc.Text(
          f"Showing the {_RUN_LIST_LIMIT} most recent runs. Filter by agent,"
          " test suite or status to reach older ones.",
          c="dimmed",
          size="sm",
          ta="center",
          py="md",
      ),
  ])


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

  return f"?{urllib.parse.urlencode(params, doseq=True)}" if params else ""


@typed_callback(
    dash.Output("url", "search", allow_duplicate=True),
    inputs=[
        (EvaluationIds.SWITCH_ARCHIVED, CP.CHECKED),
    ],
    state=[("url", CP.SEARCH)],
    prevent_initial_call=True,
)
def update_eval_url_from_archived_switch(
    include_archived: bool, current_search: str
):
  """Update URL search params from Evaluations Home archived switch."""
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
    output=[
        (EvaluationIds.FILTER_AGENT, CP.VALUE),
        (EvaluationIds.FILTER_SUITE, CP.VALUE),
        (EvaluationIds.FILTER_STATUS, CP.VALUE),
        (EvaluationIds.SWITCH_ARCHIVED, CP.CHECKED),
    ],
    inputs=[("url", CP.SEARCH)],
)
def sync_eval_filters_to_url(search: str):
  """Sync UI filters to URL search params on load/change."""
  if not search:
    return None, None, None, False

  params = urllib.parse.parse_qs(search.lstrip("?"))
  agent_id = params.get("agent_id", [None])[0]
  suite_id = params.get("suite_id", [None])[0]
  status = params.get("status", [None])[0]
  include_archived = params.get("archived", ["false"])[0] == "true"

  return agent_id, suite_id, status, include_archived


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

  suites = client.runs.get_unique_suites_from_snapshots()
  suite_data = [
      {"label": s["name"], "value": str(s["original_suite_id"])} for s in suites
  ]

  return agent_data, suite_data


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

  if triggered_id == EvaluationIds.BTN_CANCEL_COMPARE:
    return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update

  # The open buttons are pattern-matched, so this also fires when the run list
  # re-renders and the new buttons arrive with n_clicks unset. Only a trigger
  # that carries a value is a real click.
  is_open_click = False
  for t in ctx.triggered:
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

  # The button in a run's row carries that run's id as its index. The one in
  # the page header uses "list" and preselects nothing.
  preselect_run_id = None
  t_id: Any = getattr(ctx, "triggered_id", None)
  if t_id and isinstance(t_id, dict):
    idx = str(t_id.get("index", ""))
    if idx != "list":
      preselect_run_id = idx

  client = get_client()

  # Only runs of the same test suite can be compared, so the list is filtered
  # to the preselected run's suite.
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
        format_timestamp(r.created_at) if r.created_at else "Unknown Date"
    )
    accuracy = r.accuracy
    acc_str = f"{accuracy*100:.1f}%" if accuracy is not None else "N/A"

    label = f"Run #{r.id} • {agent_name} • {date_str} • Acc: {acc_str}"
    data.append({"value": str(r.id), "label": label})

  base_val = None
  chal_val = preselect_run_id if preselect_run_id else None

  # The challengers are the runs of the base run's suite, and from the header
  # button there is no base run yet, so there are none to offer. Listing every
  # run instead let a cross-suite pair be picked before the base was set, and
  # compare_runs rejects that pair with an alert. filter_challenger_runs fills
  # this in as soon as a base is chosen.
  challenger_data = data if preselect_run_id else []

  return True, data, challenger_data, base_val, chal_val


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
    output=[
        dash.Output(
            EvaluationIds.COMPARE_CHALLENGE_SELECT,
            "data",
            allow_duplicate=True,
        ),
        dash.Output(
            EvaluationIds.COMPARE_CHALLENGE_SELECT,
            "value",
            allow_duplicate=True,
        ),
    ],
    inputs=[dash.Input(EvaluationIds.COMPARE_BASE_SELECT, "value")],
    state=[dash.State(EvaluationIds.COMPARE_CHALLENGE_SELECT, "value")],
    prevent_initial_call=True,
)
def filter_challenger_runs(
    base_run_id: str | None, chal_run_id: str | None
) -> tuple[Any, Any]:
  """Filters the challengers to the test suite of the selected base run."""
  if not base_run_id:
    return dash.no_update, dash.no_update

  client = get_client()
  base_run = client.runs.get_run(int(base_run_id))
  if not base_run:
    return dash.no_update, dash.no_update

  runs = client.runs.list_runs(original_suite_id=base_run.original_suite_id)
  data = []
  for r in runs:
    agent_name = r.agent_name or "Unknown Agent"
    date_str = (
        format_timestamp(r.created_at) if r.created_at else "Unknown Date"
    )
    accuracy = r.accuracy
    acc_str = f"{accuracy*100:.1f}%" if accuracy is not None else "N/A"

    label = f"Run #{r.id} • {agent_name} • {date_str} • Acc: {acc_str}"
    data.append({"value": str(r.id), "label": label})

  # The value goes with the data. This rewrote the options and left the
  # challenger set to a run from the old suite: the field renders blank because
  # the value is not in the data, the Compare button stays enabled, and
  # navigate_to_comparison reads that value as State. Clicking it compared two
  # runs of different suites, which reads like two identical runs rather than a
  # mis-selection.
  if chal_run_id and not any(o["value"] == str(chal_run_id) for o in data):
    return data, None

  return data, dash.no_update


def render_assertion_performance(trials: list[Trial]) -> dmc.Paper | None:
  """Renders a horizontal bar chart of pass rates by assertion type."""
  # Map assertion type to [passed_count, total_count]
  counts: dict[str, list[int]] = {}

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
      type_name = name_map.get(type_val, type_val.replace("-", " ").title())

      if type_name not in counts:
        counts[type_name] = [0, 0]
      counts[type_name][1] += 1
      if ar.passed:
        counts[type_name][0] += 1

  chart_data = []
  for type_name, vals in counts.items():
    pass_rate = (vals[0] / vals[1] * 100) if vals[1] > 0 else 0
    chart_data.append({
        "type": type_name,
        "pass_rate": round(pass_rate, 1),
        "total": vals[1],
        "label": f"{type_name} ({vals[0]}/{vals[1]})",
    })

  # Worst pass rate first, so the problem types are at the top of the chart.
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


@typed_callback(
    output=dash.Output(EvaluationIds.RUN_DATA_STORE, CP.DATA),
    inputs=[
        ("url", CP.PATHNAME),
        (EvaluationIds.RUN_POLLING_INTERVAL, "n_intervals"),
        (EvaluationIds.RUN_UPDATE_SIGNAL, CP.DATA),
    ],
)
def fetch_run_detail_data(
    pathname: str, unused_n_intervals: int, unused_update_signal: Any
):
  """Fetches and stores data for the Run Detail page."""
  logger.info("fetch_run_detail_data started: %s", pathname)
  if not pathname or not pathname.startswith("/evaluations/runs/"):
    return dash.no_update

  try:
    run_id = id_from_pathname(pathname)
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
        (EvaluationIds.RUN_BIGQUERY_BADGE, CP.CHILDREN),
        (EvaluationIds.BTN_PAUSE_RUN, CP.STYLE),
        (EvaluationIds.BTN_RESUME_RUN, CP.STYLE),
        (EvaluationIds.BTN_CANCEL_RUN_EXEC, CP.STYLE),
        (EvaluationIds.BTN_SYNC_BIGQUERY, CP.STYLE),
        (EvaluationIds.BTN_ARCHIVE, CP.STYLE),
        (EvaluationIds.BTN_RESTORE, CP.STYLE),
        (EvaluationIds.RUN_POLLING_INTERVAL, CP.DISABLED),
        (EvaluationIds.RUN_CONTEXT_TRIGGER, CP.DATA),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_DATA_STORE, CP.DATA)],
    state=[dash.State(EvaluationIds.RUN_CONTEXT_TRIGGER, CP.DATA)],
)
def render_run_detail_components(
    run_data: dict[str, Any], current_trigger_id: int | None
):
  """Renders the components for the Run Detail page."""
  logger.info("render_run_detail_components triggered")
  if not run_data:
    return [dash.no_update] * 15

  state = RunDetailPageState.model_validate(run_data)

  run = state.run
  trials = state.trials
  run_id = run.id

  # The polling interval re-runs this every few seconds. Re-triggering the
  # context fetch each time would repeat the slow GDA call for the same run.
  context_trigger = run_id if current_trigger_id != run_id else dash.no_update

  # Straight from Run.accuracy, not recomputed here. The rule is fiddly (a
  # FAILED trial scores 0 instead of dropping out of the denominator; a
  # COMPLETED one with no weighted assertions does drop out) and writing it
  # twice is how this card came to disagree with the run list.
  avg_accuracy = None if run.accuracy is None else run.accuracy * 100

  durations = []
  for t in trials:
    # Only trials that have run. Appending 0 for the pending ones and then
    # dividing by the total made this the average over the whole run instead
    # of over the finished part: 2 of 10 done at 20s each read 4.00s, and the
    # card repolls every 3s, so it crept up all the way through the run.
    if t.duration_ms:
      durations.append(t.duration_ms)

  # The badge reads off the shared map, like every other status badge. It used
  # to hold its own colours and render run.status.value, so the run the list
  # called "In Progress" called itself "RUNNING" on its own page, and a paused
  # run was orange here and yellow everywhere else.
  badge_color, badge_label = run_status_display(run.status)
  show_pause = {"display": "none"}
  show_resume = {"display": "none"}
  show_cancel = {"display": "none"}
  show_archive = {"display": "none"}
  show_restore = {"display": "none"}
  polling_disabled = True

  if run.status in (
      RunStatus.RUNNING,
      RunStatus.PENDING,
      RunStatus.EXECUTING,
      RunStatus.EVALUATING,
  ):
    show_pause = {"display": "block"}
    show_cancel = {"display": "block"}
    polling_disabled = False
  elif run.status == RunStatus.PAUSED:
    show_resume = {"display": "block"}
    show_cancel = {"display": "block"}
    polling_disabled = False

  if run.is_archived:
    show_restore = {"display": "block"}
  else:
    show_archive = {"display": "block"}

  breadcrumbs = dmc.Breadcrumbs(
      separator="/",
      mb="lg",
      children=[
          dmc.Anchor("Evaluations", href="/evaluations", size="sm", fw=500),
          dmc.Text(f"Run #{run_id}", size="sm", fw=500, c="dimmed"),
      ],
  )

  avg_duration = (sum(durations) / len(durations)) if durations else 0.0
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

  context_card = run_components.render_run_context(
      run.agent_context_snapshot, loading=False
  )

  timing_chart = charts.render_tool_timing_chart(
      run.tool_timings or {}, title="Aggregate Tool Timing"
  )

  charts_grid = dmc.SimpleGrid(
      cols={"base": 1, "lg": 3},
      spacing="xl",
      children=[
          context_card,
          assertion_update
          or dmc.Alert(
              "No assertion data available for this run.",
              color="gray",
              variant="light",
          ),
          timing_chart,
      ],
  )

  # Only ask BigQuery about a run that could be in it. Export is triggered when
  # a run reaches COMPLETED (see worker.py), and this page polls every three
  # seconds for as long as the run has not reached it (see polling_disabled
  # above). Checking on each of those ticks bills a query job to be told "no",
  # which is the only answer possible until the run finishes. The local flags
  # below are free and just as accurate.
  client = get_client()
  bq_status = client.runs.get_bigquery_export_status(
      run_id, check_exported=run.status == RunStatus.COMPLETED
  )
  if not bq_status.get("enabled"):
    bq_badge = dmc.Tooltip(
        label="BigQuery export disabled (set BIGQUERY_EXPORT_ENABLED=true)",
        children=dmc.Badge(
            "BQ: Disabled",
            color="gray",
            variant="outline",
            size="md",
            radius="md",
            leftSection=DashIconify(
                icon="material-symbols:cloud-off", width=14
            ),
        ),
    )
  # Read before the failed flag. "We could not find out" is not "the export
  # failed": a database blip while reading the recorded error used to come back
  # as a failure and paint a healthy export red, with a Sync button offering to
  # redo work that was already done.
  elif bq_status.get("status") == "unknown":
    bq_badge = dmc.Tooltip(
        label=(
            "Could not read the BigQuery export status for this run. Nothing"
            " here says the export failed. Reload to ask again."
        ),
        children=dmc.Badge(
            "BQ: Unknown",
            color="gray",
            variant="outline",
            size="md",
            radius="md",
            leftSection=DashIconify(
                icon="material-symbols:help-outline", width=14
            ),
        ),
    )
  # The failed flag is read before the exported one. An export writes four
  # tables and a partial failure still lands the runs row, so both flags are
  # set and the green badge used to win. The rejected rows are the thing worth
  # showing.
  elif bq_status.get("failed"):
    bq_badge = dmc.Tooltip(
        label=(
            f"Export failed: {bq_status.get('error') or 'Unknown error'}. "
            "Click 'Sync to BigQuery' to retry."
        ),
        children=dmc.Badge(
            "BQ: Failed",
            color="red",
            variant="light",
            size="md",
            radius="md",
            leftSection=DashIconify(
                icon="material-symbols:cloud-alert", width=14
            ),
        ),
    )
  elif bq_status.get("exported"):
    bq_badge = dmc.Tooltip(
        # No project or dataset in any of these four labels. prism has no
        # authentication, so the destination was readable by anyone who could
        # reach the port. The exporter logs it on success.
        label="Exported to BigQuery",
        children=dmc.Badge(
            "BQ: Synced",
            color="green",
            variant="light",
            size="md",
            radius="md",
            leftSection=DashIconify(
                icon="material-symbols:cloud-done", width=14
            ),
        ),
    )
  elif bq_status.get("syncing"):
    bq_badge = dmc.Tooltip(
        label="Syncing to BigQuery...",
        children=dmc.Badge(
            "BQ: Syncing",
            color="blue",
            variant="outline",
            size="md",
            radius="md",
            leftSection=dmc.Loader(size=12, color="blue"),
        ),
    )
  elif run.status == RunStatus.COMPLETED:
    # Finished, not in BigQuery, and no thread working on it. This used to share
    # the "Syncing" branch above, which put a permanent spinner on a run nothing
    # was syncing: polling is off once a run completes, so the badge could never
    # correct itself. The Sync button next to it is the actual remedy.
    bq_badge = dmc.Tooltip(
        label=(
            "Not exported to BigQuery. Click 'Sync to BigQuery' to export it."
        ),
        children=dmc.Badge(
            "BQ: Not Synced",
            color="gray",
            variant="light",
            size="md",
            radius="md",
            leftSection=DashIconify(
                icon="material-symbols:cloud-off", width=14
            ),
        ),
    )
  else:
    bq_badge = dmc.Tooltip(
        label="BigQuery export will trigger upon run completion",
        children=dmc.Badge(
            "BQ: Pending",
            color="gray",
            variant="outline",
            size="md",
            radius="md",
            leftSection=DashIconify(icon="material-symbols:schedule", width=14),
        ),
    )

  show_sync_bq = {"display": "none"}
  if (
      bq_status.get("enabled")
      and (not bq_status.get("exported") or bq_status.get("failed"))
      and run.status == RunStatus.COMPLETED
  ):
    show_sync_bq = {"display": "block"}

  return (
      breadcrumbs,
      stats,
      [charts_grid],
      trials_update,
      badge_label,
      badge_color,
      bq_badge,
      show_pause,
      show_resume,
      show_cancel,
      show_sync_bq,
      show_archive,
      show_restore,
      polling_disabled,
      context_trigger,
  )


@typed_callback(
    output=[
        (EvaluationIds.RUN_UPDATE_SIGNAL, CP.DATA),
        (NOTIFICATION_CONTAINER, "sendNotifications"),
    ],
    inputs=[
        (EvaluationIds.BTN_SYNC_BIGQUERY, CP.N_CLICKS),
    ],
    state=[dash.State(EvaluationIds.RUN_DATA_STORE, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def handle_sync_bigquery_click(n_clicks: int, run_data: dict[str, Any]):
  """Triggers BigQuery export manually from the UI."""
  if not n_clicks or not run_data:
    return dash.no_update, dash.no_update

  state = RunDetailPageState.model_validate(run_data)
  run_id = state.run.id
  client = get_client()
  try:
    client.runs.sync_run_to_bigquery(run_id, force=True)
    # NotificationContainer dispatches on "action". An entry without one
    # matches nothing and is dropped, so both of these toasts were silent.
    notification = {
        "action": "show",
        "title": "BigQuery Sync Started",
        "message": (
            f"Export for Run #{run_id} has been dispatched in the background."
        ),
        "color": "blue",
    }
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.exception("Failed manual BigQuery sync: %s", e)
    notification = {
        "action": "show",
        "title": "BigQuery Sync Failed",
        # Not the exception text. See the note in render_trial_detail.
        "message": (
            f"Could not export Run #{run_id}. The details are in the server"
            " log."
        ),
        "color": "red",
    }

  return {"timestamp": time.time(), "action": "sync_bq"}, [notification]


@typed_callback(
    output=[
        (REDIRECT_HANDLER, CP.HREF),
        (EvaluationIds.RUN_UPDATE_SIGNAL, CP.DATA),
        (NOTIFICATION_CONTAINER, "sendNotifications"),
    ],
    inputs=[
        (EvaluationIds.BTN_ARCHIVE, CP.N_CLICKS),
        (EvaluationIds.BTN_RESTORE, CP.N_CLICKS),
    ],
    state=[("url", CP.PATHNAME)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_run_archive(archive_clicks, restore_clicks, pathname):
  """Toggles archiving for an evaluation run."""
  if not archive_clicks and not restore_clicks:
    return dash.no_update, dash.no_update, dash.no_update

  try:
    run_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return dash.no_update, dash.no_update, dash.no_update

  client = get_client()
  trigger_id = typed_callback.triggered_id()

  try:
    if trigger_id == EvaluationIds.BTN_ARCHIVE:
      client.runs.archive_run(run_id)
      msg = "Evaluation run archived successfully."
    else:
      client.runs.unarchive_run(run_id)
      msg = "Evaluation run restored successfully."

    # NotificationContainer wants a list of actions. A bare dict is silently
    # ignored, which hid the success toast and the error one below.
    #
    # No href either. ``redirect-handler`` is refresh=True, so returning
    # ``pathname`` reloaded the page we are already on and threw the
    # notification away before it could be read. The update signal below
    # re-renders in place instead.
    return (
        dash.no_update,
        {"ts": time.time()},
        [{
            "action": "show",
            "title": "Success",
            "message": msg,
            "color": "green",
        }],
    )
  except ValueError as e:
    # RunRepository refuses a run that has not stopped, because an archived run
    # drops out of every worker query and the run was abandoned mid-flight. Its
    # ValueErrors are fixed text written for the reader ("Run 7 is pending.
    # Cancel it first, then archive it."), with no query or bound parameters in
    # them. Folded into the generic message below, the one refusal the user can
    # act on read as a crash, and the Cancel button that clears it is sitting
    # right next to Archive.
    return (
        dash.no_update,
        dash.no_update,
        [{
            "action": "show",
            "title": "Cannot Archive Run",
            "message": str(e),
            "color": "red",
        }],
    )
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to toggle evaluation archive: %s", e)
    return (
        dash.no_update,
        dash.no_update,
        [{
            "action": "show",
            "title": "Error",
            # Not the exception text. See the note in render_trial_detail.
            "message": (
                "Could not archive this run. The details are in the server log."
            ),
            "color": "red",
        }],
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
        (EvaluationIds.BTN_DOWNLOAD_DIFF, CP.DISABLED),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_CONTEXT_DIFF_BTN, CP.N_CLICKS)],
    state=[dash.State(EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def toggle_config_diff_modal(n_clicks: int, diff_data: dict[str, Any]):
  """Opens the config diff modal, fetching the live config if it is missing."""
  if not n_clicks or not diff_data:
    return dash.no_update, False, dash.no_update, dash.no_update, dash.no_update

  if diff_data.get("live"):
    diff_table, has_changes = run_components.render_modern_context_diff(
        diff_data.get("snapshot", {}), diff_data.get("live", {})
    )
    title_children = [
        dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
        _render_change_badge(has_changes),
    ]
    return diff_table, True, title_children, dash.no_update, False

  # Show a skeleton and set is_fetching, which is what
  # fetch_live_config_for_diff keys off.
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

  # Nothing to download while the fetch is in flight, and the button keeps
  # whatever state the last open left it in otherwise.
  return skeleton, True, title_loading, new_state, True


@typed_callback(
    output=[
        (EvaluationIds.RUN_CONTEXT_DIFF_CONTENT, CP.CHILDREN),
        (EvaluationIds.RUN_CONTEXT_DIFF_TITLE, CP.CHILDREN),
        (EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA),
        (EvaluationIds.BTN_DOWNLOAD_DIFF, CP.DISABLED),
    ],
    inputs=[dash.Input(EvaluationIds.RUN_CONTEXT_DIFF_STORE, CP.DATA)],
    prevent_initial_call=True,
    allow_duplicate=True,
)
def fetch_live_config_for_diff(diff_data: dict[str, Any]):
  """Fetches live agent configuration when is_fetching is True."""
  if not diff_data or not diff_data.get("is_fetching"):
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  agent_id = diff_data.get("agent_id")
  logger.info("fetch_live_config_for_diff started for agent %s", agent_id)
  if not agent_id:
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update

  client = get_client()
  live_context = None
  try:
    # The slow one. Everything else on this page is a local read.
    live_context = client.agents.get_published_context(agent_id)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to fetch live context for agent %s: %s", agent_id, e)

  snapshot_data = diff_data.get("snapshot", {})
  new_state = diff_data.copy()
  new_state["is_fetching"] = False

  # get_published_context returns None for an agent that is gone, so both ways
  # of coming back empty land here. Falling back to the snapshot would diff it
  # against itself and badge the result "No changes detected", which tells the
  # user the published context is unchanged on the strength of a call that
  # never returned it. Leave live unset so the next click retries.
  if not live_context:
    error_title = [
        dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
    ]
    # The download is a diff of the two contexts, and there is only one of
    # them here. It used to stay enabled beside the alert and answer a click
    # with no_update: no file, no toast, no log line.
    return (
        dmc.Alert(
            "Could not read the agent's published context. It may have been"
            " deleted, or the Data Analytics API may be unavailable.",
            title="Live context unavailable",
            color="red",
        ),
        error_title,
        new_state,
        True,
    )

  diff_table, has_changes = run_components.render_modern_context_diff(
      snapshot_data, live_context
  )
  new_state["live"] = live_context

  title_children = [
      dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
      _render_change_badge(has_changes),
  ]

  return diff_table, title_children, new_state, False


def _calculate_assertion_summary(
    assertion_details: list[dict[str, Any]],
) -> AssertionSummary:
  """Calculates pass/fail metrics for a list of assertion details."""
  overall = {"total": 0, "passed": 0}
  accuracy = {"total": 0, "passed": 0}
  diagnostic = {"total": 0, "passed": 0}

  for a in assertion_details:
    weight = a.get("weight", 0)
    passed = 1 if a.get("passed", False) else 0

    overall["total"] += 1
    overall["passed"] += passed

    if weight > 0:
      accuracy["total"] += 1
      accuracy["passed"] += passed
    else:
      diagnostic["total"] += 1
      diagnostic["passed"] += passed

  def _to_metric(counts: dict[str, float]) -> AssertionMetric:
    total = int(counts["total"])
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


def _trial_error(message: str) -> list[Any]:
  """One trial-detail error return, in the order the outputs are declared.

  The alert belongs in the detail container. Put it first and it lands in the
  breadcrumb bar instead, and the container keeps the spinner the layout left
  there, so the page reads as still loading while an error sits above it.
  """
  return [dash.no_update] * 4 + [dmc.Alert(message, color="red")]


@typed_callback(
    [
        (EvaluationIds.TRIAL_BREADCRUMBS_CONTAINER, CP.CHILDREN),
        (EvaluationIds.TRIAL_TITLE, CP.CHILDREN),
        (EvaluationIds.TRIAL_DESCRIPTION, CP.CHILDREN),
        (EvaluationIds.TRIAL_ACTIONS, CP.CHILDREN),
        (EvaluationIds.TRIAL_DETAIL_CONTAINER, CP.CHILDREN),
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
    unused_update_signal: Any = None,
    sug_loading: bool = False,
):
  """Renders the Trial Detail page."""
  if not pathname or not pathname.startswith("/evaluations/trials/"):
    return [dash.no_update] * 5

  try:
    trial_id = id_from_pathname(pathname)
  except (ValueError, IndexError):
    return [dash.no_update] * 5

  logger.info(
      "Rendering trial detail pathname=%s loading=%s",
      pathname,
      sug_loading,
  )

  client = get_client()
  try:
    trial = client.runs.get_trial(trial_id)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Failed to load trial %s: %s", trial_id, e)
    # Not the exception text. A SQLAlchemy error carries the statement and
    # its bound parameters, and this renders into the page.
    return _trial_error(
        "Could not load this trial. The details are in the server log."
    )

  if not trial:
    return _trial_error("Trial not found")

  run = client.runs.get_run(trial.run_id)
  run_link = "#"
  if run and run.original_suite_id:
    run_link = f"/test_suites/view/{run.original_suite_id}"

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

  assertion_details = []
  if trial.assertion_results:
    for ar in trial.assertion_results:
      details = {
          "type": ar.assertion.type,
          "weight": ar.assertion.weight,
          "passed": ar.passed,
          "score": ar.score,
          "reasoning": ar.reasoning,
          "error_message": ar.error_message,
      }
      # The assertion schema is flat, so whatever is left after the common
      # fields are dropped is that type's own parameters.
      assertion_data = ar.assertion.model_dump()
      for k, v in assertion_data.items():
        if k not in ["type", "weight", "id", "reasoning"]:
          details[k] = v
      assertion_details.append(details)

  parsed_qs = urllib.parse.parse_qs(search.lstrip("?")) if search else {}
  filter_cat = parsed_qs.get("assertion_category", ["all"])[0] or "all"
  filter_stat = parsed_qs.get("assertion_status", ["all"])[0] or "all"
  filter_type = parsed_qs.get("assertion_type", ["all"])[0] or "all"

  duration_ms = trial.duration_ms or 0
  ttfr_ms = trial.ttfr_ms or 0

  # trial.ttfr_ms is a property over trace_results and is None when no event
  # carries a timestamp. The 0 above is what the timeline then shows.
  trace_results = trial.trace_results or []
  timeline_obj = client.runs.parse_timeline(
      trace_results, ttfr_ms=ttfr_ms, total_duration_ms=duration_ms
  )

  failed_at_text = None
  if trial.status == RunStatus.FAILED:
    failed_at_text = dmc.Text(
        f"Failed at: {trial.failed_stage}" if trial.failed_stage else "",
        c="red",
        size="xs",
    )
  # PENDING, RUNNING, CANCELLED and PAUSED used to fall through to grey with
  # the raw enum name beside it, so a running trial got the icon that means
  # nothing is happening. See the note on the map in utils.
  status_color, status_label = run_status_display(trial.status)

  if trial.status == RunStatus.FAILED:
    error_card = cards.render_error_card(
        message=trial.error_message or "Unknown error",
        traceback_str=trial.error_traceback,
        stage=trial.failed_stage,
    )
  else:
    error_card = None

  stats_cards = dmc.Group(
      id=EvaluationIds.TRIAL_DETAIL_STATS,
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
                  dmc.Text(status_label, fw=700, size="lg", mt="sm"),
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
                  dmc.Text(
                      format_duration(trial.duration_ms),
                      fw=700,
                      size="lg",
                      mt="sm",
                  ),
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
                  dmc.Text(
                      format_ttfr(trial.ttfr_ms),
                      fw=700,
                      size="lg",
                      mt="sm",
                  ),
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
    unique_types = sorted(list({item["type"] for item in assertion_details}))
    type_options = [{"label": "All Types", "value": "all"}]
    for ut in unique_types:
      style = assertion_components.get_assertion_style(ut)
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

  accordion_style = {}
  if trial.status == RunStatus.FAILED:
    accordion_style = {"display": "none"}
    suggestions_content_div = html.Div()
  else:
    suggestion_cards = []
    if trial.suggested_asserts:
      for i, sa in enumerate(trial.suggested_asserts):
        try:
          item = sa.model_dump()
          sug_id = item.get("id")
          if sug_id is None:
            # The card writes this into its buttons' index, and
            # curate_trial_suggestion hands that index to curate_suggestion as
            # a row id. The suite page draws the same card with a list
            # position, so falling back to one here meant accepting the third
            # suggestion curated whichever row holds id 2.
            logger.error(
                "Suggestion %d of %d has no id and cannot be curated",
                i,
                len(trial.suggested_asserts),
            )
            continue
          card = assertion_components.render_suggested_assertion_card(
              item, sug_id, ids_class=EvaluationIds
          )
          suggestion_cards.append(card)
        except Exception as e:  # pylint: disable=broad-exception-caught
          # Position and exception class only. The value being rendered is a
          # suggested assertion's model_dump, whose params hold text the model
          # lifted out of the agent's answer over the customer's data, and a
          # pydantic ValidationError formats input_value={...} into its
          # message. This log goes wherever the server's stdout goes.
          logger.error(
              "Failed to render suggestion card %d of %d: %s",
              i,
              len(trial.suggested_asserts),
              type(e).__name__,
          )

    if sug_loading:
      suggestions_content_div = (
          assertion_components.render_suggestion_skeleton()
      )
    elif suggestion_cards:
      suggestions_content_div = dmc.SimpleGrid(
          cols=2, spacing="lg", children=suggestion_cards
      )
    else:
      suggestions_content_div = assertion_components.render_empty_suggestions(
          {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": "empty"}
      )
  suggestions_accordion = dmc.Accordion(
      id=EvaluationIds.TRIAL_SUG_ACCORDION,
      mb="lg",
      variant="contained",
      radius="md",
      styles={
          "control": {
              "padding": "8px 16px",
              "&:hover": {"backgroundColor": "var(--mantine-color-grape-0)"},
          },
          "item": {
              "border": "1px solid var(--mantine-color-grape-2)",
              "backgroundColor": "var(--mantine-color-grape-0)",
          },
      },
      style=accordion_style,
      children=[
          dmc.AccordionItem(
              value="suggestions",
              children=[
                  dmc.AccordionControl(
                      children=dmc.Group(
                          gap="xs",
                          children=[
                              DashIconify(
                                  icon="bi:lightbulb",
                                  width=20,
                                  color="var(--mantine-color-grape-6)",
                              ),
                              dmc.Text(
                                  "Suggested Assertions",
                                  fw=700,
                                  size="lg",
                              ),
                          ],
                      )
                  ),
                  dmc.AccordionPanel(
                      p="md",
                      children=dmc.Stack(
                          children=[
                              dmc.Group(
                                  gap="xs",
                                  children=[
                                      DashIconify(
                                          icon="material-symbols:info-outline",
                                          width=20,
                                          color="var(--mantine-color-grape-6)",
                                      ),
                                      dmc.Text(
                                          "Accepted suggestions are"
                                          " added to the test suite"
                                          " for future runs. They"
                                          " do not affect current"
                                          " results.",
                                          size="xs",
                                          c="dimmed",
                                          fw=500,
                                      ),
                                  ],
                              ),
                              html.Div(
                                  id=EvaluationIds.TRIAL_SUGGESTIONS_CONTENT,
                                  children=suggestions_content_div,
                              ),
                          ]
                      ),
                      bg="white",
                  ),
              ],
          )
      ],
  )

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

  # run is None when the parent was deleted out from under the trial, which is
  # the same case the run_link fallback above covers.
  description = [
      "Execution results for agent ",
      html.Span(
          (run.agent_name if run else None) or "Unknown Agent",
          style={"fontWeight": 600},
          className="text-dark",
      ),
      " on test suite ",
      html.Span(
          (run.suite_name if run else None) or "Unknown Suite",
          style={"fontWeight": 600},
          className="text-dark",
      ),
  ]

  profiling_chart = charts.render_trial_profiling(
      trial.tool_timings or {}, title="Tool Timing Profiling"
  )
  assertion_summary = None
  if trial.status != RunStatus.FAILED:
    assertion_summary = assertion_components.render_assertion_summary(
        _calculate_assertion_summary(assertion_details)
    )

  return [
      breadcrumbs,
      f"Trial #{trial.id}",
      description,
      header_actions,
      dmc.Stack([
          stats_cards,
          # None unless the trial failed, which Dash renders as nothing.
          error_card,
          run_components.render_trial_card(
              trial,
              show_details_link=False,
              suite_link=run_link,
              chart_section=timeline.render_chart_carousel(
                  timeline_obj.model_dump(), minimal=True
              ),
          ),
          profiling_chart,
          dmc.Grid(
              gutter="md",
              mt="md",
              children=[
                  dmc.GridCol(
                      span=12,
                      children=dmc.Stack([
                          dmc.Box([
                              assertions_header,
                              assertion_summary,
                              dmc.Space(h="lg"),
                              render_assertions,
                          ]),
                      ]),
                  ),
              ],
          ),
          suggestions_accordion,
      ]),
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

  # Writing the same search back re-triggers the filter inputs, which write it
  # again.
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
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
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
def curate_trial_suggestion(unused_accept_clicks, unused_reject_clicks):
  """Handles accepting or rejecting a suggested assertion."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return dash.no_update, dash.no_update

  # The buttons are pattern-matched, so this also fires when the suggestion
  # list re-renders and the new buttons arrive with n_clicks unset. Only a
  # trigger that carries a value is a real click.
  trigger_val = ctx.triggered[0].get("value")
  if not trigger_val:
    return dash.no_update, dash.no_update

  trigger = typed_callback.triggered_id()
  if not trigger or not isinstance(trigger, dict):
    logger.warning("Invalid trigger for curate_trial_suggestion: %s", trigger)
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
  del pathname  # Any navigation clears the state.
  return False


dash.clientside_callback(
    """
    function(n_clicks) {
        if (n_clicks && n_clicks.some(c => c > 0)) {
            return [n_clicks.map(() => true), true];
        }
        const no_update = window.dash_clientside.no_update;
        return [no_update, no_update];
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
        dash.Output(
            EvaluationIds.TRIAL_SUG_POLLING_INTERVAL,
            "n_intervals",
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
    trial_id = id_from_pathname(pathname)
  except ValueError:
    return dash.no_update

  logger.info("Starting suggestion regeneration for trial %s", trial_id)
  app = flask.current_app._get_current_object()  # pylint: disable=protected-access,no-member
  client = get_client()
  client.runs.regenerate_suggestions_async(trial_id, app)
  logger.info("Triggered suggestion regeneration for trial %s", trial_id)

  return time.time(), [True] * len(n_clicks_list), True, False, 0


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
    trial_id = id_from_pathname(pathname)
  except ValueError:
    return dash.no_update

  client = get_client()
  try:
    trial = client.runs.get_trial(trial_id)
  except Exception as e:  # pylint: disable=broad-exception-caught
    logger.error("Polling failed for trial %s: %s", trial_id, e)
    # Stop polling on error to avoid infinite loop of crashes. The signal
    # still goes out. It is the only Input render_trial_detail has here, and
    # the loading store it reads alongside is State, so leaving the signal
    # alone cleared the flag without re-rendering and the skeleton stayed on
    # screen with the interval now disabled.
    return time.time(), [False] * len(btn_ids), False, True

  sug_count = (
      len(trial.suggested_asserts) if trial and trial.suggested_asserts else 0
  )
  logger.info("Polling suggestions for trial %s: count=%s", trial_id, sug_count)

  if trial and trial.suggested_asserts:
    logger.info(
        "Suggestions arrived for trial %s, stopping polling with signal",
        trial_id,
    )
    return time.time(), [False] * len(btn_ids), False, True

  # Stop polling after ~60 seconds (20 intervals * 3s)
  if n_intervals >= 20:
    logger.info("Suggestions polling timed out for trial %s", trial_id)
    # Signalled, like the error branch above, so the panel re-renders and
    # falls through to render_empty_suggestions.
    return time.time(), [False] * len(btn_ids), False, True

  return (
      typed_callback.no_update,
      [dash.no_update] * len(btn_ids),
      dash.no_update,
      dash.no_update,
  )


# The Test Suite View run modal is opened and filled by test_suite_callbacks,
# which is where the page that renders it lives. This file owns the Start Run
# button.


@typed_callback(
    [
        dash.Output(REDIRECT_HANDLER, CP.HREF, allow_duplicate=True),
        dash.Output(
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
    ],
    inputs=[(EvaluationIds.BTN_START_RUN, "n_clicks")],
    state=[
        (EvaluationIds.AGENT_SELECT, "value"),
        (EvaluationIds.TOGGLE_SUGGESTIONS, "checked"),
        (EvaluationIds.INPUT_CONCURRENCY, "value"),
        ("url", CP.PATHNAME),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
    # Starting a run spawns trials that call a paid API. Without this the
    # button stays live for the whole round trip and a second click starts a
    # second run.
    running=[
        (dash.Output(EvaluationIds.BTN_START_RUN, CP.DISABLED), True, False),
        (dash.Output(EvaluationIds.BTN_START_RUN, CP.LOADING), True, False),
    ],
)
def start_run_eval(
    n_clicks, agent_id, generate_suggestions, concurrency, pathname
):
  """Starts a new evaluation run from the Test Suite View."""
  if not n_clicks or not agent_id:
    return dash.no_update

  if not pathname or "/test_suites/view/" not in pathname:
    return dash.no_update

  try:
    suite_id = id_from_pathname(pathname)
  except ValueError:
    return dash.no_update

  client = get_client()
  agent = client.agents.get_agent(int(agent_id))

  # The button is disabled without credentials, but the modal can be open
  # from before they were cleared.
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

  try:
    run = client.runs.create_run(
        agent_id=int(agent_id),
        test_suite_id=suite_id,
        generate_suggestions=generate_suggestions,
        concurrency=concurrency,
    )
  except ValueError as e:
    # str(e) is our own ValueError, raised by ExecutionService before it
    # touches the database ("... has no active questions"), so it carries no
    # query text or bound parameters. Unwrapped it reached handle_errors, which
    # shows the same "Something went wrong" toast as a crash, and the one
    # refusal the user can act on read as a bug.
    return dash.no_update, [{
        "action": "show",
        "title": "Cannot Start Evaluation",
        "message": str(e),
        "color": "red",
        "icon": DashIconify(icon="material-symbols:error-outline"),
    }]
  run_id = run.id

  # Queues the run. The worker process picks up PENDING runs; nothing starts
  # here.
  client.runs.execute_run_async(run_id)

  return f"/evaluations/runs/{run_id}", dash.no_update


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
            NOTIFICATION_CONTAINER, "sendNotifications", allow_duplicate=True
        ),
    ],
    inputs=[dash.Input(EvaluationIds.BTN_START_NEW_EVAL, "n_clicks")],
    state=[
        dash.State(EvaluationIds.NEW_EVAL_AGENT_SELECT, "value"),
        dash.State(EvaluationIds.NEW_EVAL_SUITE_SELECT, "value"),
        dash.State(EvaluationIds.TOGGLE_SUGGESTIONS, "checked"),
        dash.State(EvaluationIds.NEW_EVAL_INPUT_CONCURRENCY, "value"),
    ],
    prevent_initial_call=True,
    allow_duplicate=True,
    # See start_run_eval: the button has to go dead while the run is created.
    running=[
        (
            dash.Output(EvaluationIds.BTN_START_NEW_EVAL, CP.DISABLED),
            True,
            False,
        ),
        (
            dash.Output(EvaluationIds.BTN_START_NEW_EVAL, CP.LOADING),
            True,
            False,
        ),
    ],
)
def start_new_eval(
    n_clicks, agent_id, suite_id, generate_suggestions, concurrency
):
  """Starts a new evaluation run from the Global Modal."""
  if not n_clicks or not agent_id or not suite_id:
    return dash.no_update

  client = get_client()
  agent = client.agents.get_agent(int(agent_id))

  # The button is disabled without credentials, but the modal can be open
  # from before they were cleared.
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

  try:
    run = client.runs.create_run(
        agent_id=int(agent_id),
        test_suite_id=int(suite_id),
        generate_suggestions=generate_suggestions,
        concurrency=concurrency,
    )
  except ValueError as e:
    # See start_run_eval: the refusal text is the actionable part, and
    # handle_errors would replace it with the generic toast.
    return dash.no_update, [{
        "action": "show",
        "title": "Cannot Start Evaluation",
        "message": str(e),
        "color": "red",
        "icon": DashIconify(icon="material-symbols:error-outline"),
    }]
  run_id = run.id

  # Queues the run. The worker process picks up PENDING runs; nothing starts
  # here.
  client.runs.execute_run_async(run_id)

  return f"/evaluations/runs/{run_id}", dash.no_update


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
def handle_run_controls(
    unused_pause_clicks,
    unused_resume_clicks,
    unused_cancel_clicks,
    pathname,
):
  """Handles Pause/Resume/Cancel button clicks."""
  if not pathname or not pathname.startswith("/evaluations/runs/"):
    return dash.no_update

  try:
    run_id = id_from_pathname(pathname)
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


def _render_change_badge(has_changes: bool) -> dmc.Badge:
  """Renders a badge indicating if changes were detected."""
  if has_changes:
    return dmc.Badge(
        "Changes detected",
        id=EvaluationIds.RUN_CONTEXT_DIFF_BADGE,
        color="orange",
        variant="light",
        radius="sm",
        size="xs",
        fw=700,
    )
  return dmc.Badge(
      "No changes detected",
      id=EvaluationIds.RUN_CONTEXT_DIFF_BADGE,
      color="gray",
      variant="light",
      radius="sm",
      size="xs",
  )
