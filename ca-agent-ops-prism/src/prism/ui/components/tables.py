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

"""Reusable table components."""

from typing import Any

from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common.schemas.execution import RunHistoryPoint
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatsSchema
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.execution import Trial
from prism.common.schemas.suite import SuiteWithStats
from prism.ui import utils
from prism.ui.components import badges
from prism.ui.components import links
from prism.ui.ids import EvaluationIds


def _render_archived_badge(is_archived: bool) -> dmc.Badge | None:
  """Renders an 'Archived' badge if the item is archived."""
  if not is_archived:
    return None
  return dmc.Badge(
      "Archived",
      variant="filled",
      color="gray",
      size="xs",
      radius="md",
      style={"flexShrink": 0},
      styles={"label": {"overflow": "visible"}},
  )


def _render_scheduled_badge(run: RunSchema) -> dmc.Tooltip | None:
  """Renders a clickable Scheduled badge when a run came from a schedule."""
  schedule_id = getattr(run, "schedule_id", None)
  if schedule_id is None:
    return None
  schedule_name = (
      getattr(run, "schedule_name", None) or f"Schedule #{schedule_id}"
  )
  filter_href = f"/evaluations?schedule_id={schedule_id}"
  return dmc.Tooltip(
      label=f"Triggered by schedule: {schedule_name}",
      withArrow=True,
      children=dmc.Anchor(
          dmc.Badge(
              "Scheduled",
              variant="light",
              color="indigo",
              size="xs",
              radius="md",
              leftSection=DashIconify(
                  icon="material-symbols:schedule", width=11
              ),
              style={"flexShrink": 0},
              styles={"label": {"overflow": "visible"}},
          ),
          href=filter_href,
          underline=False,
      ),
  )


_RUN_TABLE_COLUMNS: tuple[tuple[str | None, str, str, dict[str, Any]], ...] = (
    ("id", "RUN ID", "Run ID", {"width": "180px", "whiteSpace": "nowrap"}),
    ("agent", "AGENT", "Agent", {}),
    ("suite", "TEST SUITE", "Test Suite", {}),
    ("status", "STATUS", "Status", {}),
    ("accuracy", "ACCURACY", "Accuracy", {}),
    ("duration", "DURATION", "Duration", {}),
    ("started", "STARTED", "Started", {}),
    (None, "ACTION", "Action", {"textAlign": "right"}),
)


def _render_run_table_header(
    col_key: str | None,
    label: str,
    accessible_label: str,
    extra_style: dict[str, Any],
    *,
    sortable: bool,
    sort_by: str | None,
    sort_dir: str,
) -> html.Th:
  """Renders a run table header cell, optionally as a clickable sort button."""
  th_style: dict[str, Any] = {
      "fontSize": "11px",
      "fontWeight": 600,
      "color": "var(--mantine-color-gray-5)",
      "letterSpacing": "0.05em",
      "padding": "16px 24px",
      "textAlign": "left",
      **extra_style,
  }
  if not sortable or col_key is None:
    return html.Th(label, style=th_style)

  is_active = col_key == sort_by
  if is_active:
    aria_sort = "ascending" if sort_dir == "asc" else "descending"
    indicator = "▲" if sort_dir == "asc" else "▼"
    btn_color = "var(--mantine-color-blue-7)"
    btn_weight = 700
  else:
    aria_sort = "none"
    indicator = None
    btn_color = "var(--mantine-color-gray-6)"
    btn_weight = 600

  btn_children: list[Any] = [html.Span(label)]
  if indicator is not None:
    btn_children.append(
        html.Span(
            indicator,
            style={"fontSize": "10px", "lineHeight": 1},
            **{"aria-hidden": "true"},
        )
    )

  button = dmc.UnstyledButton(
      id={"type": EvaluationIds.BTN_SORT_COLUMN, "index": col_key},
      **{"aria-label": f"Sort by {accessible_label}"},
      style={
          "display": "inline-flex",
          "alignItems": "center",
          "gap": "4px",
          "cursor": "pointer",
          "fontSize": "11px",
          "fontWeight": btn_weight,
          "color": btn_color,
          "letterSpacing": "0.05em",
          "textTransform": "uppercase",
      },
      children=btn_children,
  )
  return html.Th(button, style=th_style, **{"aria-sort": aria_sort})


def render_run_table(
    runs: list[RunSchema],
    agent_names: dict[int, str] | None = None,
    suite_names: dict[int, str] | None = None,
    table_id: str | None = None,
    sortable: bool = False,
    sort_by: str | None = None,
    sort_dir: str = "desc",
) -> dmc.Paper:
  """Renders a stylistic table of evaluation runs.

  Args:
    runs: List of runs to display.
    agent_names: Map of agent_id to agent_name.
    suite_names: Map of suite_id to suite_name.
    table_id: Optional ID for the container.
    sortable: Whether column headers render sort controls.
    sort_by: Active sort column key, if any.
    sort_dir: Active sort direction ("asc" or "desc").

  Returns:
    A dmc.Paper component wrapping the table.
  """
  agent_names = agent_names or {}
  suite_names = suite_names or {}

  rows = []
  for run in runs:
    status_color, status_label = utils.run_status_display(run.status)

    # When the run picked up a worker, not when it was queued. The two differ
    # by however long the queue was, and it was the queued time on screen.
    # "2 hr ago" is no use for lining a run up against a deploy either, so this
    # is the timestamp.
    started_str = (
        utils.format_timestamp(run.started_at) if run.started_at else "--"
    )

    if run.duration_ms:
      duration_str = utils.format_duration(run.duration_ms)
    elif run.status == RunStatus.RUNNING:
      duration_str = "Running..."
    else:
      # duration_ms stays None until completed_at is set, so a paused run and a
      # run nothing has picked up yet have no duration to show. The status is
      # the only thing left to say about them.
      duration_str = status_label

    score_content = dmc.Text("N/A", size="sm", c="dimmed")
    if run.status == RunStatus.COMPLETED and run.accuracy is not None:
      score_pct = run.accuracy * 100
      if score_pct >= 90:
        score_bar_color = "green"
      elif score_pct >= 70:
        score_bar_color = "yellow"
      else:
        score_bar_color = "red"

      score_content = dmc.Group(
          [
              dmc.Progress(
                  value=int(score_pct),
                  color=score_bar_color,
                  size="sm",
                  radius="md",
                  w=60,
              ),
              dmc.Text(f"{score_pct:.1f}%", size="sm", fw=700),
          ],
          gap="xs",
      )
    elif run.status == RunStatus.RUNNING:
      score_content = dmc.Text(
          "Calculating...", size="sm", c="dimmed", style={"fontStyle": "italic"}
      )

    action_label = "View Report"

    agent_name = (
        getattr(run, "agent_name", None)
        or agent_names.get(run.agent_id)
        or f"Agent {run.agent_id}"
    )
    suite_name = (
        getattr(run, "suite_name", None)
        or suite_names.get(run.test_suite_snapshot_id)
        or f"Suite {run.test_suite_snapshot_id}"
    )

    row = html.Tr(
        children=[
            # Run ID
            html.Td(
                dmc.Group(
                    gap="xs",
                    wrap="nowrap",
                    children=[
                        dmc.Text(
                            f"#{run.id}", size="sm", c="dimmed", ff="monospace"
                        ),
                        _render_scheduled_badge(run),
                        _render_archived_badge(
                            getattr(run, "is_archived", False)
                        ),
                    ],
                ),
                style={"padding": "16px 24px", "whiteSpace": "nowrap"},
            ),
            # Agent
            html.Td(
                links.render_agent_link(run.agent_id, agent_name),
                style={"padding": "16px 24px"},
            ),
            # Test Suite
            html.Td(
                links.render_test_suite_link(run.original_suite_id, suite_name),
                style={"padding": "16px 24px"},
            ),
            # Status
            html.Td(
                badges.render_status_badge(status_label, status_color),
                style={"padding": "16px 24px", "whiteSpace": "nowrap"},
            ),
            # Accuracy
            html.Td(score_content, style={"padding": "16px 24px"}),
            # Duration
            html.Td(
                dmc.Text(duration_str, size="sm", c="dimmed"),
                style={"padding": "16px 24px"},
            ),
            # Started
            html.Td(
                dmc.Text(started_str, size="sm", c="dimmed"),
                style={"padding": "16px 24px"},
            ),
            # Action
            html.Td(
                dmc.Anchor(
                    dmc.Button(
                        action_label,
                        variant="light",
                        color="blue",
                        size="xs",
                        radius="md",
                    ),
                    href=f"/evaluations/runs/{run.id}",
                    underline=False,
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
        ],
    )
    rows.append(row)

  children = []
  if not runs:
    children.append(
        dmc.Text("No runs found.", c="dimmed", size="sm", ta="center", py="xl")
    )
  else:
    table_head = html.Thead(
        html.Tr(
            [
                _render_run_table_header(
                    col_key,
                    label,
                    accessible_label,
                    extra_style,
                    sortable=sortable,
                    sort_by=sort_by,
                    sort_dir=sort_dir,
                )
                for col_key, label, accessible_label, extra_style in (
                    _RUN_TABLE_COLUMNS
                )
            ],
            style={
                "backgroundColor": "var(--mantine-color-gray-0)",
                "borderBottom": "1px solid var(--mantine-color-gray-2)",
            },
        )
    )

    children.append(
        html.Div(
            dmc.Table(
                children=[table_head, html.Tbody(rows)],
                verticalSpacing=0,
                horizontalSpacing=0,
                highlightOnHover=True,
                withTableBorder=False,
                style={"minWidth": "800px"},
            ),
            style={"overflowX": "auto"},
        )
    )

  kwargs = {"style": {"width": "100%"}}
  if table_id:
    kwargs["id"] = table_id

  return dmc.Paper(
      html.Div(children=children, **kwargs),
      withBorder=False,
      radius=0,
      style={"overflow": "hidden"},
  )


def render_trial_table(
    trials: list[Trial],
) -> dmc.Paper:
  """Renders a table of trials."""
  rows = []

  for trial in trials:
    status_color, status_label = utils.run_status_display(trial.status)

    duration_str = utils.format_duration(trial.duration_ms)
    ttfr_str = utils.format_ttfr(trial.ttfr_ms)

    accuracy_str = "N/A"
    if trial.score is not None:
      accuracy_str = f"{trial.score * 100:.1f}%"

    test_case_text = trial.question or "Unknown"

    is_terminal = trial.status in (
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.CANCELLED,
    )

    action_cell = html.Td("", style={"padding": "16px 24px"})
    if is_terminal:
      action_cell = html.Td(
          dmc.Anchor(
              dmc.Button(
                  "View Details",
                  variant="light",
                  color="blue",
                  size="xs",
                  radius="md",
              ),
              href=f"/evaluations/trials/{trial.id}",
              underline=False,
          ),
          style={"textAlign": "right", "padding": "16px 24px"},
      )

    row = html.Tr(
        children=[
            # Test Case
            html.Td(
                html.Div(
                    dmc.Text(
                        test_case_text,
                        size="sm",
                        fw=500,
                        c="dark",
                        truncate="end",
                    ),
                    style={
                        "maxWidth": "400px",
                        "whiteSpace": "nowrap",
                        "overflow": "hidden",
                        "textOverflow": "ellipsis",
                    },
                    title=test_case_text,
                ),
                style={"padding": "16px 24px"},
            ),
            # Status
            html.Td(
                badges.render_status_badge(status_label, status_color),
                style={"padding": "16px 24px"},
            ),
            # Accuracy
            html.Td(
                dmc.Text(
                    accuracy_str, size="sm", fw=500, c="dark", ff="monospace"
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
            # TTFR
            html.Td(
                dmc.Text(ttfr_str, size="sm", c="dimmed", ff="monospace"),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
            # Duration
            html.Td(
                dmc.Text(duration_str, size="sm", c="dimmed", ff="monospace"),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
            # Action
            action_cell,
        ]
    )
    rows.append(row)

  table_head = html.Thead(
      html.Tr(
          [
              html.Th(
                  "TEST CASE",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                  },
              ),
              html.Th(
                  "STATUS",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                      "width": "140px",
                  },
              ),
              html.Th(
                  "ACCURACY",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "120px",
                  },
              ),
              html.Th(
                  "TTFR",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "100px",
                  },
              ),
              html.Th(
                  "DURATION",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "120px",
                  },
              ),
              html.Th(
                  "ACTIONS",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "120px",
                  },
              ),
          ],
          style={
              "backgroundColor": "var(--mantine-color-gray-0)",
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
          },
      )
  )

  return dmc.Paper(
      html.Div(
          dmc.Table(
              children=[table_head, html.Tbody(rows)],
              verticalSpacing=0,
              horizontalSpacing=0,
              highlightOnHover=True,
              withTableBorder=False,
              style={"minWidth": "800px"},
          ),
          style={"overflowX": "auto", "width": "100%"},
      ),
      withBorder=False,
      radius=0,
      style={"overflow": "hidden"},
  )


def render_test_suite_table(
    suites: list[SuiteWithStats],
) -> dmc.Paper:
  """Renders a stylistic table of test suites."""

  rows = []
  for s in suites:
    coverage_color, coverage_label = utils.coverage_display(
        s.question_count, s.assertion_coverage
    )

    row = html.Tr(
        children=[
            # Test Suite Name
            html.Td(
                dmc.Group(
                    gap="xs",
                    children=[
                        links.render_test_suite_link(s.suite.id, s.suite.name),
                        _render_archived_badge(
                            getattr(s.suite, "is_archived", False)
                        ),
                    ],
                ),
                style={"padding": "16px 24px"},
            ),
            # Description
            html.Td(
                dmc.Text(
                    s.suite.description or "No description provided",
                    size="sm",
                    c="dimmed",
                    lineClamp=1,
                ),
                style={"padding": "16px 24px"},
            ),
            # Questions
            html.Td(
                dmc.Text(
                    str(s.question_count),
                    size="sm",
                    fw=500,
                    c="dark",
                    ff="monospace",
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
            # Coverage
            html.Td(
                dmc.Group(
                    badges.render_coverage_badge(
                        coverage_label, coverage_color
                    ),
                    justify="flex-end",
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
            # Runs
            html.Td(
                dmc.Text(
                    str(s.run_count),
                    size="sm",
                    fw=500,
                    c="dark",
                    ff="monospace",
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
            # Action
            html.Td(
                dmc.Anchor(
                    dmc.Button(
                        "View Details",
                        variant="light",
                        color="blue",
                        size="xs",
                        radius="md",
                    ),
                    href=f"/test_suites/view/{s.suite.id}",
                    underline=False,
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
        ]
    )
    rows.append(row)

  table_head = html.Thead(
      html.Tr(
          [
              html.Th(
                  "TEST SUITE",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                      "width": "300px",
                  },
              ),
              html.Th(
                  "DESCRIPTION",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                  },
              ),
              html.Th(
                  "TEST CASES",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "160px",
                      "whiteSpace": "nowrap",
                  },
              ),
              html.Th(
                  "COVERAGE",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "180px",
                  },
              ),
              html.Th(
                  "RUNS",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "100px",
                  },
              ),
              html.Th(
                  "ACTIONS",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "140px",
                  },
              ),
          ],
          style={
              "backgroundColor": "var(--mantine-color-gray-0)",
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
          },
      )
  )

  return dmc.Paper(
      html.Div(
          dmc.Table(
              children=[table_head, html.Tbody(rows)],
              verticalSpacing=0,
              horizontalSpacing=0,
              highlightOnHover=True,
              withTableBorder=False,
              w="100%",
              style={"minWidth": "800px"},
          ),
          style={"overflowX": "auto"},
      ),
      withBorder=False,
      radius=0,
      style={"overflow": "hidden"},
  )


def render_agent_table(
    agents: list[Any],
    latest_runs: dict[int, RunStatsSchema],
    run_history: dict[int, list[RunHistoryPoint]],
) -> dmc.Paper:
  """Renders a table of agents with stats and history."""
  rows = []
  for agent in agents:
    is_looker = False
    source_label = "BQ"

    config = getattr(agent, "config", None)
    datasource = None

    if config and hasattr(config, "datasource"):
      datasource = config.datasource
    elif hasattr(agent, "datasource_config"):
      datasource = agent.datasource_config

    if datasource:
      if hasattr(datasource, "model_dump"):
        ds_dict = datasource.model_dump()
      elif isinstance(datasource, dict):
        ds_dict = datasource
      else:
        ds_dict = {}

      if "instance_uri" in ds_dict or "looker_instance_uri" in ds_dict:
        is_looker = True
        source_label = "LOOKER"

    source_color = "indigo" if is_looker else "blue"

    stats_schema = latest_runs.get(agent.id)
    latest_run = stats_schema.run if stats_schema else None
    accuracy = stats_schema.accuracy if stats_schema else None

    if latest_run:
      # It used to render the UTC clock as if it were local, and it left
      # the year off.
      date_str = utils.format_timestamp(latest_run.created_at)
      # An accuracy of None is a run that has scored nothing yet, not a run
      # that scored zero. The latest run is the newest one whatever its status,
      # so starting an evaluation used to put 0.0% next to today's date, as if
      # the agent had just failed everything.
      acc_str = f"{accuracy*100:.1f}%" if accuracy is not None else "--"
    else:
      date_str = "No evaluations yet"
      acc_str = "-"

    history_points = run_history.get(agent.id, [])
    # A run with no accuracy has nothing to plot. Drawn as 0.0 it read as a
    # run that had failed everything, and one queued run at the end of the
    # window was enough to turn the whole trend red.
    spark_data = [
        h.accuracy * 100 for h in history_points if h.accuracy is not None
    ]

    if not spark_data:
      history_component = dmc.Text("-", size="xs", c="dimmed")
    else:
      history_component = dmc.Sparkline(
          data=spark_data,
          w=120,
          h=40,
          curveType="monotone",
          color="green",
          fillOpacity=0.2,
          trendColors={
              "positive": "green",
              "negative": "red",
              "neutral": "gray",
          },
      )

    if latest_run:
      last_eval_content = dmc.Group(
          gap="xs",
          children=[
              dmc.Text(
                  acc_str,
                  fw=700,
                  size="sm",
                  c="dark",
              ),
              dmc.Text(
                  date_str,
                  size="xs",
                  c="dimmed",
              ),
          ],
      )
    else:
      last_eval_content = dmc.Text("Never", size="xs", c="dimmed")

    row = html.Tr(
        children=[
            # Agent Name
            html.Td(
                dmc.Group(
                    gap="xs",
                    children=[
                        links.render_agent_link(
                            agent.id,
                            agent.name
                            or getattr(agent, "agent_resource_id", None)
                            or f"Agent {agent.id}",
                        ),
                        _render_archived_badge(
                            getattr(agent, "is_archived", False)
                        ),
                    ],
                ),
                style={"padding": "16px 24px"},
            ),
            # Source
            html.Td(
                dmc.Badge(
                    source_label,
                    variant="light",
                    color=source_color,
                    size="sm",
                    radius="md",
                ),
                style={"padding": "16px 24px"},
            ),
            # Last Evaluation (Date + Accuracy)
            html.Td(
                last_eval_content,
                style={"padding": "16px 24px"},
            ),
            # History
            html.Td(
                history_component,
                style={"padding": "16px 24px"},
            ),
            # Actions
            html.Td(
                dmc.Anchor(
                    dmc.Button(
                        "View Details",
                        variant="light",
                        color="blue",
                        size="xs",
                        radius="md",
                    ),
                    href=f"/agents/view/{agent.id}",
                    underline=False,
                ),
                style={"textAlign": "right", "padding": "16px 24px"},
            ),
        ]
    )
    rows.append(row)

  table_head = html.Thead(
      html.Tr(
          [
              html.Th(
                  "AGENT",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                  },
              ),
              html.Th(
                  "DATASOURCE",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                      "width": "150px",
                  },
              ),
              html.Th(
                  "LAST EVALUATION",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                      "width": "200px",
                  },
              ),
              html.Th(
                  "HISTORY",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "left",
                      "width": "150px",
                  },
              ),
              html.Th(
                  "ACTIONS",
                  style={
                      "fontSize": "11px",
                      "fontWeight": 600,
                      "color": "var(--mantine-color-gray-5)",
                      "letterSpacing": "0.05em",
                      "padding": "16px 24px",
                      "textAlign": "right",
                      "width": "120px",
                  },
              ),
          ],
          style={
              "backgroundColor": "var(--mantine-color-gray-0)",
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
          },
      )
  )

  return dmc.Paper(
      html.Div(
          dmc.Table(
              children=[table_head, html.Tbody(rows)],
              verticalSpacing=0,
              horizontalSpacing=0,
              highlightOnHover=True,
              withTableBorder=False,
              w="100%",
              style={"minWidth": "800px"},
          ),
          style={"overflowX": "auto"},
      ),
      withBorder=False,
      radius=0,
      style={"overflow": "hidden"},
  )
