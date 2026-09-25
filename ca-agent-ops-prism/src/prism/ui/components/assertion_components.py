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
from prism.common.schemas.assertion import MatchMode
from prism.common.schemas.execution import Trial
from prism.ui.constants import ASSERTS_GUIDE, CHART_TYPE_OPTIONS
from prism.ui.ids import ComparisonIds
from prism.ui.ids import TestSuiteIds as Ids
from prism.ui.models.ui_state import AssertionMetric
from prism.ui.models.ui_state import AssertionSummary
from prism.ui.utils import clean_empty
import yaml


def _render_guide_card():
  """Renders the dynamic guide card."""
  # A server-side callback fills this in from the selected assertion type.
  return dmc.Paper(
      id=Ids.ASSERT_GUIDE_CONTAINER,
      radius="md",
      p="md",
      withBorder=True,
      style={
          "backgroundColor": "#eff6ff",
          "borderColor": "#dbeafe",
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
                          dmc.Stack(
                              gap=4,
                              children=[
                                  dmc.Text(
                                      id=Ids.ASSERT_GUIDE_TITLE,
                                      fw=700,
                                      size="sm",
                                      c="#1e40af",
                                  ),
                                  dmc.Text(
                                      id=Ids.ASSERT_GUIDE_DESC,
                                      size="sm",
                                      c="#1e3a8a",
                                      lh=1.5,
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          )
      ],
  )


def _render_code_editor():
  """Renders the code-editor style inputs."""
  return dmc.Stack(
      gap="xs",
      children=[
          dmc.Grid(
              gutter="md",
              children=[
                  dmc.GridCol(
                      span=8,
                      children=dmc.Stack(
                          gap=8,
                          children=[
                              dmc.Group(
                                  h=28,
                                  align="flex-end",
                                  justify="space-between",
                                  children=[
                                      dmc.Text(
                                          "Assertion Logic", fw=500, size="sm"
                                      ),
                                      # Only the two contains types read this,
                                      # so the type callback hides it for the
                                      # rest.
                                      dmc.SegmentedControl(
                                          id=Ids.TC_ASSERT_MODE,
                                          value=MatchMode.CONTAINS.value,
                                          data=[
                                              {
                                                  "label": "Text Match",
                                                  "value": (
                                                      MatchMode.CONTAINS.value
                                                  ),
                                              },
                                              {
                                                  "label": "Regex Match",
                                                  "value": (
                                                      MatchMode.REGEX.value
                                                  ),
                                              },
                                          ],
                                          size="xs",
                                          style={"display": "none"},
                                      ),
                                  ],
                              ),
                              dmc.Box(
                                  style={"position": "relative"},
                                  children=[
                                      # Multi-line. The values that go in here
                                      # are SQL fragments and prose, and a
                                      # single-line input showed a sliding
                                      # window of whichever one you were
                                      # editing. It rested at one row, which
                                      # read as a single-line field and hid
                                      # that it takes more. update_assertion_ui
                                      # drops it back to one row for the types
                                      # that take a number.
                                      dmc.Textarea(
                                          id=Ids.TC_ASSERT_VALUE,
                                          placeholder="Enter value...",
                                          minRows=4,
                                          maxRows=8,
                                          autosize=True,
                                          style={"display": "none"},
                                          styles={
                                              "input": {
                                                  "fontFamily": "monospace",
                                              }
                                          },
                                          className="font-mono",
                                      ),
                                      dmc.Textarea(
                                          id=Ids.TC_ASSERT_YAML,
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
                                      dmc.Select(
                                          id=Ids.ASSERT_CHART_TYPE,
                                          data=CHART_TYPE_OPTIONS,
                                          placeholder="Select chart type...",
                                          style={"display": "none"},
                                          searchable=True,
                                          allowDeselect=False,
                                      ),
                                  ],
                              ),
                          ],
                      ),
                  ),
                  dmc.GridCol(
                      span=4,
                      children=[
                          dmc.Stack(
                              id=Ids.ASSERT_EXAMPLE_CONTAINER,
                              gap=8,
                              children=[
                                  dmc.Group(
                                      h=28,
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
                                          # Matches the field it is an example
                                          # for. A long example was clipped
                                          # here while the box beside it wrapped
                                          # the same text.
                                          dmc.Textarea(
                                              id=Ids.ASSERT_EXAMPLE_VALUE,
                                              readOnly=True,
                                              disabled=True,
                                              minRows=4,
                                              maxRows=8,
                                              autosize=True,
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
                                              id=Ids.ASSERT_EXAMPLE_YAML,
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


def _render_accuracy_toggle():
  """Renders the card-style accuracy toggle."""
  return dmc.Paper(
      radius="md",
      p="md",
      bg="gray.0",
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
                      id=Ids.TC_ASSERT_WEIGHT,
                      size="md",
                      color="blue",
                      checked=True,
                  ),
              ],
          ),
      ],
  )


def render_assertion_form_content():
  """Renders the body of the assertion modal."""
  return dmc.Stack(
      gap="lg",
      children=[
          dmc.Stack(
              gap="xs",
              children=[
                  dmc.Text("Assertion Type", fw=500, size="sm"),
                  dmc.Select(
                      id=Ids.TC_ASSERT_TYPE,
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
          _render_guide_card(),
          _render_code_editor(),
          _render_accuracy_toggle(),
          dmc.Alert(
              id=Ids.ASSERT_VAL_MSG,
              color="red",
              variant="light",
              title="Validation Error",
              style={"display": "none"},
              icon=DashIconify(icon="material-symbols:error-outline"),
          ),
      ],
  )


def is_accuracy_assertion(weight: Any) -> bool:
  """Whether an assertion counts toward the score.

  Weight is the only thing that decides it. Anything at zero is diagnostic:
  it runs and reports, but the run's accuracy ignores it.
  """
  try:
    return float(weight or 0) > 0
  except (TypeError, ValueError):
    return False


def assertion_status_color(passed: bool, is_accuracy: bool) -> str:
  """The color for one assertion result.

  A diagnostic failure is not a failed run, so it does not get the red an
  accuracy failure gets.
  """
  if passed:
    return "teal" if is_accuracy else "gray"
  return "red" if is_accuracy else "orange"


def render_assertion_status_badge(
    passed: bool,
    is_accuracy: bool,
    size: str = "xs",
    with_icon: bool = False,
    **kwargs,
) -> dmc.Badge:
  """Renders the PASS/FAIL badge for one assertion result.

  Color carries the outcome, variant carries the category. Filled means the
  result moved the score, outline means it did not. Color alone was not enough:
  a list of results made a diagnostic failure look like a broken agent.
  """
  label = "PASS" if passed else "FAIL"
  if with_icon:
    label = [
        DashIconify(
            icon="mi:check" if passed else "mi:close",
            width=14,
            style={"marginRight": "4px"},
        ),
        label,
    ]
    kwargs.setdefault(
        "styles",
        {
            "label": {
                "display": "flex",
                "alignItems": "center",
                "fontWeight": 700,
            }
        },
    )
  return dmc.Badge(
      label,
      color=assertion_status_color(passed, is_accuracy),
      variant="filled" if is_accuracy else "outline",
      size=size,
      radius="xs",
      fw=700,
      **kwargs,
  )


def render_assertion_category_badge(is_accuracy: bool, **kwargs) -> dmc.Badge:
  """Renders the Accuracy/Diagnostic badge for one assertion.

  Same green/gray as the suggestion cards on the suite questions page, so the
  category looks the same wherever it is shown.
  """
  return dmc.Badge(
      "Accuracy" if is_accuracy else "Diagnostic",
      color="green" if is_accuracy else "gray",
      variant="light",
      size="xs",
      **kwargs,
  )


# What the category badge means. Shown on hover wherever the badge appears.
ASSERTION_CATEGORY_HELP = (
    "Accuracy assertions contribute to the overall score. Diagnostic"
    " assertions (Accuracy OFF) are used for monitoring without affecting the"
    " score."
)


def get_assertion_style(a_type: str) -> dict[str, Any]:
  """Returns the icon, colours and labels used to render an assertion type."""
  style = {
      "icon": "material-symbols:help-outline",
      "color": "gray",
      "bg": "gray",
      # Title case, like every other label here. It is rendered as display
      # text, and was the one lowercase label in the map.
      "label": "Assertion",
      "badge": "CHECK",
      "desc": "Validates the response.",
  }

  if a_type == "text-contains":
    style.update({
        "icon": "material-symbols:text-fields",
        "color": "blue",
        "bg": "blue",
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
        "desc": (
            "Checks if the generated Looker query matches the specified"
            " structure. The match rate is the fraction of the parameters you"
            " specified that matched. It passes at >= 0.75 and scores 1.0 or"
            " 0.0."
        ),
    })
  elif a_type == "data-check-row":
    style.update({
        "icon": "material-symbols:table-rows",
        "color": "teal",
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
  elif a_type == "query-contains":
    style.update({
        "icon": "material-symbols:manage-search",
        "color": "orange",
        "bg": "orange",
        "label": "Query Contains",
        "badge": "SQL",
        "desc": "Checks if the generated SQL contains specific keywords.",
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
        bg="#f8fafc",
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
    columns = assertion.get("columns", {})
    if not columns and "value" in assertion:
      # Older rows keep the columns as a JSON string in "value".
      try:
        columns = json.loads(assertion["value"])
      except (ValueError, TypeError):
        columns = {}

    if not columns:
      return None

    grid_children = []
    for k, v in columns.items():
      grid_children.append(
          dmc.Text(
              f"{k}:",
              c="dimmed",
              ta="right",
              ff="mono",
              size="sm",
              style={"wordBreak": "break-all", "maxWidth": "250px"},
          )
      )
      color = "teal" if isinstance(v, str) else "blue"
      if isinstance(v, (int, float)) or (
          isinstance(v, str) and (">" in v or "<" in v)
      ):
        color = "violet"

      grid_children.append(
          dmc.Text(
              str(v),
              fw=600,
              c=color,
              ff="mono",
              size="sm",
              style={"wordBreak": "break-all"},
          )
      )

    return dmc.Box(
        bg="gray.0",
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

  elif a_type == "text-contains":
    val = assertion.get("value", "")
    return dmc.Box(
        bg="#f8fafc",
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Code(
            f'"{val}"',
            c="dark",
            bg="transparent",
            style={"fontSize": "14px", "fontFamily": "monospace"},
        ),
    )

  elif a_type == "query-contains":
    val = assertion.get("value", "")
    return dmc.Box(
        bg="#f8fafc",
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
        bg="#f8fafc",
        p="md",
        style={"borderRadius": "8px", "border": "1px solid #f1f5f9"},
        children=dmc.Text(val, size="sm", c="dark"),
    )

  return None


def render_assertion_card(
    assertion: dict[str, Any],
    index: int,
    is_suggestion: bool = False,
    suggestion_actions: Any = None,
    result: dict[str, Any] | None = None,
    show_actions: bool = True,
):
  """Renders the detailed card for one assertion."""
  a_type = assertion.get("type", "unknown")
  is_accuracy = is_accuracy_assertion(assertion.get("weight", 0))

  style = get_assertion_style(a_type)
  content = _render_assertion_content(a_type, assertion)

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
                  id={"type": Ids.ASSERT_EDIT_BTN, "index": index},
                  variant="subtle",
                  color="gray",
                  size="lg",
                  className=(
                      "hover:bg-blue-50 hover:text-blue-600 transition-colors"
                  ),
              ),
          ],
      )

  result_footer = None
  result = result or assertion.get("result")
  if result:
    passed = result.get("passed", False)
    reason = result.get("reasoning", "No reason provided.")
    error = result.get("error_message")

    status_color = assertion_status_color(passed, is_accuracy)
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
    p_color = assertion_status_color(result.get("passed", False), is_accuracy)
    paper_style = {
        "borderColor": f"var(--mantine-color-{p_color}-4)",
        "borderWidth": "1.5px",
        "backgroundColor": "white",
    }

  content_box = None
  if content:
    content_box = dmc.Box(
        pl="4.5rem",  # Clears the status icon and its gap, so this lines up
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
          dmc.Group(
              justify="space-between",
              p="md",
              className="cursor-pointer hover:bg-slate-50/50 transition-colors",
              children=[
                  dmc.Group(
                      children=[
                          dmc.ThemeIcon(
                              DashIconify(icon=style["icon"], width=24),
                              size=40,
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
                  dmc.Group(
                      gap="md",
                      children=[
                          dmc.Tooltip(
                              label=ASSERTION_CATEGORY_HELP,
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
                                                  Ids.ASSERT_TOGGLE_ACCURACY
                                              ),
                                              "index": index,
                                          },
                                          size="sm",
                                          color="blue",
                                      ),
                                  ],
                              ),
                          ),
                          dmc.Divider(orientation="vertical", h=20),
                          action_buttons,
                      ],
                  ),
              ],
          ),
          content_box,
          footer_box,
      ],
  )


def render_suggested_assertion_card(
    suggestion: dict[str, Any],
    index: int,
    action_buttons: list[dmc.Button | dmc.ActionIcon] | None = None,
    ids_class: Any = Ids,
):
  """Renders a suggested assertion card (grape theme)."""
  a_type = suggestion.get("type", "unknown")
  style = get_assertion_style(a_type)
  content = _render_assertion_content(a_type, suggestion)

  content_box = None
  if content:
    content_box = dmc.Box(
        children=content,
        className="bg-white/80 rounded-lg border border-slate-200 shadow-sm",
    )

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
                  dmc.ThemeIcon(
                      DashIconify(icon=style["icon"], width=20),
                      size=32,
                      radius="md",
                      color=style["color"],
                      variant="light",
                      className="border border-white/50 shadow-sm",
                  ),
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
                          content_box,
                          actions_row,
                      ],
                  ),
              ],
          )
      ],
  )


def render_suggestion_skeleton():
  """Renders the placeholder cards shown while suggestions load."""
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


def render_empty_suggestions(button_id: str | dict[str, Any] | None = None):
  """Renders the empty state for assertion suggestions."""
  children = [
      dmc.ThemeIcon(
          DashIconify(icon="bi:stars", width=24),
          size=50,
          radius="md",
          variant="light",
          color="grape",
      ),
      dmc.Text("No suggested assertions.", fw=700, size="lg"),
      dmc.Text(
          "There are currently no suggested assertions for this trial"
          " execution.",
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
  """Renders the empty state for assertions."""
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
  """Renders a summary of assertion results as a row of metric cards."""

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
                        # Sits on the same baseline as the big percentage.
                        mb=4,
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
  if hasattr(ar, "model_dump"):
    ar = ar.model_dump()
  assertion = ar.get("assertion", {})

  # original_assertion_id is the ID in the live assertions table, so it is
  # stable across runs.
  if assertion.get("original_assertion_id"):
    return f"orig-{assertion['original_assertion_id']}"

  # Ad-hoc assertions and rows with no original ID fall back to content
  # matching. assertion.get('id') is usually the snapshot ID, which changes
  # every run, so it cannot align anything.
  a_type = assertion.get("type", "unknown")
  a_val = str(assertion.get("value", ""))
  if not a_val and "params" in assertion:
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
          clean_empty(params), sort_keys=False, default_flow_style=False
      ).strip()
    return assertion.get("yaml_config") or ""

  if a_type == "data-check-row":
    columns = assertion.get("columns", {})
    if columns:
      return yaml.dump(
          clean_empty(columns), sort_keys=False, default_flow_style=False
      ).strip()

  val = assertion.get("value", "")
  if isinstance(val, (dict, list)):
    return yaml.dump(
        clean_empty(val), sort_keys=False, default_flow_style=False
    ).strip()

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
                    dmc.Text(
                        f"{k}:",
                        c="pink.3",
                        ff="mono",
                        size="xs",
                        style={"wordBreak": "break-all", "maxWidth": "150px"},
                    ),
                    dmc.Text(
                        json.dumps(v),
                        c="yellow.2",
                        ff="mono",
                        size="xs",
                        style={"wordBreak": "break-all"},
                    ),
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

  # data-check-row and other non-scalar values get a YAML dump, in a code
  # block when it spans lines.
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
) -> dmc.Paper:
  """Renders a detailed table comparing assertion results between two trials."""
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

  # Sort keys: regressions first, then by the alignment key itself. That key
  # is normally "orig-<original_assertion_id>", so the secondary order is
  # lexicographic on the live-row id, not on the assertion type.
  def sort_key(k: str) -> tuple[int, str]:
    br = base_results.get(k)
    cr = chal_results.get(k)
    is_regression = br and br.passed and cr and not cr.passed
    return (0 if is_regression else 1, k)

  all_keys.sort(key=sort_key)

  rows = []
  for key in all_keys:
    base_ar = base_results.get(key)
    chal_ar = chal_results.get(key)

    ar = chal_ar or base_ar
    if not ar:
      continue
    assertion = ar.assertion
    style = get_assertion_style(assertion.type)

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
                        wrap="nowrap",
                        align="center",
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
                    style={
                        "padding": "16px 24px",
                        "whiteSpace": "nowrap",
                        "minWidth": "180px",
                    },
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
                    style={"padding": "16px 24px", "minWidth": "250px"},
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
                    style={
                        "padding": "16px 24px",
                        "whiteSpace": "nowrap",
                        "minWidth": "120px",
                    },
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
                    style={"padding": "16px 24px", "minWidth": "350px"},
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
                                # Only a regression gets colour. Every
                                # other reason stays dimmed.
                                c=(
                                    "#e03131"
                                    if status_label == "REGRESSED"
                                    else "dimmed"
                                ),
                                lh=1.5,
                            ),
                        ],
                    )
                    if chal_ar
                    else dmc.Text("N/A", size="xs", c="dimmed", lh=1.5),
                    style={"padding": "16px 24px", "minWidth": "350px"},
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
                                      "width": "1%",
                                      "whiteSpace": "nowrap",
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
                                      "minWidth": "250px",
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
                                      "width": "1%",
                                      "whiteSpace": "nowrap",
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
                                      "minWidth": "300px",
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
                                      "minWidth": "300px",
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
) -> dmc.Paper:
  """Renders a table of assertion results."""
  rows = []
  for item in assertion_details:
    a_type = item.get("type", "unknown")
    style = get_assertion_style(a_type)
    passed = item.get("passed", False)
    is_accuracy = is_accuracy_assertion(item.get("weight", 0))

    rows.append(
        html.Tr(
            children=[
                # Status
                html.Td(
                    render_assertion_status_badge(passed, is_accuracy),
                    style={
                        "padding": "16px 24px",
                        "minWidth": "120px",
                        "whiteSpace": "nowrap",
                    },
                ),
                # Category
                html.Td(
                    dmc.Tooltip(
                        label=ASSERTION_CATEGORY_HELP,
                        position="top",
                        withArrow=True,
                        children=render_assertion_category_badge(is_accuracy),
                    ),
                    style={
                        "padding": "16px 24px",
                        "minWidth": "150px",
                        "whiteSpace": "nowrap",
                    },
                ),
                # Type
                html.Td(
                    dmc.Group(
                        gap="sm",
                        wrap="nowrap",
                        align="center",
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
                    style={
                        "padding": "16px 24px",
                        "whiteSpace": "nowrap",
                        "minWidth": "180px",
                    },
                ),
                # Value
                html.Td(
                    _render_assertion_value_display(
                        a_type, item, is_table=True
                    ),
                    style={"padding": "16px 24px", "minWidth": "250px"},
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
                    style={"padding": "16px 24px", "minWidth": "350px"},
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
                                      "minWidth": "120px",
                                      "whiteSpace": "nowrap",
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
                                      "minWidth": "150px",
                                      "whiteSpace": "nowrap",
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
                                      "minWidth": "180px",
                                      "whiteSpace": "nowrap",
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
                                      "minWidth": "250px",
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
                                      "minWidth": "350px",
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
