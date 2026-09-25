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

"""Reusable dashboard components for Agent Detail page."""

import hashlib
from typing import Any
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui import utils
from prism.ui.components import links
from prism.ui.components.badges import render_status_badge
from prism.ui.pages.agent_ids import AgentIds


def get_suite_color(suite_name: str, index: int | None = None) -> str:
  """Returns a consistent color for a test suite name."""
  colors = ["violet", "blue", "teal", "lime", "orange", "red", "pink"]
  if index is not None:
    return f"{colors[index % len(colors)]}.6"

  # Every caller passes an index from a sorted list. The hash keeps the
  # colour stable for any that does not.
  h = int(hashlib.md5(suite_name.encode()).hexdigest(), 16)
  return f"{colors[h % len(colors)]}.6"


def render_evaluation_chart(
    daily_accuracy: list[dict[str, Any]],
    suites: list[str] | None = None,
    dropdown_id: str | None = None,
    container_id: str | None = None,
    selected_days: str = "Last 30 Days",
) -> dmc.Paper:
  """Renders the Evaluation Accuracy chart."""
  if not daily_accuracy:
    return dmc.Paper(
        withBorder=True,
        p="lg",
        radius="md",
        children=dmc.Text("No data available", c="dimmed"),
        **({"id": container_id} if container_id else {}),
    )

  series = []
  if suites:
    sorted_suites = sorted(suites)
    for i, ds in enumerate(sorted_suites):
      series.append({
          "name": ds,
          "color": get_suite_color(ds, i),
          "label": ds,
      })
  else:
    series = [{"name": "accuracy", "color": "violet.6", "label": "Accuracy"}]

  processed_data = []
  for item in daily_accuracy:
    new_item = item.copy()
    for k, v in new_item.items():
      if k != "date" and isinstance(v, (int, float)):
        new_item[k] = round(v * 100, 1)
    processed_data.append(new_item)

  dropdown = None
  if dropdown_id:
    dropdown = dmc.Select(
        id=dropdown_id,
        data=["Last 30 Days", "Last 7 Days"],
        value=selected_days,
        size="sm",
        w=150,
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      children=[
          dmc.Group(
              justify="space-between",
              mb="lg",
              children=[
                  dmc.Stack(
                      gap=0,
                      children=[
                          dmc.Text("Evaluation Accuracies", fw=700, size="lg"),
                          dmc.Text(
                              "Performance trend over time",
                              c="dimmed",
                              size="sm",
                              mb="sm" if suites else 0,
                          ),
                      ],
                  ),
                  dropdown,
              ],
          ),
          html.Div(
              children=[
                  dmc.AreaChart(
                      h=300,
                      data=processed_data,
                      dataKey="date",
                      series=series,
                      curveType="monotone",
                      tickLine="xy",
                      gridAxis="xy",
                      withGradient=True,
                      withDots=True,
                      withLegend=bool(suites),
                      unit="%",
                      areaProps={
                          "isAnimationActive": True,
                          "animationDuration": 1000,
                          "animationEasing": "ease-in-out",
                      },
                  ),
              ],
              **({"id": container_id} if container_id else {}),
          ),
      ],
  )


def render_run_volume_chart(
    run_history: list[dict[str, Any]],
) -> dmc.Paper:
  """Renders the Run Volume bar chart."""
  if not run_history:
    return dmc.Paper(
        withBorder=True,
        p="lg",
        radius="md",
        children=dmc.Text("No data available", c="dimmed"),
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      children=[
          dmc.Stack(
              gap=0,
              mb="lg",
              children=[
                  dmc.Text("Evaluation Volume", fw=700, size="lg"),
                  dmc.Text(
                      "Number of runs per day",
                      c="dimmed",
                      size="sm",
                  ),
              ],
          ),
          dmc.BarChart(
              h=300,
              data=run_history,
              dataKey="date",
              series=[{"name": "count", "color": "blue.6", "label": "Runs"}],
              tickLine="xy",
              gridAxis="xy",
              withLegend=False,
              barProps={
                  "isAnimationActive": True,
                  "animationDuration": 1000,
              },
          ),
      ],
  )


def render_duration_chart(
    daily_duration: list[dict[str, Any]],
    suites: list[str] | None = None,
    dropdown_id: str | None = None,
    container_id: str | None = None,
    selected_days: str = "Last 30 Days",
) -> dmc.Paper:
  """Renders the Duration Trend chart."""
  if not daily_duration:
    return dmc.Paper(
        withBorder=True,
        p="lg",
        radius="md",
        children=dmc.Text("No duration data available", c="dimmed"),
        **({"id": container_id} if container_id else {}),
    )

  series = []
  if suites:
    sorted_suites = sorted(suites)
    for i, ds in enumerate(sorted_suites):
      series.append({
          "name": ds,
          "color": get_suite_color(ds, i),
          "label": ds,
      })
  else:
    series = [{"name": "duration", "color": "teal.6", "label": "Duration (ms)"}]

  dropdown = None
  if dropdown_id:
    dropdown = dmc.Select(
        id=dropdown_id,
        data=["Last 30 Days", "Last 7 Days"],
        value=selected_days,
        size="sm",
        w=150,
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      children=[
          dmc.Group(
              justify="space-between",
              mb="lg",
              children=[
                  dmc.Stack(
                      gap=0,
                      children=[
                          dmc.Text("Duration Trends", fw=700, size="lg"),
                          dmc.Text(
                              "Average execution time per test suite",
                              c="dimmed",
                              size="sm",
                          ),
                      ],
                  ),
                  dropdown,
              ],
          ),
          html.Div(
              children=[
                  dmc.AreaChart(
                      h=300,
                      data=daily_duration,
                      dataKey="date",
                      series=series,
                      curveType="monotone",
                      tickLine="xy",
                      gridAxis="xy",
                      withGradient=True,
                      withDots=True,
                      withLegend=bool(suites),
                      unit="ms",
                      areaProps={
                          "isAnimationActive": True,
                          "animationDuration": 1000,
                          "animationEasing": "ease-in-out",
                      },
                  ),
              ],
              **({"id": container_id} if container_id else {}),
          ),
      ],
  )


def render_recent_evals_table(
    recent_evals: list[dict[str, Any]], agent_id: int | None = None
) -> dmc.Paper:
  """Renders the Recent Evaluations table matching main evaluations table."""

  rows = []
  for run in recent_evals:
    status_val = run.get("status", "PENDING")
    status_color, status_label = utils.run_status_display(status_val)

    score_pct = run["score"] * 100 if run["score"] is not None else None

    # When the worker picked the run up, not when it was queued. Null while it
    # is still queued.
    started_at = run.get("started_at")
    started_str = utils.format_timestamp(started_at) if started_at else "--"

    score_content = dmc.Text("--", size="sm", c="dimmed")
    if status_val == "COMPLETED" and score_pct is not None:
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
    elif status_val == "RUNNING":
      score_content = dmc.Text(
          "Calculating...", size="sm", c="dimmed", style={"fontStyle": "italic"}
      )

    rows.append(
        html.Tr([
            # Run ID
            html.Td(
                dmc.Text(
                    f"#{run['id']}",
                    ff="monospace",
                    size="sm",
                    c="dimmed",
                ),
                style={"padding": "16px 24px"},
            ),
            # Test Suite Link
            html.Td(
                links.render_test_suite_link(
                    run.get("suite_id"), run.get("suite_name") or "N/A"
                ),
                style={"padding": "16px 24px"},
            ),
            # Status
            html.Td(
                render_status_badge(status_label, status_color),
                style={"padding": "16px 24px"},
            ),
            # Accuracy
            html.Td(score_content, style={"padding": "16px 24px"}),
            # Duration
            html.Td(
                dmc.Text(run.get("duration", "--"), size="sm", c="dimmed"),
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
                        "View Report",
                        variant="light",
                        color="blue",
                        size="xs",
                        radius="md",
                    ),
                    href=f"/evaluations/runs/{run['id']}",
                    underline=False,
                ),
                style={"padding": "16px 24px", "textAlign": "right"},
            ),
        ])
    )

  header_style = {
      "padding": "16px 24px",
      "color": "var(--mantine-color-gray-5)",
      "fontWeight": 600,
      "textAlign": "left",
      "fontSize": "11px",
      "textTransform": "uppercase",
      "letterSpacing": "0.05em",
  }

  return dmc.Paper(
      withBorder=True,
      radius="md",
      shadow="sm",
      children=[
          dmc.Group(
              justify="space-between",
              p="lg",
              style={"borderBottom": "1px solid var(--mantine-color-gray-2)"},
              children=[
                  dmc.Text("Recent Evaluations", fw=700, size="lg"),
                  dmc.Anchor(
                      "View All",
                      href=f"/evaluations?agent_id={agent_id}"
                      if agent_id
                      else "/evaluations",
                      size="sm",
                      fw=500,
                  ),
              ],
          ),
          html.Div(
              style={"overflowX": "auto"},
              children=dmc.Table(
                  verticalSpacing=0,
                  horizontalSpacing=0,
                  highlightOnHover=True,
                  withTableBorder=False,
                  style={"width": "100%"},
                  children=[
                      html.Thead(
                          html.Tr(
                              [
                                  html.Th(
                                      "RUN ID",
                                      style={
                                          **header_style,
                                          "width": "120px",
                                          "whiteSpace": "nowrap",
                                      },
                                  ),
                                  html.Th("TEST SUITE", style=header_style),
                                  html.Th("STATUS", style=header_style),
                                  html.Th("ACCURACY", style=header_style),
                                  html.Th("DURATION", style=header_style),
                                  html.Th("STARTED", style=header_style),
                                  html.Th(
                                      "ACTION",
                                      style={
                                          **header_style,
                                          "textAlign": "right",
                                      },
                                  ),
                              ],
                              style={
                                  "backgroundColor": (
                                      "var(--mantine-color-gray-0)"
                                  ),
                                  "borderBottom": (
                                      "1px solid var(--mantine-color-gray-2)"
                                  ),
                              },
                          )
                      ),
                      html.Tbody(rows),
                  ],
              ),
          ),
      ],
  )


def render_empty_evaluations_placeholder() -> dmc.Paper:
  """Renders a placeholder when no evaluation data is available."""
  return dmc.Paper(
      withBorder=True,
      radius="md",
      p=60,
      shadow="sm",
      children=dmc.Center(
          dmc.Stack(
              align="center",
              gap="md",
              children=[
                  dmc.ThemeIcon(
                      DashIconify(icon="bi:clipboard-x", width=40),
                      size=80,
                      radius=100,
                      color="gray.1",
                      variant="light",
                      style={
                          "color": "var(--mantine-color-gray-4)",
                          "border": "2px dashed var(--mantine-color-gray-3)",
                      },
                  ),
                  dmc.Stack(
                      gap=4,
                      align="center",
                      children=[
                          dmc.Text(
                              "Agent not yet evaluated",
                              fw=600,
                              size="lg",
                              c="dark",
                          ),
                          dmc.Text(
                              "Data will appear once the agent has been"
                              " evaluated on a test suite.",
                              c="dimmed",
                              size="sm",
                              ta="center",
                              style={"maxWidth": "320px"},
                          ),
                      ],
                  ),
                  dmc.Button(
                      "Run Your First Evaluation",
                      id=AgentIds.Detail.BTN_EMPTY_RUN_EVAL,
                      variant="light",
                      color="blue",
                      radius="md",
                      mt="md",
                      leftSection=DashIconify(icon="bi:play-fill", width=18),
                  ),
              ],
          )
      ),
  )
