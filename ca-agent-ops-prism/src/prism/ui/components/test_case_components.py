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

"""Presentational components for the Test Suites UI."""

from typing import Any
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.assertion_components import get_assertion_style
from prism.ui.ids import TestSuiteIds as Ids
from prism.ui.models import ui_state

# get_assertion_style lived here too, as a copy that had drifted. It was
# missing the desc key on twelve of its fourteen branches, so anything that
# read a description off it got the generic one. The assertion_components copy
# is the one with the descriptions and the one six other call sites use.


def render_assertion_badges(asserts: list[Any]):
  """Renders a list of badges for each assertion type."""
  num_asserts = len(asserts)
  badges = []

  if num_asserts > 0:
    type_counts = {}
    for a in asserts:
      if isinstance(a, dict):
        a_type = a.get("type", "unknown")
      else:
        a_type = getattr(a, "type", "unknown")
      type_counts[a_type] = type_counts.get(a_type, 0) + 1

    for a_type, count in sorted(type_counts.items()):
      style = get_assertion_style(a_type)
      # The label is a phrase, not a noun, so it does not take a plural. The
      # rule that used to run here turned two of them into "2 Text Containses".
      label = style["label"]

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


def render_test_case_card(
    test_case: ui_state.TestCaseState, index: int, read_only: bool = False
):
  """Renders a single test case card in the builder.

  There is no editable variant on screen. The card is rendered from two
  places, both of them the suite view page, and that page is the only one
  holding the list container the render callback writes into, so its
  ``read_only = "/view/" in pathname`` is always True. The pencil and trash
  this used to draw for the other case never reached a browser.
  """
  asserts = test_case.asserts or []
  badges = render_assertion_badges(asserts)

  return dmc.Card(
      p="lg",
      radius="md",
      withBorder=True,
      mb="md",
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
                              test_case.question,
                              fw=600,
                              size="md",
                              style={"lineHeight": "1.4"},
                          ),
                      ],
                  ),
              ],
          ),
          dmc.Group(
              gap="md",
              children=badges,
          ),
      ],
  )


def render_test_case_nav_item(
    test_case: ui_state.TestCaseState, index: int, active: bool = False
):
  """Renders a navigation link/button for the test case playground."""
  # Inactive look, overridden below when this is the item being edited.
  bg_color = "transparent"
  border_color = "transparent"
  icon_color = "#94a3b8"
  text_color = "dimmed"
  msg_icon = "material-symbols:chat-bubble-outline"

  if active:
    bg_color = "#eff6ff"
    border_color = "#bfdbfe"
    icon_color = "#2563eb"
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

  assert_count = len(test_case.asserts)
  count_label = f"{assert_count} Asserts" if assert_count != 1 else "1 Assert"
  coverage_badge = dmc.Badge(
      count_label,
      size="xs",
      variant="light",
      color="blue" if test_case.asserts else "orange",
      styles={
          "root": {
              "textTransform": "none",
              "padding": "0 4px",
              "height": "16px",
          }
      },
  )

  return dmc.UnstyledButton(
      id={"type": Ids.TC_LIST_ITEM, "index": index},
      w="100%",
      mb="xs",
      children=dmc.Paper(
          p="sm",
          radius="md",
          withBorder=True,
          style={
              "backgroundColor": bg_color,
              "borderColor": border_color,
              "transition": "all 0.2s ease",
          },
          className="group hover:bg-slate-50",
          children=dmc.Stack(
              gap="xs",
              children=[
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
                  dmc.Text(
                      test_case.question or "(Empty Test Case)",
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
