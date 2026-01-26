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

"""Reusable UI components for assertion forms."""

import json
from typing import Any

from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common.schemas.execution import Trial
from prism.ui.constants import ASSERTS_GUIDE
from prism.ui.models.ui_state import AssertionMetric
from prism.ui.models.ui_state import AssertionSummary
from prism.ui.pages.comparison_ids import ComparisonIds
from prism.ui.pages.dataset_ids import DatasetIds as Ids
import yaml


def _render_guide_card(ids_class):
  """Renders the dynamic guide card."""
  # This container will be populated by a client-side callback
  # based on the selected assertion type.
  return dmc.Paper(
      id=ids_class.ASSERT_GUIDE_CONTAINER,
      radius="md",
      p="md",
      withBorder=True,
      style={
          "backgroundColor": "#eff6ff",  # blue-50
          "borderColor": "#dbeafe",  # blue-100
          "display": "none",  # Toggled by callback
      },
      children=[
          dmc.Group(
              align="start",
              wrap="nowrap",
              justify="space-between",
              children=[
                  dmc.Group(
                      align="start",
                      gap="md",
                      children=[
                          # Icon
                          dmc.ThemeIcon(
                              size="lg",
                              radius="md",
                              variant="light",
                              color="blue",
                              children=DashIconify(
                                  icon="material-symbols:lightbulb",
                                  width=20,
                              ),
                          ),
                          # Content
                          dmc.Stack(
                              gap=4,
                              children=[
                                  dmc.Text(
                                      id=ids_class.ASSERT_GUIDE_TITLE,
                                      fw=700,
                                      size="sm",
                                      c="#1e40af",  # blue-800
                                  ),
                                  dmc.Text(
                                      id=ids_class.ASSERT_GUIDE_DESC,
                                      size="sm",
                                      c="#1e3a8a",  # blue-900
                                      lh=1.5,
                                  ),
                              ],
                          ),
                      ],
                  ),
                  # Right side placeholder (optional, keeps layout balanced)
                  # Can be used for images or close buttons in future
              ],
          )
      ],
  )


def _render_code_editor(ids_class):
  """Renders the code-editor style inputs."""
  return dmc.Stack(
      gap="xs",
      children=[
          dmc.Grid(
              gutter="md",
              children=[
                  # User Input (2/3 width)
                  dmc.GridCol(
                      span=8,
                      children=dmc.Stack(
                          gap=4,
                          children=[
                              dmc.Group(
                                  h=20,
                                  align="flex-end",
                                  justify="space-between",
                                  children=[
                                      dmc.Text(
                                          "Assertion Logic", fw=500, size="sm"
                                      ),
                                      dmc.Anchor(
                                          "Test Regex",
                                          href="#",
                                          size="xs",
                                          c="blue",
                                          style={"display": "none"},
                                      ),
                                  ],
                              ),
                              dmc.Box(
                                  style={"position": "relative"},
                                  children=[
                                      dmc.TextInput(
                                          id=ids_class.ASSERT_VALUE,
                                          placeholder="Enter value...",
                                          style={"display": "none"},
                                          styles={
                                              "input": {
                                                  "fontFamily": "monospace",
                                              }
                                          },
                                          className="font-mono",
                                      ),
                                      dmc.Textarea(
                                          id=ids_class.ASSERT_YAML,
                                          placeholder="Enter configuration...",
                                          minRows=5,
                                          autosize=True,
                                          style={"display": "none"},
                                          styles={
                                              "input": {
                                                  "fontFamily": "monospace",
                                                  "lineHeight": "1.5rem",
                                              }
                                          },
                                          className="font-mono",
                                      ),
                                  ],
                              ),
                          ],
                      ),
                  ),
                  # Example Block (1/3 width)
                  dmc.GridCol(
                      span=4,
                      children=[
                          dmc.Stack(
                              id=ids_class.ASSERT_EXAMPLE_CONTAINER,
                              gap=4,
                              children=[
                                  dmc.Group(
                                      h=20,
                                      align="flex-end",
                                      children=[
                                          dmc.Text(
                                              "Example",
                                              size="10px",
                                              fw=700,
                                              c="dimmed",
                                              tt="uppercase",
                                              lts="0.1em",
                                          ),
                                      ],
                                  ),
                                  dmc.Box(
                                      children=[
                                          dmc.TextInput(
                                              id=ids_class.ASSERT_EXAMPLE_VALUE,
                                              readOnly=True,
                                              disabled=True,
                                              style={"display": "none"},
                                              styles={
                                                  "input": {
                                                      "fontFamily": "monospace",
                                                      "backgroundColor": (
                                                          "#f8fafc"
                                                      ),
                                                      "cursor": "not-allowed",
                                                  }
                                              },
                                              className="font-mono",
                                          ),
                                          dmc.Textarea(
                                              id=ids_class.ASSERT_EXAMPLE_YAML,
                                              readOnly=True,
                                              disabled=True,
                                              minRows=5,
                                              autosize=True,
                                              style={"display": "none"},
                                              styles={
                                                  "input": {
                                                      "fontFamily": "monospace",
                                                      "lineHeight": "1.5rem",
                                                      "backgroundColor": (
                                                          "#f8fafc"
                                                      ),
                                                      "cursor": "not-allowed",
                                                  }
                                              },
                                              className="font-mono",
                                          ),
                                      ],
                                  ),
                              ],
                          )
                      ],
                  ),
              ],
          ),
      ],
  )


def _render_accuracy_toggle(ids_class):
  """Renders the card-style accuracy toggle."""
  return dmc.Paper(
      radius="md",
      p="md",
      bg="gray.0",  # bg-slate-50 equivalent
      children=[
          dmc.Group(
              justify="space-between",
              children=[
                  dmc.Group(
                      children=[
                          dmc.ThemeIcon(
                              DashIconify(
                                  icon="material-symbols:analytics", width=24
                              ),
                              size="xl",
                              color="blue",
                              variant="light",
                              radius="md",
                          ),
                          dmc.Stack(
                              gap=0,
                              children=[
                                  dmc.Text(
                                      "Accuracy Assertion", fw=500, size="sm"
                                  ),
                                  dmc.Text(
                                      "Include this assertion result in the"
                                      " overall accuracy score.",
                                      size="xs",
                                      c="dimmed",
                                  ),
                              ],
                          ),
                      ]
                  ),
                  dmc.Switch(
                      id=ids_class.ASSERT_WEIGHT,
                      size="md",
                      color="blue",
                      checked=True,
                  ),
              ],
          ),
      ],
  )


def render_assertion_form_content(
    ids_class: type[Any],
    is_edit: bool = False,
    is_suggestion: bool = False,
):
  """Renders the common content for a assertion modal."""
  del is_edit, is_suggestion  # Unused for now

  return dmc.Stack(
      gap="lg",
      children=[
          # assertion Type Select
          dmc.Stack(
              gap="xs",
              children=[
                  dmc.Text("Assertion Type", fw=500, size="sm"),
                  dmc.Select(
                      id=ids_class.ASSERT_TYPE,
                      data=[
                          {"label": g["label"], "value": g["name"]}
                          for g in ASSERTS_GUIDE
                      ],
                      placeholder="Select Assertion Type",
                      searchable=True,
                      allowDeselect=False,
                      leftSection=DashIconify(icon="bi:search"),
                  ),
              ],
          ),
          # Dynamic Guide Card
          _render_guide_card(ids_class),
          # Logic Editor
          _render_code_editor(ids_class),
          # assertion Met Toggle
          _render_accuracy_toggle(ids_class),
          # Validation Error Message
          dmc.Alert(
              id=ids_class.VAL_MSG,
              color="red",
              variant="light",
              title="Validation Error",
              style={"display": "none"},
              icon=DashIconify(icon="material-symbols:error-outline"),
          ),
      ],
  )


def render_assertion_result_compact(result):
  """Renders a compact assertion result card.

  Args:
      result: assertionResult schema object or dict.

  Returns:
      A Dash component.
  """
  # Normalize input if it's a Pydantic model
  if hasattr(result, "model_dump"):
    result = result.model_dump()

  assertion = result.get("assertion", {})
  a_type = assertion.get("type", "Unknown")
  a_weight = assertion.get("weight", 0)
  a_val = assertion.get("value") or assertion.get("params")

  is_accuracy = a_weight > 0
  passed = result.get("passed", False)
  reason = result.get("reasoning")
  error = result.get("error_message")

  # Status Color
  status_color = "green" if passed else "red"
  if not is_accuracy and not passed:
    status_color = "orange"

  type_label = a_type.replace("-", " ").title()

  # Value/Params
  code_component = None
  if a_val:
    code_component = dmc.Code(
        str(a_val),
        block=False,
        c="dimmed",
        style={
            "fontSize": "10px",
            "maxWidth": "250px",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
            "whiteSpace": "nowrap",
        },
    )

  return dmc.Paper(
      withBorder=True,
      radius="sm",
      p="xs",
      mb="xs",
      style={
          "borderLeft": f"4px solid var(--mantine-color-{status_color}-5)",
          "backgroundColor": "var(--mantine-color-gray-0)",
      },
      children=[
          dmc.Group(
              justify="space-between",
              align="start",
              children=[
                  dmc.Stack(
                      gap=0,
                      children=[
                          dmc.Group(
                              gap="xs",
                              children=[
                                  dmc.Text(type_label, fw=600, size="sm"),
                                  dmc.Badge(
                                      "Accuracy"
                                      if is_accuracy
                                      else "Diagnostic",
                                      variant="dot",
                                      color="blue" if is_accuracy else "gray",
                                      size="xs",
                                  ),
                              ],
                          ),
                          code_component,
                      ],
                  ),
                  # Score / Status
                  dmc.Stack(
                      gap=0,
                      align="end",
                      children=[
                          dmc.Badge(
                              "PASS" if passed else "FAIL",
                              color=status_color,
                              variant="light",
                              size="sm",
                          ),
                      ],
                  ),
              ],
          ),
          # Reason / Error
          dmc.Text(reason, size="xs", mt="xs", c="dimmed", fs="italic")
          if reason
          else None,
          dmc.Text(error, size="xs", mt="xs", c="red") if error else None,
      ],
  )


def get_assertion_style(a_type: str) -> dict[str, Any]:
  """Returns icon, color, label for assertion type matching mockup."""
  # Default
  style = {
      "icon": "material-symbols:help-outline",
      "color": "gray",
      "bg": "gray",
      "label": "assertion",
      "badge": "CHECK",
      "desc": "Validates the response.",
  }

  if a_type == "text-contains" or a_type == "text-exact-match":
    style.update({
        "icon": "material-symbols:text-fields",
        "color": "blue",
        "bg": "blue",  # blue-50 equivalent handled in component
        "label": "Text Contains",
        "badge": "STRING",
        "desc": (
            "Validates that the response text contains a specific substring."
        ),
    })
  elif a_type == "looker-query-match":
    style.update({
        "icon": "material-symbols:query-stats",
        "color": "pink",
        "bg": "pink",
        "label": "Looker Query Match",
        "badge": "LOOKML",
        "desc": "Matches Looker query parameters using YAML configuration.",
    })
  elif a_type == "data-check-row":
    style.update({
        "icon": "material-symbols:table-rows",
        "color": "teal",  # emerald equivalent
        "bg": "teal",
        "label": "Data Check Row",
        "badge": "DATA",
        "desc": "Validates values in specific columns of the result row.",
    })
  elif a_type == "data-check-row-count":
    style.update({
        "icon": "material-symbols:format-list-numbered",
        "color": "cyan",
        "bg": "cyan",
        "label": "Data Check Row Count",
        "badge": "DATA",
        "desc": "Checks the number of rows in the result.",
    })
  elif a_type == "chart-check-type":
    style.update({
        "icon": "material-symbols:bar-chart",
        "color": "indigo",
        "bg": "indigo",
        "label": "Chart Check Type",
        "badge": "CHART",
        "desc": "Checks if the chart type matches the expected type.",
    })
  elif a_type == "query-contains" or a_type == "sql-valid":
    style.update({
        "icon": "material-symbols:manage-search",
        "color": "orange",  # amber equivalent
        "bg": "orange",
        "label": "Query Contains",
        "badge": "SQL",
        "desc": "Checks if the generated SQL contains specific keywords.",
    })
  elif a_type == "custom":
    style.update({
        "icon": "material-symbols:code",
        "color": "violet",
        "bg": "violet",
        "label": "Custom Python",
        "badge": "PYTHON",
        "desc": "Executes custom Python logic for validation.",
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
        "desc": "Ensures response time does not exceed threshold.",
    })
  elif a_type == "llm-evaluation":
    style.update({
        "icon": "material-symbols:psychology",
        "color": "grape",
        "bg": "grape",
        "label": "LLM Evaluation",
        "badge": "TONE",
        "desc": "Validates the politeness and tone of the response.",
    })
  elif a_type == "regex-match":
    style.update({
        "icon": "material-symbols:code",
        "color": "emerald",
        "bg": "emerald",
        "label": "Regex Pattern",
        "badge": "MATCH",
        "desc": "Checks for specific keywords using regex.",
    })
  elif a_type == "sentiment-score":
    style.update({
        "icon": "material-symbols:mood",
        "color": "sky",
        "bg": "sky",
        "label": "Sentiment Analysis",
        "badge": "SCORE",
        "desc": "Monitors sentiment trends over turns.",
    })
  elif a_type == "resolution-confirmation":
    style.update({
        "icon": "material-symbols:verified",
        "color": "orange",
        "bg": "orange",
        "label": "Resolution Confirmation",
        "badge": "SCRIPT",
        "desc": "Verify explicit confirmation.",
    })
  elif a_type == "ai-judge":
    style.update({
        "icon": "material-symbols:psychology",
        "color": "grape",
        "bg": "grape",
        "label": "AI Judge",
        "badge": "LLM",
        "desc": "Uses an LLM to evaluate the response based on criteria.",
    })

  return style


def _render_assertion_content(a_type: str, assertion: dict[str, Any]):
  """Renders the content block for the assertion card."""
  if a_type in ["duration-max-ms", "latency-max-ms"]:
    val = assertion.get("value", "0")
    return dmc.Box(
        bg="#f8fafc",  # slate-50
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Text(f"{val} ms", c="grape", fw=700, ff="mono", size="sm"),
    )

  if a_type == "data-check-row-count":
    val = assertion.get("value", "0")
    return dmc.Box(
        bg="#f8fafc",
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Text(str(val), c="cyan", fw=700, ff="mono", size="sm"),
    )

  if a_type == "chart-check-type":
    val = assertion.get("value", "unknown")
    return dmc.Box(
        bg="#f8fafc",
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Text(
            val.upper(), c="indigo", fw=700, ff="mono", size="sm"
        ),
    )

  if a_type == "data-check-row":
    # Render Columns Dictionary
    columns = assertion.get("columns", {})
    if not columns and "value" in assertion:
      # Fallback if stored differently
      try:
        columns = json.loads(assertion["value"])
      except (ValueError, TypeError):
        columns = {}

    if not columns:
      return None

    grid_children = []
    for k, v in columns.items():
      # Key
      grid_children.append(
          dmc.Text(f"{k}:", c="dimmed", ta="right", ff="mono", size="sm")
      )
      # Value (Styled)
      color = "teal" if isinstance(v, str) else "blue"
      if isinstance(v, (int, float)) or (
          isinstance(v, str) and (">" in v or "<" in v)
      ):
        color = "violet"

      grid_children.append(
          dmc.Text(str(v), fw=600, c=color, ff="mono", size="sm")
      )

    return dmc.Box(
        bg="gray.0",  # slate-50
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=[
            dmc.Text(
                "Columns",
                size="10px",
                fw=700,
                c="dimmed",
                tt="uppercase",
                lts="0.1em",
                mb="xs",
            ),
            dmc.SimpleGrid(
                cols=2,
                spacing="xs",
                verticalSpacing="xs",
                children=grid_children,
                style={"gridTemplateColumns": "auto 1fr"},
            ),
        ],
    )

  elif a_type == "looker-query-match":
    return _render_assertion_value_display(a_type, assertion, is_table=False)

  elif a_type in ["text-contains", "text-exact-match"]:
    val = assertion.get("value", "")
    return dmc.Box(
        bg="#f8fafc",  # slate-50
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Code(
            f'"{val}"',
            c="dark",
            bg="transparent",
            style={"fontSize": "14px", "fontFamily": "monospace"},
        ),
    )

  elif a_type in ["query-contains", "sql-valid"]:
    val = assertion.get("value", "")
    return dmc.Box(
        bg="#f8fafc",  # slate-50
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Code(
            val,
            c="dark",
            bg="transparent",
            style={"fontSize": "14px", "fontFamily": "monospace"},
        ),
    )

  elif a_type == "ai-judge":
    val = assertion.get("value", "")
    return dmc.Box(
        bg="grape.0",
        p="md",
        style={
            "borderRadius": "8px",
            "border": "1px solid var(--mantine-color-grape-2)",
        },
        children=dmc.Text(val, size="sm", c="grape.9"),
    )

  return None


def render_assertion_result_card(
    assertion: dict[str, Any],
    result: dict[str, Any] | None = None,
    is_suggestion: bool = False,
    index: int = 0,
    ids_class: Any = None,
):
  """Renders a simple, reusable assertion result card matching the mockup."""
  a_type = assertion.get("type", "unknown")
  weight = assertion.get("weight", 0)
  is_accuracy = weight > 0
  if hasattr(a_type, "value"):
    a_type = a_type.value
  style = get_assertion_style(a_type)

  # Title: Use name from params if available, else style label
  title = (
      assertion.get("name") or assertion.get("description") or style["label"]
  )

  # Normalize result
  result = result or assertion.get("result") or {}
  passed = result.get("passed", False)
  reason = result.get("reasoning") or "No reason provided."

  # Colors and Icons
  if is_suggestion:
    border_color = "var(--mantine-color-grape-4)"
    status_badge = dmc.Badge(
        "AI",
        variant="light",
        color="grape",
        size="xs",
        radius="sm",
    )
    footer = None
  else:
    status_color = "teal" if passed else "red"
    border_color = f"var(--mantine-color-{status_color}-5)"
    status_badge = dmc.Badge(
        [
            DashIconify(
                icon="mi:check" if passed else "mi:close",
                width=14,
                style={"marginRight": "4px"},
            ),
            "PASS" if passed else "FAIL",
        ],
        variant="outline",
        color=status_color,
        size="sm",
        radius="xs",
        styles={
            "label": {
                "display": "flex",
                "alignItems": "center",
                "fontWeight": 700,
            }
        },
    )

    footer_bg = f"var(--mantine-color-{status_color}-0)"
    footer_border = f"var(--mantine-color-{status_color}-1)"
    footer_text_color = f"var(--mantine-color-{status_color}-9)"

    footer = dmc.Box(
        p="sm",
        px="xl",
        style={
            "backgroundColor": footer_bg,
            "borderTop": f"1px solid {footer_border}",
        },
        children=dmc.Text(reason, size="sm", c=footer_text_color),
    )

  # Content Rendering
  # Normalize a_type for pseudo-code logic
  a_type_str = a_type.value if hasattr(a_type, "value") else str(a_type)

  content_box = _render_assertion_content(a_type_str, assertion)

  # Suggestion Actions
  actions = None
  if is_suggestion and ids_class:
    actions = dmc.Group(
        grow=True,
        gap="sm",
        mt="md",
        children=[
            dmc.Button(
                "Accept",
                id={"type": ids_class.INLINE_SUG_ADD_BTN, "index": index},
                variant="outline",
                color="blue",
                size="xs",
                leftSection=DashIconify(icon="mi:add-circle"),
            ),
            dmc.Button(
                "Reject",
                id={"type": ids_class.INLINE_SUG_REJECT_BTN, "index": index},
                variant="subtle",
                color="gray",
                size="xs",
            ),
        ],
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      shadow="xs",
      style={
          "borderColor": border_color,
          "borderWidth": "1.5px",
          "overflow": "hidden",
          "display": "flex",
          "flexDirection": "column",
          "height": "100%",
          "borderStyle": "dashed" if is_suggestion else "solid",
      },
      children=[
          dmc.Stack(
              p="xl",
              gap="md",
              style={"flex": 1},
              children=[
                  dmc.Group(
                      justify="space-between",
                      align="start",
                      children=[
                          dmc.Group(
                              gap="xs",
                              style={"flex": 1},
                              children=[
                                  dmc.Text(title, fw=700, size="md"),
                                  dmc.Text(
                                      "Accuracy"
                                      if is_accuracy
                                      else "Diagnostic",
                                      size="10px",
                                      fw=700,
                                      c="dimmed",
                                      tt="uppercase",
                                      lts="0.1em",
                                  )
                                  if not is_suggestion
                                  else None,
                              ],
                          ),
                          status_badge,
                      ],
                  ),
                  content_box,
                  dmc.Text(
                      assertion.get("reasoning", ""), size="xs", c="dimmed"
                  )
                  if is_suggestion and assertion.get("reasoning")
                  else None,
                  actions,
              ],
          ),
          footer,
      ],
  )


def render_assertion_card(
    assertion: dict[str, Any],
    index: int,
    is_suggestion: bool = False,
    suggestion_actions: Any = None,
    result: dict[str, Any] | None = None,
    ids_class: Any = Ids,
    show_actions: bool = True,
):
  """Renders a detailed assertion card matching the mockup."""
  a_type = assertion.get("type", "unknown")
  weight = assertion.get("weight", 0)
  is_accuracy = weight > 0

  style = get_assertion_style(a_type)
  content = _render_assertion_content(a_type, assertion)

  # Determine actions (Edit/Delete vs Custom Suggestion Actions)
  action_buttons = None
  if show_actions:
    if is_suggestion and suggestion_actions:
      action_buttons = suggestion_actions
    else:
      action_buttons = dmc.Group(
          gap=4,
          children=[
              dmc.ActionIcon(
                  DashIconify(icon="material-symbols:edit", width=20),
                  id={"type": ids_class.ASSERT_EDIT_BTN, "index": index},
                  variant="subtle",
                  color="gray",
                  size="lg",
                  className=(
                      "hover:bg-blue-50 hover:text-blue-600 transition-colors"
                  ),
              )
              if hasattr(ids_class, "ASSERT_EDIT_BTN")
              else None,
              dmc.ActionIcon(
                  DashIconify(icon="material-symbols:delete", width=20),
                  id={
                      "type": ids_class.Q_REMOVE_ASSERTION_BTN,
                      "index": index,
                  },
                  variant="subtle",
                  color="gray",
                  size="lg",
                  className=(
                      "hover:bg-red-50 hover:text-red-600 transition-colors"
                  ),
              )
              if hasattr(ids_class, "Q_REMOVE_ASSERTION_BTN")
              else None,
          ],
      )

  # Result Footer
  result_footer = None
  result = result or assertion.get("result")
  if result:
    passed = result.get("passed", False)
    reason = result.get("reasoning", "No reason provided.")
    error = result.get("error_message")

    status_color = "teal" if passed else "red"
    icon = None if passed else "material-symbols:warning-amber-rounded"

    footer_children = []
    if icon:
      footer_children.append(
          DashIconify(
              icon=icon,
              color=f"var(--mantine-color-{status_color}-6)",
              width=20,
              style={"marginTop": "2px", "minWidth": "20px"},
          )
      )

    footer_children.append(
        dmc.Box(
            children=[
                dmc.Text(
                    children=[
                        html.Span("Result: ", style={"fontWeight": 700}),
                        reason,
                    ],
                    size="sm",
                    c=f"{status_color}.9",
                ),
                dmc.Text(
                    f"Error: {error}",
                    size="xs",
                    c="red.8",
                    fw=600,
                    mt=4,
                )
                if error
                else None,
            ]
        )
    )

    result_footer = dmc.Box(
        p="md",
        className=(
            f"rounded-xl border mt-4 {'flex items-start gap-3' if icon else ''}"
        ),
        style={
            "backgroundColor": f"var(--mantine-color-{status_color}-0)",
            "borderColor": f"var(--mantine-color-{status_color}-2)",
        },
        children=footer_children,
    )

  paper_style = {}
  if result:
    passed = result.get("passed", False)
    p_color = "teal" if passed else "red"
    paper_style = {
        "borderColor": f"var(--mantine-color-{p_color}-4)",
        "borderWidth": "1.5px",
        "backgroundColor": "white",
    }

  content_box = None
  if content:
    content_box = dmc.Box(
        pl="4.5rem",  # Indent to align with text
        pr="md",
        pb="md",
        children=content,
    )

  footer_box = None
  if result_footer:
    footer_box = dmc.Box(
        pl="4.5rem",
        pr="md",
        pb="md",
        children=result_footer,
    )

  return dmc.Paper(
      radius="md",
      withBorder=True,
      mb="md",
      style=paper_style,
      className=(
          "group transition-all duration-200 hover:border-blue-200 shadow-sm"
      ),
      children=[
          # Header
          dmc.Group(
              justify="space-between",
              p="md",
              className="cursor-pointer hover:bg-slate-50/50 transition-colors",
              children=[
                  # Left: Icon + Text
                  dmc.Group(
                      children=[
                          dmc.ThemeIcon(
                              DashIconify(icon=style["icon"], width=24),
                              size=40,  # size-10 equivalent
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
                                              style["label"],
                                              fw=700,
                                              size="sm",
                                              c="dark",
                                          ),
                                          dmc.Badge(
                                              style.get("badge", "CHECK"),
                                              size="xs",
                                              color=style["color"],
                                              variant="light",
                                              radius="md",
                                              style={
                                                  "fontWeight": 700,
                                                  "letterSpacing": "0.05em",
                                              },
                                          ),
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
                      gap="md",
                      children=[
                          # Accuracy Toggle
                          dmc.Tooltip(
                              label=(
                                  "Accuracy assertions contribute to the"
                                  " overall score. Diagnostic assertions"
                                  " (Accuracy OFF) are used for monitoring"
                                  " without affecting the score."
                              ),
                              position="top",
                              withArrow=True,
                              children=dmc.Group(
                                  gap="xs",
                                  children=[
                                      dmc.Text(
                                          "ACCURACY"
                                          if is_accuracy
                                          else "DIAGNOSTIC",
                                          size="10px",
                                          fw=700,
                                          c="dimmed",
                                          tt="uppercase",
                                          lts="0.05em",
                                      ),
                                      dmc.Switch(
                                          checked=is_accuracy,
                                          id={
                                              "type": (
                                                  ids_class.ASSERT_TOGGLE_ACCURACY
                                              ),
                                              "index": index,
                                          },
                                          size="sm",
                                          color="blue",
                                      )
                                      if hasattr(
                                          ids_class,
                                          "ASSERT_TOGGLE_ACCURACY",
                                      )
                                      else None,
                                  ],
                              ),
                          ),
                          dmc.Divider(orientation="vertical", h=20),
                          # Edit / Delete Buttons or Custom Actions
                          action_buttons,
                      ],
                  ),
              ],
          ),
          # Content Block
          content_box,
          # Result Footer (New)
          footer_box,
      ],
  )


def render_suggested_assertion_card(
    suggestion: dict[str, Any],
    index: int,
    action_buttons: list[dmc.Button | dmc.ActionIcon] | None = None,
    ids_class: Any = Ids,
):
  """Renders a suggested assertion card (Amber theme)."""
  a_type = suggestion.get("type", "unknown")
  style = get_assertion_style(a_type)
  content = _render_assertion_content(a_type, suggestion)

  content_box = None
  if content:
    content_box = dmc.Box(
        children=content,
        className="bg-white/80 rounded-lg border border-slate-200 shadow-sm",
    )

  # Actions row
  actions_row = dmc.Group(
      gap="sm",
      justify="end",
      mt="md",
      children=action_buttons
      if action_buttons is not None
      else [
          dmc.Button(
              "Accept",
              id={
                  "type": ids_class.INLINE_SUG_ADD_BTN,
                  "index": index,
              },
              leftSection=DashIconify(
                  icon="material-symbols:check",
                  width=16,
              ),
              color="grape",
              size="xs",
              radius="md",
              px="md",
          ),
          dmc.Button(
              "Reject",
              id={
                  "type": ids_class.INLINE_SUG_REJECT_BTN,
                  "index": index,
              },
              leftSection=DashIconify(
                  icon="material-symbols:close",
                  width=16,
              ),
              variant="subtle",
              color="grape",
              size="xs",
              radius="md",
              px="md",
          ),
      ],
  )

  return dmc.Paper(
      radius="md",
      withBorder=True,
      bg="grape.0",
      className=(
          "group transition-all duration-200 hover:border-grape-400"
          " overflow-hidden"
      ),
      style={"borderColor": "var(--mantine-color-grape-2)"},
      p="md",
      mb="md",
      children=[
          dmc.Group(
              align="start",
              gap="md",
              wrap="nowrap",
              children=[
                  # Icon
                  dmc.ThemeIcon(
                      DashIconify(icon=style["icon"], width=20),
                      size=32,
                      radius="md",
                      color=style["color"],
                      variant="light",
                      className="border border-white/50 shadow-sm",
                  ),
                  # Info + Content
                  dmc.Stack(
                      gap="sm",
                      style={"flex": 1},
                      children=[
                          dmc.Stack(
                              gap=2,
                              children=[
                                  dmc.Group(
                                      gap="xs",
                                      children=[
                                          dmc.Text(
                                              style["label"],
                                              fw=700,
                                              size="sm",
                                              c="slate.9",
                                          ),
                                          dmc.Badge(
                                              style.get("badge", "CHECK"),
                                              size="xs",
                                              color=style["color"],
                                              variant="light",
                                              radius="md",
                                          ),
                                      ],
                                  ),
                                  dmc.Text(
                                      suggestion.get(
                                          "reasoning", style["desc"]
                                      ),
                                      size="xs",
                                      c="dimmed",
                                      lh=1.4,
                                  ),
                              ],
                          ),
                          # Card Content (Code/Pattern)
                          content_box,
                          # Actions at the bottom of the stack
                          actions_row,
                      ],
                  ),
              ],
          )
      ],
  )


def render_suggestion_skeleton():
  """Renders a grid of skeletons for suggested assertion."""
  skeleton_card = dmc.Paper(
      radius="md",
      withBorder=True,
      p="md",
      mb="md",
      children=[
          dmc.Group(
              align="start",
              gap="md",
              wrap="nowrap",
              children=[
                  dmc.Skeleton(height=32, width=32, radius="md"),
                  dmc.Stack(
                      gap="xs",
                      style={"flex": 1},
                      children=[
                          dmc.Skeleton(height=16, width="40%"),
                          dmc.Skeleton(height=12, width="90%"),
                          dmc.Skeleton(height=60, radius="md"),
                          dmc.Group(
                              justify="end",
                              children=[
                                  dmc.Skeleton(height=28, width=80),
                                  dmc.Skeleton(height=28, width=60),
                              ],
                          ),
                      ],
                  ),
              ],
          )
      ],
  )
  return dmc.SimpleGrid(cols=2, spacing="lg", children=[skeleton_card] * 4)


def render_empty_suggestions(button_id: str | dict | None = None):
  """Renders a high-fidelity empty state for assertion suggestions."""
  children = [
      dmc.ThemeIcon(
          DashIconify(icon="bi:stars", width=24),
          size=50,
          radius="md",
          variant="light",
          color="grape",
      ),
      dmc.Text("No suggestions yet.", fw=700, size="lg"),
      dmc.Text(
          "Generate new assertion to get AI-powered insights"
          " based on this execution's trace.",
          c="dimmed",
          size="sm",
          ta="center",
          maw=300,
      ),
  ]

  if button_id:
    children.append(
        dmc.Button(
            "Suggest Assertions",
            id=button_id,
            leftSection=DashIconify(icon="bi:magic"),
            variant="filled",
            color="grape",
            radius="md",
            mt="md",
        )
    )

  return dmc.Center(
      py=40,
      children=[
          dmc.Stack(
              align="center",
              gap="sm",
              children=children,
          )
      ],
  )


def render_assertion_empty():
  """Renders a high-fidelity empty state for assertion."""
  return dmc.Center(
      py=40,
      children=[
          dmc.Stack(
              align="center",
              gap="sm",
              children=[
                  dmc.ThemeIcon(
                      DashIconify(icon="bi:clipboard-check", width=24),
                      size=50,
                      radius="md",
                      variant="light",
                      color="gray",
                  ),
                  dmc.Text("No assertions found.", fw=700, size="lg"),
                  dmc.Text(
                      "Check your filters or ensure assertions are defined"
                      " for this trial.",
                      c="dimmed",
                      size="sm",
                      ta="center",
                      maw=300,
                  ),
              ],
          )
      ],
  )


def render_assertion_summary(summary: AssertionSummary) -> dmc.SimpleGrid:
  """Renders a summary of assertion results with RingProgress charts."""

  def render_metric_card(
      label: str, metric: AssertionMetric, color: str, icon: str
  ) -> dmc.Paper:
    """Renders a single metric card with a ThemeIcon and status details."""
    return dmc.Paper(
        withBorder=True,
        radius="md",
        p="md",
        shadow="sm",
        children=[
            dmc.Group(
                align="center",
                gap="xs",
                mb="xs",
                children=[
                    dmc.ThemeIcon(
                        DashIconify(icon=icon, width=18),
                        variant="light",
                        color=color,
                        radius="md",
                        size="md",
                    ),
                    dmc.Text(
                        label,
                        size="xs",
                        fw=700,
                        c="dimmed",
                        tt="uppercase",
                        lts="0.05em",
                    ),
                ],
            ),
            dmc.Group(
                justify="space-between",
                align="flex-end",
                children=[
                    dmc.Text(
                        f"{metric.pass_rate:.1f}%"
                        if metric.pass_rate is not None
                        else "N/A",
                        size="xl",
                        fw=700,
                        c="dark",
                    ),
                    dmc.Text(
                        f"{metric.passed} / {metric.total} Passed",
                        size="sm",
                        c="dimmed",
                        fw=500,
                        mb=4,  # Subtle alignment adjustment
                    ),
                ],
            ),
        ],
    )

  return dmc.SimpleGrid(
      cols={"base": 1, "md": 3},
      spacing="lg",
      children=[
          render_metric_card(
              "Combined", summary.overall, "blue", "bi:layers-fill"
          ),
          render_metric_card(
              "Accuracy", summary.accuracy, "yellow", "bi:trophy-fill"
          ),
          render_metric_card(
              "Diagnostic", summary.diagnostic, "indigo", "bi:activity"
          ),
      ],
  )


def get_assertion_result_key(ar: Any) -> str:
  """Gets a unique key for an assertion to align them."""
  # Normalize to dict if pydantic
  if hasattr(ar, "model_dump"):
    ar = ar.model_dump()
  assertion = ar.get("assertion", {})

  # 1. Prioritize original_assertion_id for stable alignment across runs
  # This corresponds to the ID in the live 'assertions' table.
  if assertion.get("original_assertion_id"):
    return f"orig-{assertion['original_assertion_id']}"

  # 2. Fallback to content-based matching for ad-hoc assertions or missing IDs
  # We do NOT use assertion.get('id') here because that is often the Snapshot ID,
  # which changes for every run and prevents alignment.
  a_type = assertion.get("type", "unknown")
  a_val = str(assertion.get("value", ""))
  if not a_val and "params" in assertion:
    # Use sorted params string for deterministic comparison
    params = assertion["params"]
    if isinstance(params, dict):
      a_val = str(sorted(params.items()))
    else:
      a_val = str(params)

  return f"content-{a_type}-{a_val}"


def _format_assertion_value(assertion: Any) -> str:
  """Formats assertion value for table display."""
  if hasattr(assertion, "model_dump"):
    assertion = assertion.model_dump()

  a_type = assertion.get("type", "unknown")
  if a_type in ["duration-max-ms", "latency-max-ms"]:
    return f"{assertion.get('value', 0)}ms"

  if a_type == "looker-query-match":
    params = assertion.get("params", {})
    if params:
      return yaml.dump(
          params, sort_keys=False, default_flow_style=False
      ).strip()
    return assertion.get("yaml_config") or ""

  if a_type == "data-check-row":
    columns = assertion.get("columns", {})
    if columns:
      return yaml.dump(
          columns, sort_keys=False, default_flow_style=False
      ).strip()

  val = assertion.get("value", "")
  if isinstance(val, (dict, list)):
    return yaml.dump(val, sort_keys=False, default_flow_style=False).strip()

  if isinstance(val, str) and val:
    return f'"{val}"'
  return str(val)


def _render_assertion_value_display(
    a_type: str, assertion: dict[str, Any], is_table: bool = False
):
  """Renders the value display component for an assertion."""
  if a_type == "looker-query-match":
    params = assertion.get("params", {})
    yaml_str = assertion.get("yaml_config")

    rows = []
    # Title/Header
    rows.append(
        dmc.Text(
            "LOOKML",
            size="10px",
            fw=700,
            c="dimmed",
            tt="uppercase",
            lts="0.1em",
            mb="xs",
        ),
    )

    if isinstance(params, dict) and params:
      # Reuse the "formatted" Looker query params style
      for k, v in params.items():
        if not v:
          continue
        rows.append(
            dmc.Group(
                gap=4,
                children=[
                    dmc.Text(f"{k}:", c="pink.3", ff="mono", size="xs"),
                    dmc.Text(json.dumps(v), c="yellow.2", ff="mono", size="xs"),
                ],
            )
        )
    elif yaml_str:
      rows.append(
          dmc.Code(
              yaml_str, block=True, color="dark", style={"fontSize": "12px"}
          )
      )

    bg = "#1e293b" if not is_table else "var(--mantine-color-gray-9)"
    border = "#334155" if not is_table else "var(--mantine-color-gray-8)"

    return dmc.Box(
        bg=bg,
        p="sm" if not is_table else "xs",
        style={
            "borderRadius": "4px",
            "border": f"1px solid {border}",
        },
        children=dmc.Stack(gap=2, children=rows),
    )

  # Default to YAML dump for other complex types or the requested types
  if a_type == "data-check-row" or not isinstance(
      assertion.get("value"), (str, int, float, bool)
  ):
    val_str = _format_assertion_value(assertion)
    if "\n" in val_str:
      return dmc.Code(
          val_str,
          block=True,
          style={
              "fontSize": "11px",
              "fontFamily": "var(--font-mono)",
              "backgroundColor": "var(--mantine-color-gray-0)",
              "border": "1px solid var(--mantine-color-gray-2)",
              "color": "var(--mantine-color-gray-8)",
              "padding": "4px 8px",
              "borderRadius": "4px",
          },
      )

  # Fallback to standard code representation
  return dmc.Code(
      _format_assertion_value(assertion),
      style={
          "fontSize": "11px",
          "fontFamily": "var(--font-mono)",
          "backgroundColor": "var(--mantine-color-gray-0)",
          "border": "1px solid var(--mantine-color-gray-2)",
          "color": "var(--mantine-color-gray-8)",
          "padding": "2px 6px",
          "borderRadius": "4px",
          "display": "inline-block",
          "whiteSpace": "pre-wrap",
      },
  )


def render_assertion_diagnostic_table(
    base_trial: Trial | None, chal_trial: Trial | None
) -> dmc.Table:
  """Renders a detailed table comparing assertion results between two trials."""
  # 1. Align assertions
  base_results = (
      {get_assertion_result_key(ar): ar for ar in base_trial.assertion_results}
      if base_trial
      else {}
  )
  chal_results = (
      {get_assertion_result_key(ar): ar for ar in chal_trial.assertion_results}
      if chal_trial
      else {}
  )

  all_keys = list(base_results.keys() | chal_results.keys())

  # Sort keys: Regressions first, then by type
  def sort_key(k: str) -> tuple[int, str]:
    br = base_results.get(k)
    cr = chal_results.get(k)
    # Regression = Baseline passed, candidate failed
    is_regression = br and br.passed and cr and not cr.passed
    return (0 if is_regression else 1, k)

  all_keys.sort(key=sort_key)

  rows = []
  for key in all_keys:
    base_ar = base_results.get(key)
    chal_ar = chal_results.get(key)

    # Use whichever assertion definition is available
    ar = chal_ar or base_ar
    if not ar:
      continue
    assertion = ar.assertion
    style = get_assertion_style(assertion.type)

    # Kind / Status
    status_label = "STABLE"
    status_color = "gray"

    if base_ar and chal_ar:
      if chal_ar.passed and not base_ar.passed:
        status_label = "IMPROVED"
        status_color = "green"
      elif base_ar.passed and not chal_ar.passed:
        status_label = "REGRESSED"
        status_color = "red"
      elif not base_ar.passed and not chal_ar.passed:
        status_label = "FAILED"
        status_color = "red"
    elif chal_ar:
      status_label = "NEW"
      status_color = "blue"
    else:
      status_label = "REMOVED"
      status_color = "gray"

    rows.append(
        html.Tr(
            children=[
                # Type
                html.Td(
                    dmc.Group(
                        gap="sm",
                        children=[
                            dmc.ThemeIcon(
                                DashIconify(icon=style["icon"], width=16),
                                size="sm",
                                variant="light",
                                color=style["color"],
                                radius="sm",
                            ),
                            dmc.Text(style["label"], size="sm", fw=500),
                        ],
                    ),
                    style={"padding": "16px 24px"},
                ),
                # Value
                html.Td(
                    dmc.Code(
                        _format_assertion_value(assertion),
                        style={
                            "fontSize": "11px",
                            "fontFamily": "var(--font-mono)",
                            "backgroundColor": "var(--mantine-color-gray-0)",
                            "border": "1px solid var(--mantine-color-gray-2)",
                            "color": "var(--mantine-color-gray-8)",
                            "padding": "2px 6px",
                            "borderRadius": "4px",
                            "display": "inline-block",
                            "whiteSpace": "pre-wrap",
                        },
                    ),
                    style={"padding": "16px 24px"},
                ),
                # Status
                html.Td(
                    dmc.Badge(
                        status_label,
                        color=status_color,
                        variant="light",
                        size="xs",
                        radius="xs",
                        fw=700,
                    ),
                    style={"padding": "16px 24px"},
                ),
                # Baseline Reason
                html.Td(
                    dmc.Group(
                        gap="xs",
                        align="start",
                        wrap="nowrap",
                        children=[
                            dmc.Box(
                                style={
                                    "width": 8,
                                    "height": 8,
                                    "borderRadius": "50%",
                                    "backgroundColor": (
                                        "var(--mantine-color-green-6)"
                                        if base_ar.passed
                                        else "var(--mantine-color-red-6)"
                                    ),
                                    "marginTop": "6px",
                                    "flexShrink": 0,
                                }
                            ),
                            dmc.Text(
                                base_ar.reasoning or "--",
                                size="xs",
                                c="dimmed",
                                lh=1.5,
                            ),
                        ],
                    )
                    if base_ar
                    else dmc.Text("N/A", size="xs", c="dimmed", lh=1.5),
                    style={"padding": "16px 24px"},
                ),
                # Candidate Reason
                html.Td(
                    dmc.Group(
                        gap="xs",
                        align="start",
                        wrap="nowrap",
                        children=[
                            dmc.Box(
                                style={
                                    "width": 8,
                                    "height": 8,
                                    "borderRadius": "50%",
                                    "backgroundColor": (
                                        "var(--mantine-color-green-6)"
                                        if chal_ar.passed
                                        else "var(--mantine-color-red-6)"
                                    ),
                                    "marginTop": "6px",
                                    "flexShrink": 0,
                                }
                            ),
                            dmc.Text(
                                chal_ar.reasoning or "--",
                                size="xs",
                                c=(
                                    "#e03131"  # red-7 for high contrast
                                    if status_label == "REGRESSED"
                                    else "dimmed"
                                ),
                                lh=1.5,
                            ),
                        ],
                    )
                    if chal_ar
                    else dmc.Text("N/A", size="xs", c="dimmed", lh=1.5),
                    style={"padding": "16px 24px"},
                ),
            ]
        )
    )

  return dmc.Paper(
      html.Div(
          dmc.Table(
              children=[
                  html.Thead(
                      html.Tr(
                          [
                              html.Th(
                                  "TYPE",
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
                                  "VALUE",
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
                                  },
                              ),
                              html.Th(
                                  "BASELINE REASON",
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
                                  "CANDIDATE REASON",
                                  style={
                                      "fontSize": "11px",
                                      "fontWeight": 600,
                                      "color": "var(--mantine-color-gray-5)",
                                      "letterSpacing": "0.05em",
                                      "padding": "16px 24px",
                                      "textAlign": "left",
                                  },
                              ),
                          ],
                          style={
                              "backgroundColor": "var(--mantine-color-gray-0)",
                              "borderBottom": (
                                  "1px solid var(--mantine-color-gray-2)"
                              ),
                          },
                      )
                  ),
                  html.Tbody(rows),
              ],
              withTableBorder=False,
              withColumnBorders=False,
              withRowBorders=True,
              verticalSpacing=0,
              horizontalSpacing=0,
              style={"backgroundColor": "white"},
          ),
          style={"overflowX": "auto"},
      ),
      withBorder=True,
      radius="md",
      shadow="sm",
      style={
          "overflow": "hidden",
          "borderTopLeftRadius": 0,
          "borderTopRightRadius": 0,
      },
  )


def render_assertion_diagnostic_accordion(
    base_trial: Trial | None, chal_trial: Trial | None, logical_id: str
) -> dmc.Accordion:
  """Renders the full diagnostic view as an accordion."""

  base_results = base_trial.assertion_results if base_trial else []
  chal_results = chal_trial.assertion_results if chal_trial else []

  # Calculate regressions
  base_passed_keys = {
      get_assertion_result_key(ar) for ar in base_results if ar.passed
  }
  regressions = [
      ar
      for ar in chal_results
      if not ar.passed and get_assertion_result_key(ar) in base_passed_keys
  ]
  regression_count = len(regressions)

  control = dmc.Group(
      gap="sm",
      children=[
          dmc.Text(
              "ASSERTION DIAGNOSTIC VIEW",
              size="xs",
              fw=700,
              c="dimmed",
              style={"letterSpacing": "0.1em"},
          ),
          dmc.Badge(
              f"{regression_count} Regressions",
              color="red",
              variant="light",
              size="xs",
              radius="sm",
          )
          if regression_count > 0
          else None,
      ],
  )

  return dmc.Accordion(
      id={
          "type": ComparisonIds.TrialDiagnostic.ACCORDION,
          "index": logical_id,
      },
      chevronPosition="right",
      variant="default",
      styles={
          "item": {"border": "none"},
          "control": {
              "padding": "8px 24px",
              "backgroundColor": "white",
              "borderTop": "1px solid var(--mantine-color-gray-2)",
          },
          "panel": {
              "padding": "0",
              "backgroundColor": "white",
          },
          "content": {"padding": "0"},
      },
      children=[
          dmc.AccordionItem(
              value="diagnostic",
              children=[
                  dmc.AccordionControl(control),
                  dmc.AccordionPanel(
                      children=[
                          render_assertion_diagnostic_table(
                              base_trial, chal_trial
                          ),
                      ]
                  ),
              ],
          )
      ],
  )


def render_assertion_results_table(
    assertion_details: list[dict[str, Any]],
) -> dmc.Table:
  """Renders a table of assertion results."""
  rows = []
  for item in assertion_details:
    a_type = item.get("type", "unknown")
    style = get_assertion_style(a_type)
    passed = item.get("passed", False)
    status_color = "teal" if passed else "red"
    status_label = "PASS" if passed else "FAIL"

    rows.append(
        html.Tr(
            children=[
                # Status
                html.Td(
                    dmc.Badge(
                        status_label,
                        color=status_color,
                        variant="light",
                        size="xs",
                        radius="xs",
                        fw=700,
                    ),
                    style={"padding": "16px 24px", "width": "100px"},
                ),
                # Kind
                html.Td(
                    dmc.Tooltip(
                        label=(
                            "Accuracy assertions contribute to the overall"
                            " score. Diagnostic assertions (Accuracy OFF) are"
                            " used for monitoring without affecting the score."
                        ),
                        position="top",
                        withArrow=True,
                        children=dmc.Text(
                            "Accuracy"
                            if item.get("weight", 0) > 0
                            else "Diagnostic",
                            size="sm",
                        ),
                    ),
                    style={"padding": "16px 24px", "width": "120px"},
                ),
                # Type
                html.Td(
                    dmc.Group(
                        gap="sm",
                        children=[
                            dmc.ThemeIcon(
                                DashIconify(icon=style["icon"], width=14),
                                size="sm",
                                variant="light",
                                color=style["color"],
                                radius="sm",
                            ),
                            dmc.Text(style["label"], size="sm", fw=500),
                        ],
                    ),
                    style={"padding": "16px 24px", "whiteSpace": "nowrap"},
                ),
                # Value
                html.Td(
                    _render_assertion_value_display(
                        a_type, item, is_table=True
                    ),
                    style={"padding": "16px 24px"},
                ),
                # Reasoning
                html.Td(
                    dmc.Text(
                        item.get("reasoning")
                        or item.get("error_message")
                        or "--",
                        size="xs",
                        c="dimmed",
                        lh=1.5,
                    ),
                    style={"padding": "16px 24px"},
                ),
            ]
        )
    )

  return dmc.Paper(
      html.Div(
          dmc.Table(
              children=[
                  html.Thead(
                      html.Tr(
                          [
                              html.Th(
                                  "STATUS",
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
                                  "CATEGORY",
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
                                  "TYPE",
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
                                  "VALUE",
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
                                  "REASONING",
                                  style={
                                      "fontSize": "11px",
                                      "fontWeight": 600,
                                      "color": "var(--mantine-color-gray-5)",
                                      "letterSpacing": "0.05em",
                                      "padding": "16px 24px",
                                      "textAlign": "left",
                                  },
                              ),
                          ],
                          style={
                              "backgroundColor": "var(--mantine-color-gray-0)",
                              "borderBottom": (
                                  "1px solid var(--mantine-color-gray-2)"
                              ),
                          },
                      )
                  ),
                  html.Tbody(rows),
              ],
              verticalSpacing=0,
              horizontalSpacing=0,
              withTableBorder=False,
              withColumnBorders=False,
              withRowBorders=True,
              style={"backgroundColor": "white"},
          ),
          style={"overflowX": "auto"},
      ),
      withBorder=True,
      radius="md",
      shadow="sm",
      style={
          "overflow": "hidden",
      },
  )
