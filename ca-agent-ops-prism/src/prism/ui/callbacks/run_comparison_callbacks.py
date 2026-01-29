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

"""Callbacks for Run Comparison Page."""

import math
from typing import Any
import urllib.parse
import dash
from dash import Input
from dash import Output
from dash import State
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas.execution import RunStatus
from prism.ui.components.assertion_components import get_assertion_style
from prism.ui.components.assertion_components import render_assertion_diagnostic_accordion
from prism.ui.components.run_components import render_modern_context_diff
from prism.ui.ids import ComparisonIds
from prism.ui.models.comparison_state import RunComparisonUIState
from prism.ui.utils import handle_errors
from prism.ui.utils import typed_callback


def _render_accuracy_delta_bar(val: float):
  """Renders a simple horizontal bar for accuracy delta."""
  color = "green" if val >= 0 else "red"
  width = abs(val) * 100
  # Cap at 100 for safety, though it shouldn't exceed 1.0 (100%)
  width = min(width, 100)

  return dmc.Box(
      style={
          "width": "100%",
          "height": "6px",
          "backgroundColor": "var(--mantine-color-gray-1)",
          "borderRadius": "3px",
          "overflow": "hidden",
          "position": "relative",
      },
      children=[
          dmc.Box(
              style={
                  "width": f"{width}%",
                  "height": "100%",
                  "backgroundColor": f"var(--mantine-color-{color}-6)",
                  "borderRadius": "3px",
                  "position": "absolute",
                  "left": "0" if val >= 0 else "auto",
                  "right": "0" if val < 0 else "auto",
              }
          )
      ],
  )


def _render_performance_delta_chart(cases: list[Any]):
  """Renders the bar chart for trial performance deltas."""
  # Cases are already ordered by logical_id/test suite order from the service
  sorted_cases = cases

  # Calculate max absolute delta for vertical scaling
  max_abs_delta = max(
      (abs(c.score_delta or 0.0) for c in sorted_cases), default=0.0
  )
  # Round up to nearest 5% for Y-axis labels and consistent scaling
  label_max = math.ceil(max_abs_delta / 0.05) * 0.05
  if label_max == 0:
    label_max = 0.05  # Minimum scale

  bars = []
  for case in sorted_cases:
    delta = case.score_delta or 0.0
    color = "green" if delta > 0 else "red" if delta < 0 else "gray"

    # Calculate height as percentage of total container (max 50% for one side)
    pct_height = (abs(delta) / label_max) * 50

    # Ensure minimum visibility
    if delta == 0:
      height_style = "2px"
      margin_top = "-1px"
    else:
      # Use python max to avoid CSS max() compatibility issues or string
      # formatting bugs. 2% is roughly 4-5px on a 200-250px high chart.
      effective_pct = max(pct_height, 2.0)
      height_style = f"{effective_pct:.2f}%"
      margin_top = "0"

    bars.append(
        dmc.Box(
            style={
                "flex": 1,
                "minWidth": "6px",  # Slightly wider min width
                "height": "100%",
                "position": "relative",
                "cursor": "pointer",
            },
            children=[
                # 1. The Visible Bar (Absolute positioned)
                dmc.Box(
                    style={
                        "width": "100%",
                        "height": height_style,
                        "backgroundColor": (
                            f"var(--mantine-color-{color}-4)"
                            if delta != 0
                            else "var(--mantine-color-gray-3)"
                        ),
                        "borderRadius": "1px",
                        "position": "absolute",
                        "bottom": "50%" if delta >= 0 else "auto",
                        "top": "50%" if delta < 0 else "auto",
                        "marginTop": margin_top,
                        "zIndex": 1,
                    }
                ),
                # 2. The Tooltip Trigger (Invisible overlay filling the column)
                dmc.Tooltip(
                    label=f"{case.question}: {delta:+.1%}",
                    children=dmc.Box(
                        style={
                            "position": "absolute",
                            "inset": 0,
                            "zIndex": 2,  # Above the bar
                        }
                    ),
                    withArrow=True,
                ),
            ],
        )
    )

  return dmc.Box(
      style={
          "height": "100%",
          "flex": 1,
          "display": "flex",
          "flexDirection": "row",
          "alignItems": "center",
          "padding": "20px 0",
          "overflow": "hidden",  # Prevent overflow
      },
      children=[
          # Y-axis Labels
          dmc.Box(
              style={
                  "display": "flex",
                  "flexDirection": "column",
                  "justifyContent": "space-between",
                  "height": "100%",  # Fill container
                  "paddingRight": "12px",
                  "borderRight": "1px solid var(--mantine-color-gray-2)",
              },
              children=[
                  dmc.Text(f"+{label_max:.0%}", size="xs", c="dimmed", fw=500),
                  dmc.Text("0%", size="xs", c="dimmed", fw=500),
                  dmc.Text(f"-{label_max:.0%}", size="xs", c="dimmed", fw=500),
              ],
          ),
          # Chart Area
          dmc.Box(
              style={
                  "flex": 1,
                  "height": "100%",  # Fill container
                  "position": "relative",
                  "display": "flex",
                  "alignItems": "center",
                  "paddingLeft": "12px",
              },
              children=[
                  # Midline
                  dmc.Box(
                      style={
                          "position": "absolute",
                          "left": 0,
                          "right": 0,
                          "top": "50%",
                          "height": "1px",
                          "backgroundColor": "var(--mantine-color-gray-2)",
                          "zIndex": 0,
                      }
                  ),
                  dmc.Group(
                      gap=3,
                      align="stretch",  # Ensure columns stretch to full height
                      style={"zIndex": 1, "width": "100%", "height": "100%"},
                      children=bars,
                      grow=True,
                  ),
              ],
          ),
      ],
  )


def _parse_search(search: str | None) -> RunComparisonUIState:
  """Parses URL search string into UI State."""
  state = RunComparisonUIState()
  if not search:
    return state

  params = urllib.parse.parse_qs(search.lstrip("?"))

  def get_first(key, default=None):
    vals = params.get(key, [])
    return vals[0] if vals else default

  state.suite_id = (
      int(get_first(ComparisonIds.URL_SUITE_ID))
      if get_first(ComparisonIds.URL_SUITE_ID)
      else None
  )
  state.base_run_id = (
      int(get_first(ComparisonIds.URL_BASE_RUN_ID))
      if get_first(ComparisonIds.URL_BASE_RUN_ID)
      else None
  )
  state.challenger_run_id = (
      int(get_first(ComparisonIds.URL_CHALLENGER_RUN_ID))
      if get_first(ComparisonIds.URL_CHALLENGER_RUN_ID)
      else None
  )
  state.filter_status = get_first(ComparisonIds.URL_FILTER)
  return state


def _build_search(
    base_id: int | None,
    chal_id: int | None,
    suite_id: int | None = None,
    filter_status: str | None = None,
) -> str:
  """Builds URL search string from state."""
  params = {}
  if suite_id:
    params[ComparisonIds.URL_SUITE_ID] = str(suite_id)
  if base_id:
    params[ComparisonIds.URL_BASE_RUN_ID] = str(base_id)
  if chal_id:
    params[ComparisonIds.URL_CHALLENGER_RUN_ID] = str(chal_id)
  if filter_status:
    params[ComparisonIds.URL_FILTER] = filter_status
  return "?" + urllib.parse.urlencode(params) if params else ""


# 1. URL -> UI (Selects & Filters)
@typed_callback(
    inputs=[
        Input(ComparisonIds.LOC_URL, "search"),
        Input(ComparisonIds.FILTER_ALL, "n_clicks"),
        Input(ComparisonIds.FILTER_REGRESSIONS, "n_clicks"),
        Input(ComparisonIds.FILTER_IMPROVEMENTS, "n_clicks"),
        Input(ComparisonIds.FILTER_UNCHANGED, "n_clicks"),
    ],
    output=[
        Output(ComparisonIds.LOC_URL, "search", allow_duplicate=True),
    ],
    prevent_initial_call="initial_duplicate",
)
def synchronize_filters(
    current_search: str | None,
    *_args,  # Sink unused n_clicks
) -> tuple[str] | Any:
  """Synchronizes filters in URL."""
  ctx = dash.callback_context
  trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

  # Parse current URL state
  url_state = _parse_search(current_search)

  # If filter button was clicked, update URL search
  if "comp-filter-" in trigger:
    new_filter = url_state.filter_status
    if ComparisonIds.FILTER_REGRESSIONS in trigger:
      new_filter = "REGRESSION"
    elif ComparisonIds.FILTER_IMPROVEMENTS in trigger:
      new_filter = "IMPROVED"
    elif ComparisonIds.FILTER_UNCHANGED in trigger:
      new_filter = "STABLE"
    elif ComparisonIds.FILTER_ALL in trigger:
      new_filter = None

    return (
        _build_search(
            url_state.base_run_id,
            url_state.challenger_run_id,
            url_state.suite_id,
            new_filter,
        ),
    )

  return dash.no_update


# 2. Modal Callbacks
@typed_callback(
    inputs=[
        Input(ComparisonIds.BTN_OPEN_SELECT_RUNS, "n_clicks"),
        Input(ComparisonIds.BTN_EMPTY_SELECT_RUNS, "n_clicks"),
        Input(ComparisonIds.BTN_CLOSE_SELECT_RUNS, "n_clicks"),
        Input(ComparisonIds.BTN_APPLY_SELECT_RUNS, "n_clicks"),
    ],
    state=[
        State(ComparisonIds.LOC_URL, "search"),
        State(ComparisonIds.SUITE_SELECT, "value"),
        State(ComparisonIds.BASE_RUN_SELECT, "value"),
        State(ComparisonIds.CHALLENGE_RUN_SELECT, "value"),
    ],
    output=[
        Output(ComparisonIds.SELECT_RUNS_MODAL, "opened"),
        Output(ComparisonIds.LOC_URL, "search", allow_duplicate=True),
        Output(ComparisonIds.SUITE_SELECT, "value"),
        Output(ComparisonIds.BASE_RUN_SELECT, "value"),
        Output(ComparisonIds.CHALLENGE_RUN_SELECT, "value"),
    ],
    prevent_initial_call=True,
)
def handle_select_runs_modal(
    unused_open_clicks,
    unused_empty_clicks,
    unused_close_clicks,
    unused_apply_clicks,
    current_search,
    suite_id,
    base_id,
    chal_id,
):
  """Handles opening, closing, and applying run selection."""
  ctx = dash.callback_context
  if not ctx.triggered:
    return dash.no_update

  trigger = ctx.triggered[0]["prop_id"]

  if ComparisonIds.BTN_APPLY_SELECT_RUNS in trigger:
    if not base_id or not chal_id:
      return dash.no_update  # Or show error in modal
    new_search = _build_search(
        int(base_id), int(chal_id), int(suite_id) if suite_id else None
    )
    return False, new_search, dash.no_update, dash.no_update, dash.no_update

  if ComparisonIds.BTN_CLOSE_SELECT_RUNS in trigger:
    return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update

  # OPEN triggered - Pre-populate from URL
  url_state = _parse_search(current_search)
  suite_id = url_state.suite_id
  base_id = url_state.base_run_id
  chal_id = url_state.challenger_run_id

  if not suite_id and (base_id or chal_id):
    # Try to infer suite ID from runs
    client = get_client()
    for rid in [base_id, chal_id]:
      if rid:
        run = client.runs.get_run(rid)
        if run and run.original_suite_id:
          suite_id = run.original_suite_id
          break

  return (
      True,
      dash.no_update,
      str(suite_id) if suite_id else dash.no_update,
      str(base_id) if base_id else dash.no_update,
      str(chal_id) if chal_id else dash.no_update,
  )


# 3. URL -> Content (Metrics & List)
@handle_errors
@typed_callback(
    inputs=[
        Input(ComparisonIds.LOC_URL, "pathname"),
        Input(ComparisonIds.LOC_URL, "search"),
    ],
    output=[
        Output(ComparisonIds.METRICS_CARDS, "children"),
        Output(ComparisonIds.COMPARISON_LIST, "children"),
        Output(ComparisonIds.CONTEXT_DIFF_CONTENT, "children"),
        Output(ComparisonIds.CONTEXT_DIFF_BADGE, "children"),
        Output(ComparisonIds.CONTEXT_DIFF_BADGE, "color"),
        Output(ComparisonIds.EMPTY_STATE, "style"),
        Output(ComparisonIds.SUMMARY_SECTION, "style"),
        Output(ComparisonIds.CONTEXT_DIFF_ACCORDION, "style"),
        Output(ComparisonIds.SUBTITLE_TEXT, "children"),
        Output(ComparisonIds.PERFORMANCE_DELTA_CHART, "children"),
        Output(ComparisonIds.ASSERTION_DELTA_CHART, "children"),
        Output(ComparisonIds.FILTER_BAR, "children"),
    ],
)
def update_page_content(
    unused_pathname: str | None,
    search: str | None,
) -> tuple[Any, ...]:
  """Updates page content based on URL state."""
  # Parse IDs and filters from search
  state = _parse_search(search)

  if not state.base_run_id or not state.challenger_run_id:
    return (
        [],
        [],
        [
            dmc.Text(
                "Select two runs to compare their configurations.",
                c="dimmed",
                ta="center",
                size="sm",
                py="xl",
            )
        ],
        "CONTEXT DIFF",
        "gray",
        {"display": "block"},
        {"display": "none"},
        {"display": "none"},
        None,
        [],
        [],
        [],
    )

  client = get_client()
  try:
    comparison = client.comparison.compare_runs(
        state.base_run_id, state.challenger_run_id
    )
  except ValueError as e:
    return (
        [dmc.Alert(str(e), color="red")],
        [],
        [],
        "CONTEXT DIFF",
        "gray",
        {"display": "block"},
        {"display": "none"},
        {"display": "none"},
        dash.no_update,
        [],
        [],
        [],
    )

  # Render Context Diff
  base_run = client.runs.get_run(state.base_run_id)
  chal_run = client.runs.get_run(state.challenger_run_id)
  context_diff = []
  badge_text = "CONTEXT DIFF"
  badge_color = "gray"

  if base_run and chal_run:
    base_snap = base_run.agent_context_snapshot or {}
    chal_snap = chal_run.agent_context_snapshot or {}

    diff_table, change_count = render_modern_context_diff(base_snap, chal_snap)
    context_diff = [diff_table]

    if change_count > 0:
      badge_text = "Changes detected"
      badge_color = "orange"
    else:
      badge_text = "No changes detected"
      badge_color = "gray"

  # Render Metrics
  delta = comparison.delta
  metrics = [
      # Accuracy
      _render_metric_card(
          "Accuracy Delta",
          f"{delta.accuracy_delta:+.1%}",
          "material-symbols:trending-up"
          if delta.accuracy_delta >= 0
          else "material-symbols:trending-down",
          "green" if delta.accuracy_delta >= 0 else "red",
          "Accuracy Gain" if delta.accuracy_delta >= 0 else "Degradation",
      ),
      # Duration
      _render_metric_card(
          "Avg Latency Delta",
          f"{delta.duration_delta_avg:+.0f}ms",
          "material-symbols:timer",
          "orange" if delta.duration_delta_avg > 0 else "green",
          "Slower" if delta.duration_delta_avg > 0 else "Faster",
      ),
      # Regressions
      _render_metric_card(
          "Regressions",
          str(delta.regressions_count),
          "material-symbols:warning",
          "red" if delta.regressions_count > 0 else "gray",
          "Cases impacted",
      ),
      # Improvements
      _render_metric_card(
          "Improvements",
          str(delta.improvements_count),
          "material-symbols:star",
          "green" if delta.improvements_count > 0 else "gray",
          "Cases improved",
      ),
  ]

  # Subtitle
  subtitle = dmc.Group(
      gap="xs",
      children=[
          dmc.Text("Comparing", size="xl"),
          _render_run_pill(
              f"Run #{state.base_run_id} (Baseline)",
              f"/evaluations/runs/{state.base_run_id}",
          ),
          dmc.Text("vs", size="xl"),
          _render_run_pill(
              f"Run #{state.challenger_run_id} (Candidate)",
              f"/evaluations/runs/{state.challenger_run_id}",
          ),
      ],
      mb="md",
  )

  # Exclusion Notice
  if delta.errors_count > 0:
    subtitle.children.append(
        dmc.Alert(
            f"Note: {delta.errors_count} failed trial(s) were excluded from"
            " accuracy and latency calculations.",
            color="orange",
            variant="light",
            radius="md",
            mt="md",
            icon=DashIconify(icon="material-symbols:info-outline", width=18),
        )
    )

  # Assertion Deltas (Aggregate from cases)
  assertion_deltas: dict[str, list[float]] = {}
  for case in comparison.cases:
    if not case.base_trial or not case.challenger_trial:
      continue
    # Map assertion type -> change in score
    base_scores = {
        ar.assertion.type: ar.score for ar in case.base_trial.assertion_results
    }
    chal_scores = {
        ar.assertion.type: ar.score
        for ar in case.challenger_trial.assertion_results
    }
    for atype, chal_score in chal_scores.items():
      if atype in base_scores:
        assertion_deltas.setdefault(atype, []).append(
            chal_score - base_scores[atype]
        )

  assertion_delta_elements = []
  for atype, deltas in assertion_deltas.items():
    avg_delta = sum(deltas) / len(deltas)
    style = get_assertion_style(atype)
    assertion_delta_elements.append(
        dmc.Stack(
            gap=4,
            children=[
                dmc.Group(
                    justify="space-between",
                    children=[
                        dmc.Group(
                            gap="xs",
                            children=[
                                dmc.ThemeIcon(
                                    DashIconify(
                                        icon=style["icon"],
                                        width=14,
                                    ),
                                    size="sm",
                                    variant="light",
                                    color=style["color"],
                                    radius="sm",
                                ),
                                dmc.Text(style["label"], size="sm", fw=500),
                            ],
                        ),
                        dmc.Text(
                            f"{avg_delta:+.1%}",
                            size="sm",
                            fw=700,
                            c="green" if avg_delta >= 0 else "red",
                        ),
                    ],
                ),
                _render_accuracy_delta_bar(avg_delta),
            ],
        )
    )

  # Filter Cases
  cases = comparison.cases

  # Calculate Counts
  regressed_count = len([c for c in cases if c.status == "REGRESSION"])
  improved_count = len([c for c in cases if c.status == "IMPROVED"])
  unchanged_count = len([c for c in cases if c.status == "STABLE"])

  # Section Title and Filters
  filter_bar = dmc.Group(
      mt="xl",
      mb="md",
      justify="space-between",
      children=[
          dmc.Text("Test Cases", fw=700, size="lg"),
          dmc.Group(
              gap="xs",
              p=4,
              bg="gray.1",
              style={"borderRadius": "var(--mantine-radius-md)"},
              children=[
                  dmc.Button(
                      dmc.Group(
                          gap=8,
                          children=[
                              dmc.Text(
                                  "All",
                                  size="sm",
                                  fw=500,
                                  c="dark"
                                  if not state.filter_status
                                  else "gray.7",
                              ),
                              dmc.Badge(
                                  str(comparison.metadata.total_cases),
                                  size="xs",
                                  variant="light",
                                  color="dark",
                                  radius="sm",
                              ),
                          ],
                      ),
                      id=ComparisonIds.FILTER_ALL,
                      variant="filled" if not state.filter_status else "subtle",
                      color="dark" if not state.filter_status else "gray",
                      bg="white" if not state.filter_status else "transparent",
                      size="xs",
                      radius="sm",
                      style={
                          "boxShadow": (
                              "var(--mantine-shadow-xs)"
                              if not state.filter_status
                              else "none"
                          )
                      },
                  ),
                  dmc.Button(
                      dmc.Group(
                          gap=8,
                          children=[
                              dmc.Text(
                                  "Regressed",
                                  size="sm",
                                  fw=500,
                                  c="red"
                                  if state.filter_status == "REGRESSION"
                                  else "gray.7",
                              ),
                              dmc.Badge(
                                  str(regressed_count),
                                  size="xs",
                                  variant="light",
                                  color="red",
                                  radius="sm",
                              ),
                          ],
                      ),
                      id=ComparisonIds.FILTER_REGRESSIONS,
                      variant="filled"
                      if state.filter_status == "REGRESSION"
                      else "subtle",
                      color="red"
                      if state.filter_status == "REGRESSION"
                      else "gray",
                      bg="white"
                      if state.filter_status == "REGRESSION"
                      else "transparent",
                      size="xs",
                      radius="sm",
                      style={
                          "boxShadow": (
                              "var(--mantine-shadow-xs)"
                              if state.filter_status == "REGRESSION"
                              else "none"
                          )
                      },
                  ),
                  dmc.Button(
                      dmc.Group(
                          gap=8,
                          children=[
                              dmc.Text(
                                  "Improved",
                                  size="sm",
                                  fw=500,
                                  c="green"
                                  if state.filter_status == "IMPROVED"
                                  else "gray.7",
                              ),
                              dmc.Badge(
                                  str(improved_count),
                                  size="xs",
                                  variant="light",
                                  color="green",
                                  radius="sm",
                              ),
                          ],
                      ),
                      id=ComparisonIds.FILTER_IMPROVEMENTS,
                      variant="filled"
                      if state.filter_status == "IMPROVED"
                      else "subtle",
                      color="green"
                      if state.filter_status == "IMPROVED"
                      else "gray",
                      bg="white"
                      if state.filter_status == "IMPROVED"
                      else "transparent",
                      size="xs",
                      radius="sm",
                      style={
                          "boxShadow": (
                              "var(--mantine-shadow-xs)"
                              if state.filter_status == "IMPROVED"
                              else "none"
                          )
                      },
                  ),
                  dmc.Button(
                      dmc.Group(
                          gap=8,
                          children=[
                              dmc.Text(
                                  "Unchanged",
                                  size="sm",
                                  fw=500,
                                  c="dark"
                                  if state.filter_status == "STABLE"
                                  else "gray.7",
                              ),
                              dmc.Badge(
                                  str(unchanged_count),
                                  size="xs",
                                  variant="light",
                                  color="gray",
                                  radius="sm",
                              ),
                          ],
                      ),
                      id=ComparisonIds.FILTER_UNCHANGED,
                      variant="filled"
                      if state.filter_status == "STABLE"
                      else "subtle",
                      color="dark"
                      if state.filter_status == "STABLE"
                      else "gray",
                      bg="white"
                      if state.filter_status == "STABLE"
                      else "transparent",
                      size="xs",
                      radius="sm",
                      style={
                          "boxShadow": (
                              "var(--mantine-shadow-xs)"
                              if state.filter_status == "STABLE"
                              else "none"
                          )
                      },
                  ),
              ],
          ),
      ],
  )

  if state.filter_status:
    cases = [c for c in cases if c.status == state.filter_status]

  # Render List
  row_elements = [
      _render_comparison_row(c, state.base_run_id, state.challenger_run_id)
      for c in cases
  ]
  if not row_elements:
    row_elements = [
        dmc.Text("No cases found matching filters.", c="dimmed", ta="center")
    ]

  return (
      metrics,
      row_elements,
      context_diff,
      badge_text,
      badge_color,
      {"display": "none"},
      {"display": "block"},
      {"display": "block"},
      subtitle,
      _render_performance_delta_chart(comparison.cases),
      assertion_delta_elements,
      filter_bar,
  )


# 4. Populate Run Selects (Independent)
@handle_errors
@dash.callback(
    Output(ComparisonIds.SUITE_SELECT, "data"),
    Output(ComparisonIds.BASE_RUN_SELECT, "data"),
    Output(ComparisonIds.CHALLENGE_RUN_SELECT, "data"),
    Input(ComparisonIds.LOC_URL, "pathname"),  # Trigger on load
    Input(ComparisonIds.SUITE_SELECT, "value"),  # Trigger on test suite change
    State(ComparisonIds.LOC_URL, "search"),  # Get current IDs
)
def populate_run_selects(
    pathname: str | None, selected_suite_id: str | None, search: str | None
):
  """Populates the run selection dropdowns."""
  if not pathname or pathname != "/compare":
    return dash.no_update, dash.no_update, dash.no_update

  # Parse IDs from search
  state = _parse_search(search)
  required_ids = {state.base_run_id, state.challenger_run_id} - {None}

  client = get_client()

  # 1. Populate Test Suite Options
  suites = client.runs.get_unique_suites_from_snapshots()
  suite_options = [
      {"label": s["name"], "value": str(s["original_suite_id"])} for s in suites
  ]

  # 2. Determine which test suite to use for filtering runs
  # Priority: selected_suite_id > state.suite_id > inferred
  suite_to_use = selected_suite_id or (
      str(state.suite_id) if state.suite_id else None
  )

  if not suite_to_use and required_ids:
    # Try to infer test suite from either required run
    for run_id in required_ids:
      run = client.runs.get_run(run_id)
      if run and run.original_suite_id:
        suite_to_use = str(run.original_suite_id)
        break

  # 3. Populate Run Options
  if not suite_to_use:
    return suite_options, [], []

  # Fetch runs for the selected test suite
  runs = client.runs.list_runs(original_suite_id=int(suite_to_use), limit=50)

  # Ensure required IDs are in the list if they belong to this test suite
  existing_ids = {r.id for r in runs}
  for run_id in required_ids:
    if run_id not in existing_ids:
      run = client.runs.get_run(run_id)
      if run and run.original_suite_id == int(suite_to_use):
        runs.append(run)

  # Sort again just in case
  runs.sort(key=lambda r: r.created_at, reverse=True)

  run_options = [
      {
          "value": str(r.id),
          "label": f"Run #{r.id} ({r.created_at.strftime('%Y-%m-%d %H:%M')})",
      }
      for r in runs
  ]

  return suite_options, run_options, run_options


# 5. Swap Runs
@typed_callback(
    inputs=[Input(ComparisonIds.BTN_SWAP_RUNS, "n_clicks")],
    state=[
        State(ComparisonIds.BASE_RUN_SELECT, "value"),
        State(ComparisonIds.CHALLENGE_RUN_SELECT, "value"),
    ],
    output=[
        Output(ComparisonIds.BASE_RUN_SELECT, "value", allow_duplicate=True),
        Output(
            ComparisonIds.CHALLENGE_RUN_SELECT, "value", allow_duplicate=True
        ),
    ],
    prevent_initial_call=True,
)
def swap_runs(_: int, base_id: str | None, chal_id: str | None):
  """Swaps base and challenger runs in the modal."""
  return chal_id, base_id


# 6. Populate Run Nav Links
@typed_callback(
    output=[
        Output(ComparisonIds.BASE_RUN_NAV, "children"),
        Output(ComparisonIds.CHALLENGE_RUN_NAV, "children"),
    ],
    inputs=[
        Input(ComparisonIds.BASE_RUN_SELECT, "value"),
        Input(ComparisonIds.CHALLENGE_RUN_SELECT, "value"),
    ],
)
def populate_run_nav(
    base_id: str | None, chal_id: str | None
) -> tuple[Any, Any]:
  """Populates navigation links under run selectors."""

  def get_nav(run_id: str | None):
    if not run_id:
      return []
    return [
        dmc.Anchor(
            dmc.Button(
                "View Run Page",
                leftSection=DashIconify(icon="bi:box-arrow-up-right", width=14),
                variant="subtle",
                size="compact-xs",
                color="blue",
            ),
            href=f"/evaluations/runs/{run_id}",
            target="_blank",
        )
    ]

  return get_nav(base_id), get_nav(chal_id)


# --- Helpers ---


def _render_run_pill(label: str, href: str):
  """Renders a run link as a pill button."""
  return dmc.Anchor(
      dmc.Box(
          label,
          style={
              "padding": "4px 10px",
              "borderRadius": "var(--mantine-radius-md)",
              "backgroundColor": "var(--mantine-color-gray-0)",
              "border": "1px solid var(--mantine-color-gray-2)",
              "display": "inline-block",
              "transition": (
                  "background-color 0.2s ease, border-color 0.2s ease"
              ),
              "cursor": "pointer",
          },
          fw=700,
          fz="md",
      ),
      href=href,
      underline=False,
      c="blue.6",
      target="_blank",
  )


def _render_metric_card(title, value, icon, color, status_text=None):
  """Renders a metric card."""
  badge = None
  if status_text:
    badge = dmc.Text(status_text, size="xs", c=color, fw=500)

  return dmc.Paper(
      p="md",
      withBorder=True,
      radius="md",
      shadow="sm",
      children=[
          dmc.Group(
              justify="space-between",
              align="flex-start",
              children=[
                  dmc.Stack(
                      gap=4,
                      children=[
                          dmc.Text(
                              title,
                              size="xs",
                              c="dimmed",
                              fw=700,
                              tt="uppercase",
                          ),
                          dmc.Group(
                              align="baseline",
                              gap="xs",
                              children=[
                                  dmc.Text(
                                      value,
                                      fw=700,
                                      size="xl",
                                      style={"fontFamily": "var(--font-mono)"},
                                  ),
                                  badge,
                              ],
                          ),
                      ],
                  ),
                  dmc.ThemeIcon(
                      DashIconify(icon=icon, width=20),
                      color=color,
                      variant="light",
                      size="lg",
                      radius="md",
                  ),
              ],
          ),
      ],
  )


def _render_comparison_row(case, base_run_id, challenger_run_id):
  """Renders a single comparison row (case)."""
  color = "gray"
  status_label = case.status.value
  if case.status == "REGRESSION":
    color = "red"
    status_label = "REGRESSION"
  elif case.status == "IMPROVED":
    color = "green"
    status_label = "IMPROVED"
  elif case.status == "ERROR":
    color = "orange"
  elif case.status == "NEW":
    color = "blue"
    status_label = "ADDED"
  elif case.status == "REMOVED":
    color = "gray"

  # Score Delta: 0.00 -> 0.00
  base_score = (
      case.base_trial.score
      if case.base_trial and case.base_trial.score is not None
      else 0.0
  )
  chal_score = (
      case.challenger_trial.score
      if case.challenger_trial and case.challenger_trial.score is not None
      else 0.0
  )

  latency_delta = case.duration_delta or 0
  if latency_delta > 50:
    latency_color = "red"
  elif latency_delta < -50:
    latency_color = "green"
  else:
    latency_color = "gray"

  # Accuracy Change Section
  if case.status in ["NEW", "REMOVED"]:
    accuracy_change_content = dmc.Text(
        "N/A",
        size="sm",
        fw=700,
        c="dimmed",
        style={"fontFamily": "var(--font-mono)"},
    )
  else:
    chal_score_color = "inherit"
    if case.status in ["REGRESSION", "IMPROVED"]:
      chal_score_color = color

    accuracy_change_content = dmc.Group(
        gap=8,
        children=[
            dmc.Text(
                f"{base_score:.0%}",
                size="sm",
                fw=700,
                style={"fontFamily": "var(--font-mono)"},
            ),
            DashIconify(
                icon="material-symbols:arrow-right-alt",
                width=16,
                color="var(--mantine-color-gray-4)",
            ),
            dmc.Text(
                f"{chal_score:.0%}",
                size="sm",
                fw=700,
                c=chal_score_color,
                style={"fontFamily": "var(--font-mono)"},
            ),
        ],
    )

  # Anchors and diagnostics
  view_trial_anchor = None
  view_trace_anchor = None
  if case.base_trial:
    is_terminal = case.base_trial.status in (
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    )
    if is_terminal:
      view_trial_anchor = dmc.Anchor(
          "View Trial",
          href=f"/evaluations/trials/{case.base_trial.id}",
          size="10px",
          fw=700,
          underline=True,
          c="blue.6",
      )
      view_trace_anchor = dmc.Anchor(
          "View Trace",
          href=f"/evaluations/trials/{case.base_trial.id}/trace",
          size="10px",
          fw=700,
          underline=True,
          c="blue.6",
      )

  view_chal_trial_anchor = None
  view_chal_trace_anchor = None
  if case.challenger_trial:
    is_terminal = case.challenger_trial.status in (
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    )
    if is_terminal:
      view_chal_trial_anchor = dmc.Anchor(
          "View Trial",
          href=f"/evaluations/trials/{case.challenger_trial.id}",
          size="10px",
          fw=700,
          underline=True,
          c="blue.6",
      )
      view_chal_trace_anchor = dmc.Anchor(
          "View Trace",
          href=f"/evaluations/trials/{case.challenger_trial.id}/trace",
          size="10px",
          fw=700,
          underline=True,
          c="blue.6",
      )

  assertion_diagnostic = None
  if (case.base_trial and case.base_trial.assertion_results) or (
      case.challenger_trial and case.challenger_trial.assertion_results
  ):
    assertion_diagnostic = render_assertion_diagnostic_accordion(
        case.base_trial, case.challenger_trial, case.logical_id
    )

  base_trial_summary = dmc.Text("N/A", c="dimmed", size="sm")
  if case.base_trial:
    base_trial_summary = _render_trial_summary(case.base_trial, is_base=True)

  chal_trial_summary = dmc.Text("N/A", c="dimmed", size="sm")
  if case.challenger_trial:
    chal_trial_summary = _render_trial_summary(
        case.challenger_trial, is_base=False
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      mb="xl",
      style={
          "overflow": "hidden",
          "borderColor": (
              "var(--mantine-color-red-2)"
              if case.status == "REGRESSION"
              else "var(--mantine-color-gray-2)"
          ),
      },
      children=[
          # Header
          dmc.Box(
              p="lg",
              children=[
                  dmc.Group(
                      justify="space-between",
                      align="flex-start",
                      children=[
                          dmc.Stack(
                              gap=8,
                              children=[
                                  dmc.Group(
                                      gap="xs",
                                      children=[
                                          dmc.Badge(
                                              status_label,
                                              color=color,
                                              variant="light",
                                              size="xs",
                                              radius="sm",
                                              fw=700,
                                          ),
                                      ],
                                  ),
                                  dmc.Text(
                                      f'"{case.question}"',
                                      fw=600,
                                      size="md",
                                      style={"letterSpacing": "-0.01em"},
                                  ),
                              ],
                          ),
                          dmc.Group(
                              gap="xl",
                              children=[
                                  dmc.Stack(
                                      gap=4,
                                      align="flex-end",
                                      children=[
                                          dmc.Text(
                                              "Accuracy Change",
                                              size="10px",
                                              fw=700,
                                              c="dimmed",
                                              style={
                                                  "fontFamily": (
                                                      "var(--font-mono)"
                                                  )
                                              },
                                          ),
                                          accuracy_change_content,
                                      ],
                                  ),
                                  dmc.Stack(
                                      gap=4,
                                      align="flex-end",
                                      children=[
                                          dmc.Text(
                                              "LATENCY",
                                              size="10px",
                                              fw=700,
                                              c="dimmed",
                                              style={
                                                  "fontFamily": (
                                                      "var(--font-mono)"
                                                  )
                                              },
                                          ),
                                          dmc.Text(
                                              f"{latency_delta:+}ms",
                                              size="sm",
                                              fw=700,
                                              c=latency_color,
                                              style={
                                                  "fontFamily": (
                                                      "var(--font-mono)"
                                                  )
                                              },
                                          ),
                                      ],
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          ),
          # Body
          dmc.Grid(
              gutter=0,
              style={"borderTop": "1px solid var(--mantine-color-gray-1)"},
              children=[
                  # Base
                  dmc.GridCol(
                      span=6,
                      p="lg",
                      children=[
                          dmc.Group(
                              gap="xs",
                              mb="md",
                              children=[
                                  dmc.Box(
                                      style={
                                          "width": "6px",
                                          "height": "6px",
                                          "borderRadius": "50%",
                                          "backgroundColor": (
                                              "var(--mantine-color-gray-4)"
                                          ),
                                      }
                                  ),
                                  dmc.Text(
                                      f"BASELINE (RUN #{base_run_id})",
                                      size="10px",
                                      fw=700,
                                      c="dimmed",
                                  ),
                                  view_trial_anchor,
                                  view_trace_anchor,
                              ],
                          ),
                          base_trial_summary,
                      ],
                  ),
                  # Challenger
                  dmc.GridCol(
                      span=6,
                      p="lg",
                      style={
                          "borderLeft": "1px solid var(--mantine-color-gray-1)",
                          "backgroundColor": (
                              "var(--mantine-color-red-0)"
                              if case.status == "REGRESSION"
                              else "transparent"
                          ),
                      },
                      children=[
                          dmc.Group(
                              gap="xs",
                              mb="md",
                              children=[
                                  dmc.Box(
                                      style={
                                          "width": "6px",
                                          "height": "6px",
                                          "borderRadius": "50%",
                                          "backgroundColor": (
                                              "var(--mantine-color-blue-5)"
                                          ),
                                      }
                                  ),
                                  dmc.Text(
                                      f"CANDIDATE (RUN #{challenger_run_id})",
                                      size="10px",
                                      fw=700,
                                      c="blue.7",
                                  ),
                                  view_chal_trial_anchor,
                                  view_chal_trace_anchor,
                              ],
                          ),
                          chal_trial_summary,
                      ],
                  ),
              ],
          ),
          # Footer - Collapsible Assertions
          assertion_diagnostic,
      ],
  )


def _render_trial_summary(trial, is_base: bool):
  """Renders a summary of a single trial for side-by-side comparison."""
  error_alert = None
  if trial.error_message:
    error_alert = dmc.Alert(
        dmc.Code(
            trial.error_message,
            block=True,
            style={
                "backgroundColor": "transparent",
                "padding": 0,
                "color": "inherit",
                "whiteSpace": "pre-wrap",
                "wordBreak": "break-all",
            },
        ),
        color="red",
        title="Trial Error",
        icon=DashIconify(icon="material-symbols:error-outline", width=18),
        mt="xs",
        styles={"message": {"paddingTop": 0}},
    )

  return dmc.Paper(
      p="md",
      radius="md",
      bg="var(--mantine-color-gray-0)" if is_base else "white",
      withBorder=not is_base,
      style={
          "borderColor": "var(--mantine-color-gray-2)",
      },
      children=[
          dmc.Text(
              trial.output_text,
              size="sm",
              style={
                  "fontFamily": "var(--font-mono)",
                  "lineHeight": "1.7",
                  "whiteSpace": "pre-wrap",
              },
          ),
          error_alert,
      ],
  )
