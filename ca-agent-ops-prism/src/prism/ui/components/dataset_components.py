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

"""Presentational components for the Datasets UI."""

import json
from typing import Any
from dash import html
from dash_ace import DashAceEditor
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common.schemas import suite
from prism.ui.models import ui_state
from prism.ui.pages.dataset_ids import DatasetIds as Ids


def render_dataset_card(
    s: suite.Suite, question_count: int = 0, run_count: int = 0
):
  """Renders a single dataset card for the dashboard."""
  card_content = dmc.Card(
      p="lg",
      radius="md",
      withBorder=True,
      style={
          "&:hover": {
              "boxShadow": "var(--mantine-shadow-md)",
              "borderColor": "var(--mantine-color-blue-500)",
          },
          "cursor": "pointer",
          "transition": "all 0.2s ease",
      },
      children=[
          dmc.Group(
              justify="space-between",
              mb="xs",
              children=[
                  dmc.Text(s.name, fw=600, size="lg"),
                  dmc.Badge(
                      s.datasource_type or "No Source",
                      variant="light",
                      color="blue" if s.datasource_type == "BQ" else "indigo",
                  ),
              ],
          ),
          dmc.Text(
              s.description or "No description provided.",
              size="sm",
              c="dimmed",
              lineClamp=2,
              mb="xl",
              style={"height": "3.2em"},
          ),
          dmc.Divider(mb="md"),
          dmc.Group(
              gap="xl",
              children=[
                  dmc.Stack(
                      gap=0,
                      children=[
                          dmc.Text(str(question_count), fw=700),
                          dmc.Text("Test Cases", size="xs", c="dimmed"),
                      ],
                  ),
                  dmc.Stack(
                      gap=0,
                      children=[
                          dmc.Text(str(run_count), fw=700),
                          dmc.Text("Runs", size="xs", c="dimmed"),
                      ],
                  ),
              ],
          ),
      ],
  )

  return dmc.Anchor(
      card_content,
      href=f"/test_suites/view/{s.id}",
      underline=False,
      c="inherit",
      style={"display": "block", "textDecoration": "none"},
  )


def render_assertion_badges(asserts: list[Any]):
  """Renders a list of badges for each assertion type."""
  num_asserts = len(asserts)
  badges = []

  if num_asserts > 0:
    # Group by type
    type_counts = {}
    for a in asserts:
      if isinstance(a, dict):
        a_type = a.get("type", "unknown")
      else:
        a_type = getattr(a, "type", "unknown")
      type_counts[a_type] = type_counts.get(a_type, 0) + 1

    for a_type, count in sorted(type_counts.items()):
      style = get_assertion_style(a_type)
      label = style["label"]
      if count > 1:
        if any(
            label.endswith(suffix) for suffix in ["ch", "sh", "x", "s", "z"]
        ):
          label += "es"
        else:
          label += "s"

      badges.append(
          dmc.Group(
              gap=6,
              px="xs",
              py=4,
              style={
                  "backgroundColor": f"var(--mantine-color-{style['bg']}-0)",
                  "border": f"1px solid var(--mantine-color-{style['bg']}-2)",
                  "borderRadius": "var(--mantine-radius-md)",
              },
              children=[
                  DashIconify(
                      icon=style["icon"],
                      color=f"var(--mantine-color-{style['color']}-7)",
                      width=16,
                  ),
                  dmc.Text(
                      f"{count} {label}",
                      size="xs",
                      fw=700,
                      c=style["color"],
                  ),
              ],
          )
      )
  else:
    # 0 Assertions Badge
    badges.append(
        dmc.Group(
            gap=6,
            px="xs",
            py=4,
            style={
                "backgroundColor": "var(--mantine-color-orange-0)",
                "border": "1px solid var(--mantine-color-orange-2)",
                "borderRadius": "var(--mantine-radius-md)",
            },
            children=[
                DashIconify(
                    icon="material-symbols:warning",
                    color="var(--mantine-color-orange-8)",
                    width=16,
                ),
                dmc.Text(
                    "0 Assertions",
                    size="xs",
                    fw=700,
                    c="orange",
                ),
            ],
        )
    )

  return badges


def render_question_card(
    question: ui_state.SuiteQuestion, index: int, read_only: bool = False
):
  """Renders a single test case card in the builder."""
  asserts = question.asserts or []
  badges = render_assertion_badges(asserts)

  return dmc.Card(
      p="lg",
      radius="md",
      withBorder=True,
      mb="md",
      className="group",  # For hover effects if we add CSS
      style={
          "transition": "all 0.2s ease",
          "cursor": "pointer" if read_only else "default",
          "&:hover": {
              "boxShadow": "var(--mantine-shadow-sm)",
              "borderColor": "var(--mantine-color-blue-3)",
          },
      },
      children=[
          dmc.Group(
              justify="space-between",
              align="start",
              wrap="nowrap",
              mb="md",
              children=[
                  dmc.Group(
                      align="start",
                      gap="md",
                      children=[
                          dmc.Badge(
                              f"TC{index + 1}",
                              variant="light",
                              color="gray",
                              radius="sm",
                              size="lg",
                              styles={
                                  "root": {
                                      "textTransform": "none",
                                      "fontFamily": "monospace",
                                  }
                              },
                          ),
                          dmc.Text(
                              question.question,
                              fw=600,
                              size="md",
                              style={"lineHeight": "1.4"},
                          ),
                      ],
                  ),
                  _render_question_actions(index, read_only),
              ],
          ),
          dmc.Group(
              gap="md",
              children=badges,
          ),
      ],
  )


def _render_question_actions(index: int, read_only: bool):
  """Renders edit/delete buttons if not read-only."""
  if read_only:
    return html.Div()

  return dmc.Group(
      gap="xs",
      children=[
          dmc.ActionIcon(
              DashIconify(icon="bi:pencil", width=20),
              id={
                  "type": "edit-question-btn",
                  "index": index,
              },
              variant="subtle",
              color="gray",
              className="opacity-0 group-hover:opacity-100 transition-opacity",
          ),
          dmc.ActionIcon(
              DashIconify(icon="bi:trash", width=20),
              id={
                  "type": Ids.Q_REMOVE_QUESTION_BTN,
                  "index": index,
              },
              variant="subtle",
              color="gray",
              className=(
                  "opacity-0 group-hover:opacity-100 transition-opacity"
                  " hover:text-red-500"
              ),
          ),
      ],
  )


def render_question_nav_item(
    question: ui_state.SuiteQuestion, index: int, active: bool = False
):
  """Renders a navigation link/button for the test case playground."""
  # Colors from mockup
  bg_color = "transparent"
  border_color = "transparent"
  icon_color = "#94a3b8"  # slate-400
  text_color = "dimmed"
  msg_icon = "material-symbols:chat-bubble-outline"

  if active:
    bg_color = "#eff6ff"  # blue-50
    border_color = "#bfdbfe"  # blue-200
    icon_color = "#2563eb"  # blue-600
    text_color = "dark"
    msg_icon = "material-symbols:chat-bubble"

  editing_badge = []
  if active:
    editing_badge.append(
        dmc.Text(
            "EDITING",
            size="10px",
            fw=700,
            c="blue",
            tt="uppercase",
            style={"letterSpacing": "0.05em"},
        )
    )

  assert_count = len(question.asserts)
  count_label = f"{assert_count} Asserts" if assert_count != 1 else "1 Assert"
  coverage_badge = dmc.Badge(
      count_label,
      size="xs",
      variant="light",
      color="blue" if question.asserts else "orange",
      styles={
          "root": {
              "textTransform": "none",
              "padding": "0 4px",
              "height": "16px",
          }
      },
  )

  return dmc.UnstyledButton(
      id={"type": Ids.Q_LIST_ITEM, "index": index},
      w="100%",
      mb="xs",
      children=dmc.Paper(
          p="sm",
          radius="md",
          withBorder=True,
          style={
              "backgroundColor": bg_color,
              "borderColor": border_color if active else "transparent",
              "transition": "all 0.2s ease",
          },
          className="group hover:bg-slate-50",
          children=dmc.Stack(
              gap="xs",
              children=[
                  # Top Row: Icon + [EDITING] + ID
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Group(
                              gap="xs",
                              children=[
                                  DashIconify(
                                      icon=msg_icon,
                                      width=16,
                                      color=icon_color,
                                  ),
                                  *editing_badge,
                                  coverage_badge,
                              ],
                          ),
                          dmc.Text(
                              f"#{index + 1:03d}",
                              size="10px",
                              c="dimmed",
                              style={"fontFamily": "monospace"},
                          ),
                      ],
                  ),
                  # Bottom Row: Test Case Text
                  dmc.Text(
                      question.question or "(Empty Test Case)",
                      size="sm",
                      fw=600 if active else 500,
                      c=text_color,
                      lineClamp=2,
                      style={"lineHeight": "1.4"},
                  ),
              ],
          ),
      ),
  )


def render_question_modal(ids: Any):
  """Renders the modal for adding/editing a test case."""
  return dmc.Modal(
      id=ids.MODAL_QUESTION,
      title="Add/Edit Test Case",
      size="lg",
      children=[
          dmc.Textarea(
              id=ids.MODAL_QUESTION_TEXT,
              label="Test Case Text",
              placeholder="e.g. What is the total revenue for last month?",
              required=True,
              minRows=3,
              mb="lg",
          ),
          dmc.Text("Assertions", fw=600, size="sm", mb="xs"),
          html.Div(
              id=ids.MODAL_ASSERT_LIST,
              className="mb-lg p-sm border rounded",
              style={"minHeight": "50px"},
          ),
          dmc.Paper(
              p="sm",
              withBorder=True,
              radius="sm",
              children=[
                  dmc.Text("Add New Assertion", fw=600, size="xs", mb="xs"),
                  dmc.Grid(
                      children=[
                          dmc.GridCol(
                              span=4,
                              children=[
                                  dmc.Select(
                                      id=ids.MODAL_ASSERT_TYPE,
                                      data=[
                                          {
                                              "label": "Equals",
                                              "value": "equals",
                                          },
                                          {
                                              "label": "Contains",
                                              "value": "contains",
                                          },
                                          {
                                              "label": "SQL Valid",
                                              "value": "sql_valid",
                                          },
                                          {
                                              "label": "Custom",
                                              "value": "custom",
                                          },
                                      ],
                                      placeholder="Type",
                                  )
                              ],
                          ),
                          dmc.GridCol(
                              span=6,
                              children=[
                                  dmc.TextInput(
                                      id=ids.MODAL_ASSERT_VALUE,
                                      placeholder="Value (or YAML)",
                                  ),
                                  html.Div(
                                      id=ids.MODAL_ACE_CONTAINER,
                                      style={"display": "none"},
                                      children=[
                                          DashAceEditor(
                                              id=ids.MODAL_ASSERT_YAML,
                                              mode="yaml",
                                              theme="github",
                                              width="100%",
                                              height="150px",
                                          )
                                      ],
                                  ),
                              ],
                          ),
                          dmc.GridCol(
                              span=2,
                              children=[
                                  dmc.ActionIcon(
                                      DashIconify(icon="bi:plus-lg"),
                                      id=ids.MODAL_ADD_ASSERT_BTN,
                                      size="lg",
                                      variant="light",
                                  )
                              ],
                          ),
                      ]
                  ),
              ],
          ),
          dmc.Group(
              justify="flex-end",
              mt="xl",
              children=[
                  dmc.Button(
                      "Cancel",
                      id=ids.MODAL_CANCEL_BTN,
                      variant="subtle",
                      color="gray",
                  ),
                  dmc.Button("Save Test Case", id=ids.MODAL_SAVE_BTN),
              ],
          ),
      ],
  )


def get_assertion_style(a_type: str):
  """Returns icon, color, label for assertion type matching mockup."""
  # Default
  style = {
      "icon": "material-symbols:help-outline",
      "color": "gray",
      "bg": "gray",
      "label": "Assertion",
      "badge": "CHECK",
      "desc": "Validates the response.",
  }

  if a_type == "text-contains" or a_type == "text-exact-match":
    style.update({
        "icon": "material-symbols:text-fields",
        "color": "blue",
        "bg": "blue",
        "label": "Text Contains",
        "badge": "STRING",
    })
  elif a_type == "looker-query-match":
    style.update({
        "icon": "material-symbols:query-stats",
        "color": "pink",
        "bg": "pink",
        "label": "Looker Query Match",
        "badge": "LOOKML",
    })
  elif a_type == "data-check-row":
    style.update({
        "icon": "material-symbols:table-rows",
        "color": "teal",
        "bg": "teal",
        "label": "Data Check Row",
        "badge": "DATA",
    })
  elif a_type == "data-check-row-count":
    style.update({
        "icon": "material-symbols:format-list-numbered",
        "color": "cyan",
        "bg": "cyan",
        "label": "Data Check Row Count",
        "badge": "DATA",
    })
  elif a_type == "chart-check-type":
    style.update({
        "icon": "material-symbols:bar-chart",
        "color": "indigo",
        "bg": "indigo",
        "label": "Chart Check Type",
        "badge": "CHART",
    })
  elif a_type == "query-contains" or a_type == "sql-valid":
    style.update({
        "icon": "material-symbols:manage-search",
        "color": "orange",
        "bg": "orange",
        "label": "Query Contains",
        "badge": "SQL",
    })
  elif a_type == "custom":
    style.update({
        "icon": "material-symbols:code",
        "color": "violet",
        "bg": "violet",
        "label": "Custom Python",
        "badge": "PYTHON",
    })
  elif a_type in ["duration-max-ms", "latency-max-ms"]:
    style.update({
        "icon": "material-symbols:timer",
        "color": "indigo",
        "bg": "indigo",
        "label": (
            "Response Duration"
            if a_type == "duration-max-ms"
            else "Response Latency"
        ),
        "badge": "PERFORMANCE",
    })
  elif a_type == "llm-evaluation":
    style.update({
        "icon": "material-symbols:psychology",
        "color": "grape",
        "bg": "grape",
        "label": "LLM Evaluation",
        "badge": "TONE",
    })
  elif a_type == "regex-match":
    style.update({
        "icon": "material-symbols:code",
        "color": "emerald",
        "bg": "emerald",
        "label": "Regex Pattern",
        "badge": "MATCH",
    })
  elif a_type == "sentiment-score":
    style.update({
        "icon": "material-symbols:mood",
        "color": "sky",
        "bg": "sky",
        "label": "Sentiment Analysis",
        "badge": "SCORE",
    })
  elif a_type == "resolution-confirmation":
    style.update({
        "icon": "material-symbols:verified",
        "color": "orange",
        "bg": "orange",
        "label": "Resolution Confirmation",
        "badge": "SCRIPT",
    })

  return style


def render_assertion_card(assertion: dict[str, Any], index: int):
  """Renders a detailed assertion card matching the mockup."""
  a_type = assertion.get("type", "unknown")
  weight = assertion.get("weight", 0)
  is_accuracy = weight > 0

  style = get_assertion_style(a_type)

  # Content Block (for regex/custom values)
  content = None
  if "params" in assertion or "value" in assertion or "columns" in assertion:
    # simplistic rendering of params for now
    val = (
        assertion.get("value")
        or assertion.get("params")
        or assertion.get("columns")
    )
    val_str = str(val)
    if isinstance(val, (dict, list)):
      val_str = json.dumps(val, indent=2)

    content = dmc.Box(
        bg="#1e293b",  # slate-800
        c="white",
        p="md",
        mt="sm",
        mx="lg",  # Indent
        mb="md",
        style={
            "borderRadius": "8px",
            "fontFamily": "monospace",
            "fontSize": "12px",
            "whiteSpace": "pre-wrap",
        },
        children=dmc.Text(
            val_str, c="teal", size="xs"
        ),  # mimicking code styling
    )

  badge_list = []
  if "badge" in style:
    badge_list.append(
        dmc.Badge(
            style.get("badge", "Check"),
            size="xs",
            color=style["color"],
            variant="light",
        )
    )

  return dmc.Paper(
      radius="md",
      withBorder=True,
      mb="md",
      style={"overflow": "hidden"},
      className="group",
      children=[
          # Header Row
          dmc.Group(
              justify="space-between",
              p="md",
              style={"cursor": "pointer"},
              className="hover:bg-gray-50 transition-colors",
              children=[
                  # Left: Icon + Text
                  dmc.Group(
                      children=[
                          dmc.ThemeIcon(
                              DashIconify(icon=style["icon"], width=24),
                              size="xl",
                              radius="md",
                              color=style["color"],
                              variant="light",
                          ),
                          dmc.Stack(
                              gap=2,
                              children=[
                                  dmc.Group(
                                      gap="xs",
                                      children=[
                                          dmc.Text(
                                              style["label"], fw=700, size="sm"
                                          ),
                                          *badge_list,
                                      ],
                                  ),
                                  dmc.Text(
                                      style["desc"], size="xs", c="dimmed"
                                  ),
                              ],
                          ),
                      ]
                  ),
                  # Right: Toggle + Actions
                  dmc.Group(
                      gap="lg",
                      children=[
                          dmc.Tooltip(
                              label=(
                                  "Accuracy assertions contribute to the"
                                  " overall score. Diagnostic assertions are"
                                  " used for monitoring without affecting the"
                                  " score."
                              ),
                              position="top",
                              withArrow=True,
                              children=dmc.Group(
                                  gap="xs",
                                  children=[
                                      dmc.Text(
                                          "ACCURACY",
                                          size="10px",
                                          fw=700,
                                          c=(
                                              "dimmed"
                                              if not is_accuracy
                                              else "dark"
                                          ),
                                      ),
                                      dmc.Switch(
                                          checked=is_accuracy,
                                          id={
                                              "type": (
                                                  Ids.ASSERT_TOGGLE_ACCURACY
                                              ),
                                              "index": index,
                                          },
                                          size="md",
                                          color="blue",
                                      ),
                                  ],
                              ),
                          ),
                          dmc.Divider(orientation="vertical", h=20),
                          # Actions
                          dmc.Group(
                              gap=4,
                              children=[
                                  dmc.ActionIcon(
                                      DashIconify(icon="bi:pencil", width=18),
                                      id={
                                          "type": Ids.ASSERT_EDIT_BTN,
                                          "index": index,
                                      },
                                      variant="subtle",
                                      color="gray",
                                  ),
                                  dmc.ActionIcon(
                                      DashIconify(icon="bi:trash", width=18),
                                      id={
                                          "type": Ids.Q_REMOVE_ASSERTION_BTN,
                                          "index": index,
                                      },
                                      variant="subtle",
                                      color="red",
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          ),
          # Content Block (collapsible effectively by presence)
          content if content else html.Div(),
      ],
  )


def render_add_question_placeholder(dataset_id: str):
  """Renders a styled placeholder card for adding a new test case."""
  return dmc.Anchor(
      dmc.Paper(
          p="lg",
          radius="md",
          withBorder=True,
          style={
              "borderStyle": "dashed",
              "cursor": "pointer",
              "backgroundColor": "#f8fafc",
          },
          className="hover:bg-gray-100 transition-colors",
          children=[
              dmc.Center(
                  children=dmc.Group(
                      children=[
                          DashIconify(
                              icon="bi:plus-circle",
                              width=20,
                              color="#64748b",
                          ),
                          dmc.Text(
                              "Add New Test Case",
                              fw=500,
                              c="dimmed",
                          ),
                      ]
                  )
              )
          ],
      ),
      href=f"/test_suites/edit/{dataset_id}?action=add",
      underline=False,
      mb="lg",
      style={"display": "block"},
  )
