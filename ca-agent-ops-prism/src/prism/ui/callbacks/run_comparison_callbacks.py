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
from dash import dcc
from dash import Input
from dash import Output
from dash import State
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.client import get_client
from prism.common.schemas.execution import RunStatus
from prism.ui.components.assertion_components import get_assertion_style
from prism.ui.components.assertion_components import render_assertion_diagnostic_accordion
from prism.ui.components.cards import error_summary_line
from prism.ui.components.run_components import render_modern_context_diff
from prism.ui.ids import ComparisonIds
from prism.ui.models.comparison_state import RunComparisonUIState
from prism.ui.utils import format_timestamp
from prism.ui.utils import handle_errors
from prism.ui.utils import typed_callback
import pydantic

# The three statuses with a chip of their own. An errored pair, a case only one
# run has and a case that never ran fall under the Other chip. Without it they
# were counted by the All chip and by nothing else, so the breakdown under it
# added up to less than the total.
_BUCKETED_STATUSES = ("REGRESSION", "IMPROVED", "STABLE")

# Not a status the service returns. It is what the Other chip writes into the
# URL, and it selects everything the three buckets above leave out.
_OTHER_FILTER = "OTHER"

# What each chip puts in the URL, keyed by the id that was clicked. Read from
# the ids rather than matched against the "comp-filter-" prefix they share, so
# renaming one in ids.py cannot leave the gate silently matching nothing.
_FILTER_STATUS = {
    ComparisonIds.FILTER_ALL: None,
    ComparisonIds.FILTER_REGRESSIONS: "REGRESSION",
    ComparisonIds.FILTER_IMPROVEMENTS: "IMPROVED",
    ComparisonIds.FILTER_UNCHANGED: "STABLE",
    ComparisonIds.FILTER_OTHER: _OTHER_FILTER,
}


def _in_filter(status: Any, filter_status: str) -> bool:
  """Whether a case belongs under the chip the URL names."""
  if filter_status == _OTHER_FILTER:
    return status not in _BUCKETED_STATUSES
  return status == filter_status


def _render_accuracy_delta_bar(val: float):
  """Renders a horizontal bar for accuracy delta."""
  color = "green" if val >= 0 else "red"
  width = abs(val) * 100

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
  # The service returns the cases in test suite order, so they are plotted in
  # that order.
  max_abs_delta = max((abs(c.score_delta or 0.0) for c in cases), default=0.0)
  # Round the axis up to the next 5% so the labels stay readable.
  label_max = math.ceil(max_abs_delta / 0.05) * 0.05
  if label_max == 0:
    label_max = 0.05

  bars = []
  for case in cases:
    delta = case.score_delta or 0.0
    color = "green" if delta > 0 else "red" if delta < 0 else "gray"

    pct_height = (abs(delta) / label_max) * 50

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
                "minWidth": "6px",
                "height": "100%",
                "position": "relative",
                "cursor": "pointer",
            },
            children=[
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
                # The tooltip hangs off an invisible overlay filling the
                # column, so a thin bar is still hoverable.
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
          "overflow": "hidden",
      },
      children=[
          dmc.Box(
              style={
                  "display": "flex",
                  "flexDirection": "column",
                  "justifyContent": "space-between",
                  "height": "100%",
                  "paddingRight": "12px",
                  "borderRight": "1px solid var(--mantine-color-gray-2)",
              },
              children=[
                  dmc.Text(f"+{label_max:.0%}", size="xs", c="dimmed", fw=500),
                  dmc.Text("0%", size="xs", c="dimmed", fw=500),
                  dmc.Text(f"-{label_max:.0%}", size="xs", c="dimmed", fw=500),
              ],
          ),
          dmc.Box(
              style={
                  "flex": 1,
                  "height": "100%",
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
                      align="stretch",
                      style={"zIndex": 1, "width": "100%", "height": "100%"},
                      children=bars,
                      grow=True,
                  ),
              ],
          ),
      ],
  )


def _assertion_key(result: Any) -> tuple[str, int | None]:
  """Identifies one assertion across the two runs' snapshots of a suite."""
  # Each run snapshots the suite separately, so the snapshot ids differ.
  # original_assertion_id points back at the live row both were taken from.
  return (result.assertion.type, result.assertion.original_assertion_id)


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


def _kept_run_value(value: str | None, options: list[dict[str, str]]):
  """What to write into a run dropdown whose list has just been rebuilt.

  Opening the modal fills the suite and both runs from the URL in one write,
  and that write reaches populate_run_selects as a suite change. Clearing on
  every suite change therefore emptied the two runs the modal had just
  pre-filled, so the page someone was looking at could not be applied again. A
  value the rebuilt list still offers came from that pre-fill, not from the
  suite that was on screen before, and it stays.
  """
  if value and any(option["value"] == value for option in options):
    return dash.no_update
  return None


@typed_callback(
    inputs=[
        Input(ComparisonIds.LOC_URL, "search"),
        Input(ComparisonIds.FILTER_ALL, "n_clicks"),
        Input(ComparisonIds.FILTER_REGRESSIONS, "n_clicks"),
        Input(ComparisonIds.FILTER_IMPROVEMENTS, "n_clicks"),
        Input(ComparisonIds.FILTER_UNCHANGED, "n_clicks"),
        Input(ComparisonIds.FILTER_OTHER, "n_clicks"),
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
  clicked = trigger.split(".")[0]

  if clicked not in _FILTER_STATUS:
    return dash.no_update

  url_state = _parse_search(current_search)
  return (
      _build_search(
          url_state.base_run_id,
          url_state.challenger_run_id,
          url_state.suite_id,
          _FILTER_STATUS[clicked],
      ),
  )


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
      return dash.no_update
    new_search = _build_search(
        int(base_id), int(chal_id), int(suite_id) if suite_id else None
    )
    return False, new_search, dash.no_update, dash.no_update, dash.no_update

  if ComparisonIds.BTN_CLOSE_SELECT_RUNS in trigger:
    return False, dash.no_update, dash.no_update, dash.no_update, dash.no_update

  # Opening the modal: pre-populate it from the URL.
  url_state = _parse_search(current_search)
  suite_id = url_state.suite_id
  base_id = url_state.base_run_id
  chal_id = url_state.challenger_run_id

  if not suite_id and (base_id or chal_id):
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
  except pydantic.ValidationError:
    # A ValidationError is a ValueError, so the branch below used to render it.
    # str() on one prints the field paths and input_value=, which here is the
    # row the schema rejected, and a link to errors.pydantic.dev. A schema that
    # drifted from the table is a bug to log, not something to explain on the
    # page, so it goes to handle_errors for a toast and a reference.
    raise
  except ValueError as e:
    # Into COMPARISON_LIST, not METRICS_CARDS. METRICS_CARDS is a child of
    # SUMMARY_SECTION, which this same return hides, so the alert rendered
    # inside a hidden subtree and the page fell back to the "No runs selected"
    # empty state. A bookmarked /compare whose base run had been deleted looked
    # identical to /compare with no query string at all, while the URL still
    # named both runs. The empty state is hidden here for the same reason: it
    # invites a choice that has already been made.
    #
    # str(e) is our own ValueError ("Base run 12 not found"), raised by
    # ComparisonService, so it carries no query text or bound parameters.
    return (
        [],
        [dmc.Alert(str(e), color="red")],
        [],
        "CONTEXT DIFF",
        "gray",
        {"display": "none"},
        {"display": "none"},
        {"display": "none"},
        dash.no_update,
        [],
        [],
        [],
    )

  base_run = client.runs.get_run(state.base_run_id)
  chal_run = client.runs.get_run(state.challenger_run_id)
  context_diff = []
  badge_text = "CONTEXT DIFF"
  badge_color = "gray"

  if base_run and chal_run:
    base_snap = base_run.agent_context_snapshot or {}
    chal_snap = chal_run.agent_context_snapshot or {}

    diff_table, has_changes = render_modern_context_diff(base_snap, chal_snap)
    context_diff = [diff_table]

    if has_changes:
      badge_text = "Changes detected"
      badge_color = "orange"
    else:
      badge_text = "No changes detected"
      badge_color = "gray"

  delta = comparison.delta

  # Zero is neither direction, and each card used to fold it into one. Two runs
  # of an unchanged agent, which is the commonest comparison there is, read
  # "+0.0% Accuracy Gain" in green over "+0ms Faster" in green.
  if delta.accuracy_delta > 0:
    accuracy_icon = "material-symbols:trending-up"
    accuracy_color = "green"
    accuracy_caption = "Accuracy Gain"
  elif delta.accuracy_delta < 0:
    accuracy_icon = "material-symbols:trending-down"
    accuracy_color = "red"
    accuracy_caption = "Degradation"
  else:
    accuracy_icon = "material-symbols:trending-flat"
    accuracy_color = "gray"
    accuracy_caption = "No change"

  if delta.duration_delta_avg > 0:
    latency_color = "orange"
    latency_caption = "Slower"
  elif delta.duration_delta_avg < 0:
    latency_color = "green"
    latency_caption = "Faster"
  else:
    latency_color = "gray"
    latency_caption = "No change"

  metrics = [
      _render_metric_card(
          "Accuracy Delta",
          f"{delta.accuracy_delta:+.1%}",
          accuracy_icon,
          accuracy_color,
          accuracy_caption,
      ),
      _render_metric_card(
          "Avg Latency Delta",
          f"{delta.duration_delta_avg:+.0f}ms",
          "material-symbols:timer",
          latency_color,
          latency_caption,
      ),
      _render_metric_card(
          "Regressions",
          str(delta.regressions_count),
          "material-symbols:warning",
          "red" if delta.regressions_count > 0 else "gray",
          "Cases impacted",
      ),
      _render_metric_card(
          "Improvements",
          str(delta.improvements_count),
          "material-symbols:star",
          "green" if delta.improvements_count > 0 else "gray",
          "Cases improved",
      ),
  ]

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

  # Beside the header, not inside it. The header is a flex row of run pills,
  # so appending to its children laid the note out as a third pill: one line,
  # squeezed to whatever width was left, with its mt="md" doing nothing.
  subtitle_children = [subtitle]

  if delta.errors_count > 0:
    subtitle_children.append(
        dmc.Alert(
            # Latency and nothing else. An errored pair's score still counts
            # towards the accuracy delta. Only its duration is dropped: a
            # trial that died on its first event is not a speed-up.
            f"Note: {delta.errors_count} failed trial(s) were excluded from"
            " latency calculations.",
            color="orange",
            variant="light",
            radius="md",
            mt="md",
            icon=DashIconify(icon="material-symbols:info-outline", width=18),
        )
    )

  assertion_deltas: dict[str, list[float]] = {}
  for case in comparison.cases:
    if not case.base_trial or not case.challenger_trial:
      continue
    # Pair per assertion, then bucket the delta by type for display. Keying
    # the pairing by type alone collapsed a case that has two assertions of
    # the same type down to the last one, and the other delta disappeared.
    base_scores = {
        _assertion_key(ar): ar.score for ar in case.base_trial.assertion_results
    }
    for ar in case.challenger_trial.assertion_results:
      key = _assertion_key(ar)
      if key in base_scores:
        assertion_deltas.setdefault(ar.assertion.type, []).append(
            ar.score - base_scores[key]
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

  cases = comparison.cases
  active = state.filter_status

  regressed_count = len([c for c in cases if c.status == "REGRESSION"])
  improved_count = len([c for c in cases if c.status == "IMPROVED"])
  unchanged_count = len([c for c in cases if c.status == "STABLE"])
  # The chips read as a breakdown of the number on the All chip, so they have
  # to add up to it. An errored pair, a case only one run has and a case that
  # never ran had no chip of their own, so a comparison over an edited suite
  # showed "All 12" above four chips totalling 9, and those three cases were
  # reachable under All and nowhere else.
  other_count = len([c for c in cases if c.status not in _BUCKETED_STATUSES])

  filter_bar = dmc.Group(
      mt="xl",
      mb="md",
      justify="space-between",
      children=[
          dmc.Text("Trials", fw=700, size="lg"),
          dmc.Group(
              gap="xs",
              p=4,
              bg="gray.1",
              style={"borderRadius": "var(--mantine-radius-md)"},
              children=[
                  _render_filter_chip(
                      ComparisonIds.FILTER_ALL,
                      "All",
                      comparison.metadata.total_cases,
                      accent="dark",
                      badge_color="dark",
                      active=not active,
                  ),
                  _render_filter_chip(
                      ComparisonIds.FILTER_REGRESSIONS,
                      "Regressed",
                      regressed_count,
                      accent="red",
                      badge_color="red",
                      active=active == "REGRESSION",
                  ),
                  _render_filter_chip(
                      ComparisonIds.FILTER_IMPROVEMENTS,
                      "Improved",
                      improved_count,
                      accent="green",
                      badge_color="green",
                      active=active == "IMPROVED",
                  ),
                  _render_filter_chip(
                      ComparisonIds.FILTER_UNCHANGED,
                      "Unchanged",
                      unchanged_count,
                      accent="dark",
                      badge_color="gray",
                      active=active == "STABLE",
                  ),
                  _render_filter_chip(
                      ComparisonIds.FILTER_OTHER,
                      "Other",
                      other_count,
                      accent="dark",
                      badge_color="gray",
                      active=active == _OTHER_FILTER,
                  ),
              ],
          ),
      ],
  )

  if active:
    cases = [c for c in cases if _in_filter(c.status, active)]

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
      subtitle_children,
      _render_performance_delta_chart(comparison.cases),
      assertion_delta_elements,
      filter_bar,
  )


# The one raw dash.callback of the 120. Only the two value outputs are written
# by another callback as well, and typed_callback's allow_duplicate goes on
# every output it is given, so it cannot express that. Writing the flag per
# output means writing handle_errors by hand too, and it has to go below the
# registration: decorators apply bottom-up, so one stacked above dash.callback
# wraps an object Dash never calls.
@dash.callback(
    Output(ComparisonIds.SUITE_SELECT, "data"),
    Output(ComparisonIds.BASE_RUN_SELECT, "data"),
    Output(ComparisonIds.CHALLENGE_RUN_SELECT, "data"),
    Output(ComparisonIds.BASE_RUN_SELECT, "value", allow_duplicate=True),
    Output(ComparisonIds.CHALLENGE_RUN_SELECT, "value", allow_duplicate=True),
    Input(ComparisonIds.LOC_URL, "pathname"),
    Input(ComparisonIds.SUITE_SELECT, "value"),
    State(ComparisonIds.LOC_URL, "search"),
    State(ComparisonIds.BASE_RUN_SELECT, "value"),
    State(ComparisonIds.CHALLENGE_RUN_SELECT, "value"),
    prevent_initial_call="initial_duplicate",
)
@handle_errors
def populate_run_selects(
    pathname: str | None,
    selected_suite_id: str | None,
    search: str | None,
    base_selected: str | None,
    chal_selected: str | None,
):
  """Populates the run selection dropdowns."""
  if not pathname or pathname != "/compare":
    return (
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
        dash.no_update,
    )

  # Changing the suite rewrites both run lists and used to leave the two
  # values pointing at runs of the suite that was on screen before. The
  # fields render blank, because the values are not in the data, but Apply
  # reads them as State and built ?base=<old suite run>&suite=<new suite>.
  # Only the suite dropdown clears them. On the load path the values are the
  # URL pre-fill, which is the whole selection.
  suite_changed = dash.callback_context.triggered_id == (
      ComparisonIds.SUITE_SELECT
  )

  state = _parse_search(search)
  required_ids = {state.base_run_id, state.challenger_run_id} - {None}

  client = get_client()

  suites = client.runs.get_unique_suites_from_snapshots()
  suite_options = [
      {"label": s["name"], "value": str(s["original_suite_id"])} for s in suites
  ]

  # The dropdown wins, then the URL, then the suite the two runs came from.
  suite_to_use = selected_suite_id or (
      str(state.suite_id) if state.suite_id else None
  )

  if not suite_to_use and required_ids:
    for run_id in required_ids:
      run = client.runs.get_run(run_id)
      if run and run.original_suite_id:
        suite_to_use = str(run.original_suite_id)
        break

  runs = []
  if suite_to_use:
    runs = client.runs.list_runs(original_suite_id=int(suite_to_use), limit=50)

    # A run named in the URL can be older than the 50 this fetched, so it has
    # to be fetched by id.
    existing_ids = {r.id for r in runs}
    for run_id in required_ids:
      if run_id not in existing_ids:
        run = client.runs.get_run(run_id)
        if run and run.original_suite_id == int(suite_to_use):
          runs.append(run)

    # Required runs appended above land at the end, so re-sort by recency.
    runs.sort(key=lambda r: r.created_at, reverse=True)

  run_options = [
      {
          "value": str(r.id),
          "label": f"Run #{r.id} ({format_timestamp(r.created_at)})",
      }
      for r in runs
  ]

  base_value = dash.no_update
  chal_value = dash.no_update
  if suite_changed:
    base_value = _kept_run_value(base_selected, run_options)
    chal_value = _kept_run_value(chal_selected, run_options)

  return suite_options, run_options, run_options, base_value, chal_value


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


def _render_filter_chip(
    chip_id: str,
    label: str,
    count: int,
    *,
    accent: str,
    badge_color: str,
    active: bool,
):
  """Renders one chip of the filter bar.

  The chips differ only in their two colors and in what makes them the active
  one. The bar was four copies of this, and a copy carrying its neighbor's
  count reads as a real count.
  """
  return dmc.Button(
      dmc.Group(
          gap=8,
          children=[
              dmc.Text(
                  label,
                  size="sm",
                  fw=500,
                  c=accent if active else "gray.7",
              ),
              dmc.Badge(
                  str(count),
                  size="xs",
                  variant="light",
                  color=badge_color,
                  radius="sm",
              ),
          ],
      ),
      id=chip_id,
      variant="filled" if active else "subtle",
      color=accent if active else "gray",
      bg="white" if active else "transparent",
      size="xs",
      radius="sm",
      style={"boxShadow": "var(--mantine-shadow-xs)" if active else "none"},
  )


def _render_comparison_row(case, base_run_id, challenger_run_id):
  """Renders a single comparison row (case)."""
  color = "gray"
  status_label = case.status.value
  if case.status == "REGRESSION":
    color = "red"
  elif case.status == "IMPROVED":
    color = "green"
  elif case.status == "ERROR":
    color = "orange"
  elif case.status == "NEW":
    color = "blue"
    status_label = "ADDED"
  elif case.status == "NOT_RUN":
    status_label = "NOT RUN"

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

  # NOT_RUN sits with the one-sided cases: the trial that never ran has no
  # score, and the 0% the arrow would show reads as an answer that scored
  # nothing.
  one_sided = case.status in ["NEW", "REMOVED", "NOT_RUN"]

  # The same reasoning as the accuracy column, which the latency column used to
  # ignore. duration_delta is None for these, and `or 0` printed "+0ms" in
  # gray, which reads as two runs that took the same time.
  if one_sided:
    latency_content = dmc.Text(
        "N/A",
        size="sm",
        fw=700,
        c="dimmed",
        style={"fontFamily": "var(--font-mono)"},
    )
  else:
    latency_content = dmc.Text(
        f"{latency_delta:+}ms",
        size="sm",
        fw=700,
        c=latency_color,
        style={"fontFamily": "var(--font-mono)"},
    )

  if one_sided:
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
                                  dmc.Group(
                                      gap=4,
                                      mt="sm",
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
                                              "TEST CASE",
                                              size="10px",
                                              fw=700,
                                              c="blue.7",
                                          ),
                                      ],
                                  ),
                                  dmc.Text(
                                      case.question,
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
                                          latency_content,
                                      ],
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          ),
          dmc.Grid(
              gutter=0,
              style={"borderTop": "1px solid var(--mantine-color-gray-1)"},
              children=[
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
          # None when neither trial has assertion results, which Dash renders
          # as nothing.
          assertion_diagnostic,
      ],
  )


def _render_trial_summary(trial, is_base: bool):
  """Renders a summary of a single trial for side-by-side comparison."""
  error_alert = None
  if trial.error_message:
    # The same line the trial page shows. This rendered the stored message
    # whole, so a comparison was the one page left that still printed
    # whatever a writer put after the first line.
    error_alert = dmc.Alert(
        error_summary_line(trial.error_message),
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
          dcc.Markdown(
              trial.output_text or "No output available.",
              style={
                  "fontFamily": "var(--font-mono)",
                  "lineHeight": "1.7",
                  "fontSize": "14px",
                  "wordBreak": "break-word",
              },
          ),
          error_alert,
      ],
  )
