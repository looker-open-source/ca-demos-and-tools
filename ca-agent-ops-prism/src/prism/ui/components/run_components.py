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

"""Presentational components for evaluation run details."""

import difflib
import json
from typing import Any

from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import EvaluationIds


def render_run_context(
    raw_context: dict[str, Any] | None = None,
    loading: bool = False,
):
  """Renders a raw JSON view of the agent context snapshot."""
  if loading:
    return dmc.Stack([
        dmc.Skeleton(h=20, w="40%"),
        dmc.Skeleton(h=200, w="100%"),
    ])

  if raw_context is None:
    return dmc.Text("No context snapshot available.", c="dimmed", size="sm")

  try:
    formatted_json = json.dumps(raw_context, indent=2)
  except (TypeError, ValueError):
    formatted_json = str(raw_context)

  return dmc.Stack([
      dmc.Group(
          [
              dmc.Group(
                  [
                      DashIconify(icon="lucide:database", width=16),
                      dmc.Text("Snapshot Context", fw=600, size="sm"),
                  ],
                  gap="xs",
              ),
              dmc.Button(
                  "Compare to Live",
                  id=EvaluationIds.RUN_CONTEXT_DIFF_BTN,
                  variant="subtle",
                  size="compact-xs",
                  leftSection=DashIconify(icon="lucide:git-diff", width=14),
                  color="blue.6",
              ),
          ],
          justify="space-between",
          mb="xs",
      ),
      dmc.Paper(
          html.Pre(
              formatted_json,
              style={
                  "whiteSpace": "pre-wrap",
                  "wordBreak": "break-all",
                  "fontSize": "12px",
                  "margin": 0,
              },
          ),
          withBorder=True,
          p="md",
          radius="md",
          bg="gray.0",
      ),
  ])


def render_context_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
):
  """Renders a side-by-side or line-by-line diff of two contexts."""
  s_json = json.dumps(snapshot_context, indent=2).splitlines()
  l_json = json.dumps(live_context, indent=2).splitlines()

  diff = difflib.unified_diff(s_json, l_json, lineterm="")
  diff_lines = list(diff)

  if not diff_lines:
    return dmc.Alert(
        "No changes detected between snapshot and live context.",
        color="blue",
        title="Context Matches",
        icon=DashIconify(icon="lucide:check-circle"),
    )

  return dmc.Stack([
      dmc.Group(
          [
              DashIconify(icon="lucide:git-diff", width=16),
              dmc.Text("Context Changes (Snapshot vs Live)", fw=600, size="sm"),
          ],
          gap="xs",
      ),
      dmc.Paper(
          html.Pre(
              "\n".join(diff_lines),
              style={
                  "whiteSpace": "pre-wrap",
                  "wordBreak": "break-all",
                  "fontSize": "12px",
                  "margin": 0,
                  "color": "var(--mantine-color-gray-8)",
              },
          ),
          withBorder=True,
          p="md",
          radius="md",
          bg="gray.0",
      ),
  ])


def render_diff_modal(change_count: int = 0):
  # Renders the modern modal container for the context diff.
  return dmc.Modal(
      title=dmc.Group(
          [
              dmc.Group(
                  [
                      dmc.Text("Context Comparison", fw=700, size="lg"),
                      dmc.Badge(
                          f"{change_count} changes",
                          id=EvaluationIds.RUN_CONTEXT_DIFF_BADGE,
                          color="orange",
                          variant="light",
                          size="sm",
                      ),
                  ],
                  id=EvaluationIds.RUN_CONTEXT_DIFF_TITLE,
                  gap="md",
              ),
          ],
          gap="md",
      ),
      id=EvaluationIds.RUN_CONTEXT_DIFF_MODAL,
      children=html.Div(id=EvaluationIds.RUN_CONTEXT_DIFF_CONTENT),
      size="90%",
      padding="xl",
      radius="lg",
      overlayProps={
          "backgroundOpacity": 0.55,
          "blur": 3,
      },
      styles={
          "header": {
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
              "marginBottom": "var(--mantine-spacing-xl)",
              "paddingBottom": "var(--mantine-spacing-md)",
          }
      },
  )


def render_modern_context_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
):
  """Renders a modern unified diff view of two contexts."""
  s_json = json.dumps(snapshot_context, indent=2).splitlines()
  l_json = json.dumps(live_context, indent=2).splitlines()

  diff = list(difflib.ndiff(s_json, l_json))

  rows = []
  s_num = 1
  l_num = 1

  def add_row(s_num, l_num, op, line, bg=None, color=None):
    return html.Tr(
        [
            html.Td(
                str(s_num) if s_num else "",
                style={
                    "width": "40px",
                    "color": "var(--mantine-color-gray-5)",
                    "textAlign": "right",
                    "paddingRight": "10px",
                    "userSelect": "none",
                },
            ),
            html.Td(
                str(l_num) if l_num else "",
                style={
                    "width": "40px",
                    "color": "var(--mantine-color-gray-5)",
                    "textAlign": "right",
                    "paddingRight": "10px",
                    "userSelect": "none",
                },
            ),
            html.Td(
                op,
                style={
                    "width": "20px",
                    "textAlign": "center",
                    "fontWeight": "bold",
                    "color": color,
                },
            ),
            html.Td(
                line,
                style={
                    "fontFamily": "var(--font-mono)",
                    "fontSize": "13px",
                    "whiteSpace": "pre-wrap",
                },
            ),
        ],
        style={"backgroundColor": bg} if bg else {},
    )

  change_count = 0
  for line in diff:
    op = line[0]
    content = line[2:]

    if op == " ":
      rows.append(add_row(s_num, l_num, "", content))
      s_num += 1
      l_num += 1
    elif op == "-":
      rows.append(
          add_row(s_num, None, "-", content, bg="#fff5f5", color="#e03131")
      )
      s_num += 1
      change_count += 1
    elif op == "+":
      rows.append(
          add_row(None, l_num, "+", content, bg="#f0fff4", color="#2f855a")
      )
      l_num += 1
      change_count += 1

  return (
      html.Table(
          html.Tbody(rows),
          style={
              "width": "100%",
              "borderCollapse": "collapse",
              "border": "1px solid var(--mantine-color-gray-2)",
              "borderRadius": "8px",
              "overflow": "hidden",
          },
      ),
      change_count,
  )


def generate_text_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
):
  # Generates a raw text unified diff of two contexts.
  s_json = json.dumps(snapshot_context, indent=2).splitlines()
  l_json = json.dumps(live_context, indent=2).splitlines()
  return "\n".join(difflib.unified_diff(s_json, l_json, lineterm=""))


def render_side_by_side_context_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
):
  # Renders a side-by-side diff of two contexts using JSON.
  s_json = json.dumps(snapshot_context, indent=2)
  l_json = json.dumps(live_context, indent=2)

  return dmc.Grid(
      [
          dmc.GridCol(
              [
                  dmc.Text("Snapshot", fw=600, size="sm", mb=4),
                  dmc.Paper(
                      html.Pre(
                          s_json,
                          style={
                              "whiteSpace": "pre-wrap",
                              "fontSize": "12px",
                              "margin": 0,
                          },
                      ),
                      withBorder=True,
                      p="md",
                      bg="gray.0",
                  ),
              ],
              span=6,
          ),
          dmc.GridCol(
              [
                  dmc.Text("Live", fw=600, size="sm", mb=4),
                  dmc.Paper(
                      html.Pre(
                          l_json,
                          style={
                              "whiteSpace": "pre-wrap",
                              "fontSize": "12px",
                              "margin": 0,
                          },
                      ),
                      withBorder=True,
                      p="md",
                      bg="gray.0",
                  ),
              ],
              span=6,
          ),
      ],
      gutter="md",
  )


def render_trial_card(
    trial: Any,
    show_details_link: bool = True,
    suite_link: str | None = None,
    chart_section: Any | None = None,
) -> dmc.Paper:
  """Renders a simplified trial results card matching the comparison view."""
  actions = []

  is_terminal = getattr(trial, "status", None) in (
      RunStatus.COMPLETED,
      RunStatus.FAILED,
      RunStatus.CANCELLED,
  )

  # Always show Trace link if terminal
  if is_terminal:
    actions.append(
        dmc.Anchor(
            "View Trace",
            href=f"/evaluations/trials/{trial.id}/trace",
            size="10px",
            fw=700,
            underline=True,
            c="blue.6",
        )
    )

  # Optional Details link (hide on Trial Detail page) if terminal
  if show_details_link and is_terminal:
    actions.append(
        dmc.Anchor(
            "View Details",
            href=f"/evaluations/trials/{trial.id}",
            size="10px",
            fw=700,
            underline=True,
            c="blue.6",
        )
    )

  # Optional Suite link
  if suite_link:
    actions.append(
        dmc.Anchor(
            "View Test Suite",
            href=suite_link,
            size="10px",
            fw=700,
            underline=True,
            c="blue.6",
        )
    )

  sections = []

  # 1. Header: Test Case
  sections.append(
      dmc.Box(
          p="lg",
          children=dmc.Text(
              f'"{trial.question}"' if trial.question else "(No Test Case)",
              fw=700,
              size="lg",
              style={"letterSpacing": "-0.01em"},
          ),
      )
  )

  # 2. Body: Actions + Output
  sections.append(
      dmc.Box(
          p="lg",
          style={"borderTop": "1px solid var(--mantine-color-gray-1)"},
          children=dmc.Stack(
              gap="md",
              children=[
                  # Actions Header
                  dmc.Group(
                      gap="md",
                      children=[
                          dmc.Group(
                              gap=4,
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
                                      "TRIAL OUTPUT",
                                      size="10px",
                                      fw=700,
                                      c="blue.7",
                                  ),
                              ],
                          ),
                          *actions,
                      ],
                  ),
                  # Output box
                  dmc.Paper(
                      p="md",
                      radius="md",
                      bg="var(--mantine-color-gray-0)",
                      withBorder=True,
                      style={"borderColor": "var(--mantine-color-gray-2)"},
                      children=dmc.Text(
                          trial.output_text or "No output available.",
                          size="sm",
                          style={
                              "fontFamily": "var(--font-mono)",
                              "lineHeight": "1.7",
                              "whiteSpace": "pre-wrap",
                          },
                      ),
                  ),
              ],
          ),
      )
  )

  # 3. Optional Charts Section
  if chart_section:
    sections.append(
        dmc.Box(
            p="lg",
            style={"borderTop": "1px solid var(--mantine-color-gray-1)"},
            children=dmc.Stack(
                gap="md",
                children=[
                    dmc.Group(
                        gap=4,
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
                                "GENERATED CHARTS",
                                size="10px",
                                fw=700,
                                c="blue.7",
                            ),
                        ],
                    ),
                    chart_section,
                ],
            ),
        )
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p=0,
      mb="xl",
      style={
          "borderColor": "var(--mantine-color-gray-2)",
          "overflow": "hidden",
      },
      children=sections,
  )
