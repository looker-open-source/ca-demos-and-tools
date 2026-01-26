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
from prism.ui.pages.evaluation_ids import EvaluationIds


def render_run_context(
    raw_context: dict[str, Any] | None = None,
    loading: bool = False,
) -> dmc.Paper:
  """Renders a raw JSON view of the agent context snapshot."""
  if loading:
    content = dmc.Stack(
        gap=4,
        children=[
            dmc.Skeleton(height=15, width="100%"),
            dmc.Skeleton(height=15, width="80%"),
            dmc.Skeleton(height=15, width="90%"),
            dmc.Skeleton(height=15, width="70%"),
        ],
    )
  else:
    json_str = (
        json.dumps(raw_context, indent=2) if raw_context else "No context data."
    )
    content = dmc.Box(
        bg="var(--mantine-color-gray-0)",
        p="md",
        style={
            "borderRadius": "var(--mantine-radius-md)",
            "border": "1px solid var(--mantine-color-gray-2)",
        },
        children=dmc.ScrollArea(
            h=180,
            children=dmc.Code(
                json_str,
                block=True,
                fz="xs",
                style={
                    "whiteSpace": "pre-wrap",
                    "backgroundColor": "transparent",
                },
            ),
        ),
    )

  return dmc.Card(
      withBorder=True,
      radius="md",
      padding="lg",
      shadow="sm",
      children=[
          dmc.CardSection(
              withBorder=False,
              inheritPadding=True,
              py="md",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Stack(
                              gap=0,
                              children=[
                                  dmc.Text(
                                      "Agent Context Snapshot",
                                      fw=700,
                                      size="lg",
                                  ),
                                  dmc.Text(
                                      "GDA Agent Context at time of run"
                                      " creation",
                                      c="dimmed",
                                      size="sm",
                                  ),
                              ],
                          ),
                          dmc.Button(
                              "Compare to Live Context",
                              id=EvaluationIds.RUN_CONTEXT_DIFF_BTN,
                              leftSection=DashIconify(
                                  icon="bi:diff-added", width=16
                              ),
                              variant="default",
                              radius="md",
                              fw=600,
                              size="xs",
                              disabled=loading,
                          ),
                      ],
                  )
              ],
          ),
          dmc.CardSection(
              inheritPadding=True,
              py="lg",
              children=content,
          ),
      ],
  )


def render_context_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
) -> list[html.Div]:
  """Renders a side-by-side or line-by-line diff of two contexts."""
  # Pretty print both using JSON
  s_lines = json.dumps(
      snapshot_context, indent=2, sort_keys=True, ensure_ascii=False
  ).splitlines()
  l_lines = json.dumps(
      live_context, indent=2, sort_keys=True, ensure_ascii=False
  ).splitlines()

  diff = list(difflib.ndiff(s_lines, l_lines))

  rows = []
  for line in diff:
    color = "inherit"
    bg = "transparent"
    icon = None

    if line.startswith("+ "):
      color = "var(--mantine-color-green-8)"
      bg = "var(--mantine-color-green-0)"
      icon = "bi:plus"
    elif line.startswith("- "):
      color = "var(--mantine-color-red-8)"
      bg = "var(--mantine-color-red-0)"
      icon = "bi:dash"
    elif line.startswith("? "):
      continue  # Intraline change markers, skip for simple view

    rows.append(
        dmc.Group(
            gap="xs",
            p=2,
            style={"backgroundColor": bg, "fontFamily": "monospace"},
            children=[
                (
                    DashIconify(icon=icon, width=12, color=color)
                    if icon
                    else html.Div(style={"width": 12})
                ),
                dmc.Text(
                    line[2:],
                    size="xs",
                    c=color,
                    style={"whiteSpace": "pre-wrap", "wordBreak": "break-word"},
                ),
            ],
        )
    )

  return rows


def render_diff_modal(children: any, change_count: int = 0) -> dmc.Modal:
  """Renders the modern modal container for the context diff."""

  if change_count == 0:
    badge = dmc.Badge(
        "No changes detected",
        color="gray",
        variant="light",
        radius="sm",
        size="xs",
    )
  else:
    badge = dmc.Badge(
        "Changes detected",
        color="orange",
        variant="light",
        radius="sm",
        size="xs",
        fw=700,
    )

  return dmc.Modal(
      id=EvaluationIds.RUN_CONTEXT_DIFF_MODAL,
      title=dmc.Group(
          id=EvaluationIds.RUN_CONTEXT_DIFF_TITLE,
          children=[
              dmc.Text("Context Diff (Snapshot vs Live)", fw=700, size="lg"),
              badge,
          ],
          gap="sm",
      ),
      size="x-large",
      opened=False,
      padding=0,
      styles={
          "header": {
              "padding": "var(--mantine-spacing-md) var(--mantine-spacing-xl)",
              "borderBottom": "1px solid var(--mantine-color-gray-2)",
              "margin": 0,
          },
          "body": {"padding": 0},
      },
      children=[
          # Info Banner
          dmc.Box(
              p="md",
              px="xl",
              bg="var(--mantine-color-gray-0)",
              style={"borderBottom": "1px solid var(--mantine-color-gray-2)"},
              children=dmc.Group(
                  gap="md",
                  align="flex-start",
                  wrap="nowrap",
                  children=[
                      DashIconify(
                          icon="material-symbols:info-outline",
                          width=20,
                          color="var(--mantine-color-blue-6)",
                      ),
                      dmc.Text(
                          "Agent context includes datasources, system"
                          " instructions, examples, and knowledge used to guide"
                          " the agent. A snapshot of this context is captured"
                          " at the moment an evaluation run starts to ensure"
                          " consistent and reproducible results.",
                          size="sm",
                          c="dimmed",
                          lh=1.5,
                      ),
                  ],
              ),
          ),
          # Unified View Header & Actions
          dmc.Group(
              justify="space-between",
              px="xl",
              py="xs",
              bg="var(--mantine-color-gray-1)",
              style={"borderBottom": "1px solid var(--mantine-color-gray-2)"},
              children=[
                  dmc.Text(
                      "Unified View",
                      size="xs",
                      fw=700,
                      c="dimmed",
                      tt="uppercase",
                  ),
                  dmc.Group(
                      gap="xs",
                      children=[
                          dmc.Button(
                              "Download Diff",
                              id=EvaluationIds.BTN_DOWNLOAD_DIFF,
                              variant="filled",
                              color="indigo",
                              size="xs",
                              radius="md",
                              leftSection=DashIconify(icon="bi:download"),
                          ),
                      ],
                  ),
              ],
          ),
          # Diff Content
          dmc.Box(
              id=EvaluationIds.RUN_CONTEXT_DIFF_CONTENT,
              style={"overflowX": "auto"},
              children=children,
          ),
      ],
  )


def render_modern_context_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
) -> tuple[html.Table, int]:
  """Renders a modern unified diff view of two contexts."""
  s_json = json.dumps(
      snapshot_context, indent=2, sort_keys=True, ensure_ascii=False
  )
  l_json = json.dumps(
      live_context, indent=2, sort_keys=True, ensure_ascii=False
  )

  s_lines = s_json.splitlines()
  l_lines = l_json.splitlines()

  matcher = difflib.SequenceMatcher(None, s_lines, l_lines)
  rows = []
  change_count = 0

  s_ptr = 1
  l_ptr = 1

  # Common styles
  cell_style = {
      "padding": "2px 10px",
      "fontFamily": "var(--font-mono)",
      "fontSize": "12px",
      "whiteSpace": "pre",
  }
  line_num_style = {
      **cell_style,
      "textAlign": "right",
      "color": "var(--mantine-color-gray-5)",
      "backgroundColor": "var(--mantine-color-gray-0)",
      "width": "40px",
      "userSelect": "none",
      "borderRight": "1px solid var(--mantine-color-gray-2)",
  }
  op_style = {
      **cell_style,
      "width": "20px",
      "textAlign": "center",
      "userSelect": "none",
      "fontWeight": "bold",
  }

  def add_row(s_num, l_num, op, line, bg=None, color=None):
    row_bg = bg or "transparent"
    row_color = color or "inherit"

    return html.Tr(
        style={"backgroundColor": row_bg},
        children=[
            html.Td(str(s_num) if s_num else "", style=line_num_style),
            html.Td(str(l_num) if l_num else "", style=line_num_style),
            html.Td(op, style={**op_style, "color": row_color}),
            html.Td(line, style={**cell_style, "color": row_color}),
        ],
    )

  for tag, i1, i2, j1, j2 in matcher.get_opcodes():
    if tag == "equal":
      for i in range(i1, i2):
        rows.append(add_row(s_ptr, l_ptr, "", s_lines[i]))
        s_ptr += 1
        l_ptr += 1
    elif tag == "delete":
      for i in range(i1, i2):
        rows.append(
            add_row(
                s_ptr,
                None,
                "-",
                s_lines[i],
                bg="#fee2e2",
                color="var(--mantine-color-red-9)",
            )
        )
        s_ptr += 1
        change_count += 1
    elif tag == "insert":
      for j in range(j1, j2):
        rows.append(
            add_row(
                None,
                l_ptr,
                "+",
                l_lines[j],
                bg="#dcfce7",
                color="var(--mantine-color-green-9)",
            )
        )
        l_ptr += 1
        change_count += 1
    elif tag == "replace":
      # Show deletions then additions
      for i in range(i1, i2):
        rows.append(
            add_row(
                s_ptr,
                None,
                "-",
                s_lines[i],
                bg="#fee2e2",
                color="var(--mantine-color-red-9)",
            )
        )
        s_ptr += 1
        change_count += 1
      for j in range(j1, j2):
        rows.append(
            add_row(
                None,
                l_ptr,
                "+",
                l_lines[j],
                bg="#dcfce7",
                color="var(--mantine-color-green-9)",
            )
        )
        l_ptr += 1
        change_count += 1

  table = html.Table(
      style={"width": "100%", "borderCollapse": "collapse"}, children=rows
  )

  return table, change_count


def generate_text_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
) -> str:
  """Generates a raw text unified diff of two contexts."""
  s_json = json.dumps(
      snapshot_context, indent=2, sort_keys=True, ensure_ascii=False
  )
  l_json = json.dumps(
      live_context, indent=2, sort_keys=True, ensure_ascii=False
  )

  s_lines = s_json.splitlines()
  l_lines = l_json.splitlines()

  diff = difflib.unified_diff(
      s_lines,
      l_lines,
      fromfile="Snapshot Context",
      tofile="Live Context",
      lineterm="",
  )
  return "\n".join(diff)


def render_side_by_side_context_diff(
    snapshot_context: dict[str, Any], live_context: dict[str, Any]
) -> tuple[dmc.Grid, int]:
  """Renders a side-by-side diff of two contexts using JSON."""
  # Pretty print both using JSON for better readability
  base_json = json.dumps(
      snapshot_context, indent=2, sort_keys=True, ensure_ascii=False
  )
  chal_json = json.dumps(
      live_context, indent=2, sort_keys=True, ensure_ascii=False
  )

  s_lines = base_json.splitlines()
  l_lines = chal_json.splitlines()

  diff = list(difflib.ndiff(s_lines, l_lines))

  base_col = []
  challenger_col = []

  for line in diff:
    if line.startswith("  "):  # Unchanged
      base_col.append(
          dmc.Text(
              line[2:],
              size="xs",
              style={
                  "fontFamily": "monospace",
                  "whiteSpace": "pre-wrap",
                  "wordBreak": "break-word",
              },
          )
      )
      challenger_col.append(
          dmc.Text(
              line[2:],
              size="xs",
              style={
                  "fontFamily": "monospace",
                  "whiteSpace": "pre-wrap",
                  "wordBreak": "break-word",
              },
          )
      )
    elif line.startswith("- "):  # Removed from base
      base_col.append(
          dmc.Text(
              line[2:],
              size="xs",
              c="red.8",
              bg="red.0",
              style={
                  "fontFamily": "monospace",
                  "whiteSpace": "pre-wrap",
                  "wordBreak": "break-word",
              },
          )
      )
      # Keep challenger side empty/spacer
      challenger_col.append(dmc.Text(" ", size="xs"))
    elif line.startswith("+ "):  # Added to challenger
      # Keep base side empty/spacer
      base_col.append(dmc.Text(" ", size="xs"))
      challenger_col.append(
          dmc.Text(
              line[2:],
              size="xs",
              c="green.8",
              bg="green.0",
              style={
                  "fontFamily": "monospace",
                  "whiteSpace": "pre-wrap",
                  "wordBreak": "break-word",
              },
          )
      )
    elif line.startswith("? "):
      continue

  # Count changes (additions and removals)
  change_count = sum(1 for line in diff if line.startswith(("+ ", "- ")))

  grid = dmc.Grid(
      gutter="xs",
      children=[
          dmc.GridCol(
              span=6,
              children=[
                  dmc.Text("Snapshot", size="xs", fw=700, mb="xs"),
                  dmc.Paper(
                      withBorder=True,
                      p="xs",
                      bg="gray.0",
                      children=dmc.Stack(gap=0, children=base_col),
                  ),
              ],
          ),
          dmc.GridCol(
              span=6,
              children=[
                  dmc.Text("Live", size="xs", fw=700, mb="xs"),
                  dmc.Paper(
                      withBorder=True,
                      p="xs",
                      bg="gray.0",
                      children=dmc.Stack(gap=0, children=challenger_col),
                  ),
              ],
          ),
      ],
  )
  return grid, change_count


def render_trial_card(
    trial: Any,
    show_details_link: bool = True,
    suite_link: str | None = None,
    chart_section: Any | None = None,
) -> dmc.Paper:
  """Renders a simplified trial results card matching the comparison view."""
  actions = []

  # Always show Trace link
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

  # Optional Details link (hide on Trial Detail page)
  if show_details_link:
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

  # 1. Header: Question
  sections.append(
      dmc.Box(
          p="lg",
          children=dmc.Text(
              f'"{trial.question}"' if trial.question else "(No Question)",
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
