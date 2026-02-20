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

"""Page for the Test Case Playground (editing and triggering runs)."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.assertion_components import render_assertion_form_content
from prism.ui.components.cards import render_detail_card
from prism.ui.components.page_layout import render_page
from prism.ui.ids import TestSuiteIds as Ids


def render_bulk_add_guide():
  """Renders a collapsible guide for assertion types in bulk add."""
  from prism.ui.constants import ASSERTS_GUIDE

  items = []
  for guide in ASSERTS_GUIDE:
    # Build a nice example block
    example_content = str(guide["example"])
    is_multiline = "\n" in example_content

    if guide["name"] in [
        "looker-query-match",
        "data-check-row",
        "custom",
        "json_valid",
    ]:
      # These expect YAML blocks, their examples are already YAML-y or just the value
      if is_multiline:
        code_text = (
            f"- type: {guide['name']}\n "
            f" {example_content.replace('\n', '\n  ')}"
        )
      else:
        code_text = f"- type: {guide['name']}\n  value: {example_content}"
    else:
      # Simple types
      code_text = f"- type: {guide['name']}\n  value: {example_content}"

    items.append(
        dmc.AccordionItem(
            [
                dmc.AccordionControl(
                    dmc.Group(
                        [
                            dmc.Text(guide["label"], fw=500, size="sm"),
                            dmc.Code(guide["name"]),
                        ],
                        gap="xs",
                    )
                ),
                dmc.AccordionPanel(
                    dmc.Stack(
                        [
                            dmc.Text(
                                guide["description"], size="xs", c="dimmed"
                            ),
                            dmc.Text("YAML Example:", size="xs", fw=600, mt=4),
                            dmc.Code(
                                code_text,
                                block=True,
                            ),
                        ],
                        gap=4,
                    )
                ),
            ],
            value=guide["name"],
        )
    )

  return dmc.Stack(
      [
          dmc.Divider(label="Advanced Mode Reference", labelPosition="center"),
          dmc.Accordion(items, variant="separated", chevronPosition="left"),
      ],
      gap="xs",
      mt="md",
      id="bulk-add-guide-container",
  )


def render_bulk_add_modal():
  """Renders the bulk add modal."""
  return dmc.Modal(
      id=Ids.MODAL_BULK_ADD,
      title="Bulk Add Test Cases",
      size="90%",
      children=[
          dmc.Stack(
              children=[
                  dmc.Center(
                      dmc.SegmentedControl(
                          id=Ids.TC_BULK_MODE,
                          data=[
                              {
                                  "label": "Simple (Questions Only)",
                                  "value": "simple",
                              },
                              {
                                  "label": "Advanced (Structured YAML)",
                                  "value": "advanced",
                              },
                          ],
                          value="advanced",
                          fullWidth=True,
                      )
                  ),
                  dmc.Grid(
                      gutter="md",
                      children=[
                          dmc.GridCol(
                              span=6,
                              children=[
                                  dmc.Stack(
                                      gap="xs",
                                      children=[
                                          dmc.Group(
                                              justify="space-between",
                                              children=[
                                                  dmc.Text(
                                                      "Input",
                                                      id="bulk-add-input-title",
                                                      fw=600,
                                                      size="sm",
                                                  ),
                                                  dmc.Button(
                                                      "Fix with AI",
                                                      id=Ids.BTN_BULK_FIX_AI,
                                                      variant="subtle",
                                                      size="xs",
                                                      leftSection=DashIconify(
                                                          icon="bi:stars"
                                                      ),
                                                      color="grape",
                                                  ),
                                              ],
                                          ),
                                          dmc.Textarea(
                                              id=Ids.INPUT_BULK_TEXT,
                                              placeholder="Enter your input...",
                                              minRows=15,
                                              maxRows=25,
                                              autosize=True,
                                              styles={
                                                  "input": {
                                                      "fontFamily": "monospace",
                                                      "fontSize": "13px",
                                                  }
                                              },
                                          ),
                                          html.Div(
                                              id="bulk-add-guide-wrapper",
                                              children=render_bulk_add_guide(),
                                          ),
                                      ],
                                  )
                              ],
                          ),
                          dmc.GridCol(
                              span=6,
                              children=[
                                  dmc.Stack(
                                      gap="xs",
                                      children=[
                                          dmc.Text(
                                              "Live Preview", fw=600, size="sm"
                                          ),
                                          dmc.ScrollArea(
                                              id=Ids.PREVIEW_BULK_ADD,
                                              h=400,
                                              type="always",
                                              offsetScrollbars=True,
                                              style={
                                                  "border": "1px solid #dee2e6",
                                                  "borderRadius": "4px",
                                                  "padding": "0.5rem",
                                                  "backgroundColor": "#f8f9fa",
                                              },
                                              children=dmc.Text(
                                                  "No valid test cases found.",
                                                  c="dimmed",
                                                  size="sm",
                                                  mt="md",
                                                  ta="center",
                                              ),
                                          ),
                                      ],
                                  )
                              ],
                          ),
                      ],
                  ),
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Text(
                              id=Ids.VAL_MSG + "-bulk-count", fw=500, size="sm"
                          ),
                          dmc.Group(
                              children=[
                                  dmc.Button(
                                      "Cancel",
                                      id=Ids.BTN_BULK_ADD_CANCEL,
                                      variant="default",
                                  ),
                                  dmc.Button(
                                      "Import Test Cases",
                                      id=Ids.BTN_BULK_ADD_CONFIRM,
                                      disabled=True,
                                  ),
                              ]
                          ),
                      ],
                  ),
              ]
          )
      ],
  )


def layout(suite_id: str | None = None, **_):
  """Renders the Test Case Playground layout."""
  return render_page(
      title="Edit Test Cases",
      description="Interactively edit test cases and run ad-hoc simulations.",
      fluid=True,
      breadcrumbs=dmc.Breadcrumbs(
          separator="/",
          children=[
              dmc.Anchor(
                  "Test Suites",
                  href="/test_suites",
                  size="sm",
                  fw=500,
              ),
              dmc.Anchor(
                  id=Ids.TC_BREADCRUMB_SUITE_NAME,
                  href="#",
                  size="sm",
                  fw=500,
              ),
              dmc.Text("Edit Test Cases", size="sm", fw=500, c="dimmed"),
          ],
      ),
      children=[
          dmc.Flex(
              h="calc(100vh - 280px)",
              style={"height": "calc(100vh - 280px)", "overflow": "hidden"},
              children=[
                  # Sidebar: Test Case List
                  dmc.Box(
                      w=400,
                      p="md",
                      pl=0,
                      style={
                          "display": "flex",
                          "flexDirection": "column",
                          "boxSizing": "border-box",
                      },
                      children=[
                          dmc.Paper(
                              shadow="sm",
                              radius="md",
                              withBorder=True,
                              style={
                                  "display": "flex",
                                  "flexDirection": "column",
                                  "flex": 1,
                                  "minHeight": 0,
                                  "overflow": "hidden",
                                  "backgroundColor": "white",
                              },
                              children=[
                                  # Summary
                                  dmc.Group(
                                      justify="space-between",
                                      px="lg",
                                      pt="lg",
                                      pb="sm",
                                      children=[
                                          dmc.Text(
                                              "TEST CASES",
                                              size="xs",
                                              fw=700,
                                              c="dimmed",
                                              tt="uppercase",
                                              style={"letterSpacing": "0.05em"},
                                          ),
                                      ],
                                  ),
                                  # Test Case List (Scrollable)
                                  dmc.Box(
                                      style={
                                          "flex": 1,
                                          "minHeight": 0,
                                          "overflowY": "auto",
                                          "position": "relative",
                                      },
                                      children=[
                                          dmc.Stack(
                                              id=Ids.TC_LIST,
                                              gap="xs",
                                              p="md",
                                              children=[dmc.Loader(size="sm")],
                                          ),
                                      ],
                                  ),
                                  # Sidebar Footer
                                  dmc.Box(
                                      p="md",
                                      style={
                                          "borderTop": "1px solid #e2e8f0",
                                          "backgroundColor": "#f8fafc",
                                      },
                                      children=[
                                          dmc.Group(
                                              grow=True,
                                              children=[
                                                  dmc.Button(
                                                      "New Test Case",
                                                      id=Ids.TC_PLAYGROUND_ADD_BTN,
                                                      leftSection=DashIconify(
                                                          icon="bi:plus-lg"
                                                      ),
                                                      variant="outline",
                                                      color="gray",
                                                      c="dark",
                                                      radius="md",
                                                  ),
                                                  dmc.Button(
                                                      "Bulk Add",
                                                      id=Ids.TC_BULK_ADD_BTN,
                                                      leftSection=DashIconify(
                                                          icon="bi:list-ul"
                                                      ),
                                                      variant="outline",
                                                      color="gray",
                                                      c="dark",
                                                      radius="md",
                                                  ),
                                              ],
                                          )
                                      ],
                                  ),
                              ],
                          )
                      ],
                  ),
                  # Main: Editor & Playground
                  dmc.Box(
                      style={
                          "flex": 1,
                          "minHeight": 0,
                          "display": "flex",
                          "flexDirection": "column",
                          "overflow": "hidden",
                      },
                      children=[
                          # Empty State
                          dmc.Center(
                              id=Ids.TC_EDITOR_EMPTY,
                              style={
                                  "height": "100%",
                                  "width": "100%",
                                  "display": "none",
                              },
                              children=dmc.Stack(
                                  align="center",
                                  children=[
                                      DashIconify(
                                          icon="bi:arrow-left-circle",
                                          width=48,
                                          color="#cbd5e1",
                                      ),
                                      dmc.Text(
                                          "Select a test case to edit",
                                          c="dimmed",
                                          size="lg",
                                      ),
                                  ],
                              ),
                          ),
                          # Editor Container
                          dmc.Box(
                              id=Ids.TC_EDITOR_CONTAINER,
                              style={
                                  "height": "100%",
                                  "display": "flex",
                                  "flexDirection": "column",
                                  "overflow": "hidden",
                                  "boxSizing": "border-box",
                              },
                              children=[
                                  # Scrollable Body
                                  dmc.Box(
                                      pt="md",
                                      px="xl",
                                      pb="xl",
                                      style={
                                          "flex": 1,
                                          "minHeight": 0,
                                          "overflowY": "auto",
                                      },
                                      children=[
                                          dmc.Container(
                                              fluid=True,
                                              p=0,
                                              children=[
                                                  # Test Case Text
                                                  render_detail_card(
                                                      title="Test Case",
                                                      description=(
                                                          "Prompt sent to"
                                                          " GDA Agent"
                                                      ),
                                                      mb="3rem",
                                                      action=dmc.Button(
                                                          "Delete Test Case",
                                                          id={
                                                              "type": (
                                                                  Ids.TC_REMOVE_TEST_CASE_BTN
                                                              ),
                                                              "index": (
                                                                  "current"
                                                              ),
                                                          },
                                                          leftSection=DashIconify(
                                                              icon="bi:trash"
                                                          ),
                                                          color="red",
                                                          variant="subtle",
                                                          fw=600,
                                                          size="xs",
                                                      ),
                                                      children=[
                                                          dmc.Box(
                                                              style={
                                                                  "position": (
                                                                      "relative"
                                                                  )
                                                              },
                                                              children=[
                                                                  dmc.Textarea(
                                                                      id=Ids.TC_INPUT_TEST_CASE,
                                                                      placeholder=(
                                                                          "E.g., Did"
                                                                          " the agent"
                                                                          " verify the"
                                                                          " user's"
                                                                          " identity?"
                                                                      ),
                                                                      autosize=True,
                                                                      minRows=3,
                                                                      styles={
                                                                          "input": {
                                                                              "paddingBottom": (
                                                                                  "2rem"
                                                                              ),
                                                                              "fontSize": (
                                                                                  "1rem"
                                                                              ),
                                                                              "lineHeight": (
                                                                                  "1.5"
                                                                              ),
                                                                          }
                                                                      },
                                                                  ),
                                                                  dmc.Text(
                                                                      "19 chars",
                                                                      id=Ids.VAL_MSG
                                                                      + "-char-count",
                                                                      size="xs",
                                                                      c="dimmed",
                                                                      style={
                                                                          "position": (
                                                                              "absolute"
                                                                          ),
                                                                          "bottom": (
                                                                              8
                                                                          ),
                                                                          "right": (
                                                                              12
                                                                          ),
                                                                          "backgroundColor": (
                                                                              "rgba(255,255,255,0.8)"
                                                                          ),
                                                                          "padding": (
                                                                              "2px 6px"
                                                                          ),
                                                                          "borderRadius": (
                                                                              "4px"
                                                                          ),
                                                                      },
                                                                  ),
                                                              ],
                                                          ),
                                                          dmc.Group(
                                                              id=Ids.TC_CHANGE_ACTIONS_GROUP,
                                                              justify=(
                                                                  "flex-end"
                                                              ),
                                                              gap="xs",
                                                              mt="xs",
                                                              style={
                                                                  "display": (
                                                                      "none"
                                                                  )
                                                              },
                                                              children=[
                                                                  dmc.Button(
                                                                      "Revert",
                                                                      id=Ids.TC_REVERT_BTN,
                                                                      leftSection=DashIconify(
                                                                          icon="bi:arrow-counterclockwise"
                                                                      ),
                                                                      variant="outline",
                                                                      color=(
                                                                          "gray"
                                                                      ),
                                                                      size="sm",
                                                                      radius=(
                                                                          "md"
                                                                      ),
                                                                  ),
                                                                  dmc.Button(
                                                                      "Save Change",
                                                                      id=Ids.TC_SAVE_BTN,
                                                                      leftSection=DashIconify(
                                                                          icon="bi:check-lg"
                                                                      ),
                                                                      color="indigo",
                                                                      size="sm",
                                                                      radius=(
                                                                          "md"
                                                                      ),
                                                                  ),
                                                              ],
                                                          ),
                                                      ],
                                                  ),
                                                  # Assertions Header
                                                  dmc.Group(
                                                      justify="space-between",
                                                      mb="md",
                                                      align="flex-end",
                                                      children=[
                                                          dmc.Stack(
                                                              gap=0,
                                                              children=[
                                                                  dmc.Group(
                                                                      gap="xs",
                                                                      children=[
                                                                          dmc.Text(
                                                                              "Assertions",
                                                                              fw=600,
                                                                              size="lg",
                                                                          ),
                                                                          dmc.Badge(
                                                                              "0",
                                                                              id=Ids.TC_ASSERT_COUNT,
                                                                              color="gray",
                                                                              variant="light",
                                                                              radius="sm",
                                                                          ),
                                                                      ],
                                                                  ),
                                                                  dmc.Text(
                                                                      "Define"
                                                                      " logic"
                                                                      " to automatically"
                                                                      " validate"
                                                                      " this"
                                                                      " test"
                                                                      " case.",
                                                                      size="sm",
                                                                      c="dimmed",
                                                                  ),
                                                                  dmc.Text(
                                                                      "Changes"
                                                                      " to assertions"
                                                                      " are automatically"
                                                                      " saved",
                                                                      size="xs",
                                                                      c="blue.6",
                                                                      fw=500,
                                                                      style={
                                                                          "fontStyle": (
                                                                              "italic"
                                                                          )
                                                                      },
                                                                  ),
                                                              ],
                                                          ),
                                                      ],
                                                  ),
                                                  # Simulation Controls
                                                  dmc.Paper(
                                                      radius="md",
                                                      withBorder=True,
                                                      mb="lg",
                                                      p="sm",
                                                      bg="gray.0",
                                                      children=[
                                                          dmc.Group(
                                                              justify="space-between",
                                                              children=[
                                                                  dmc.Group(
                                                                      gap="xs",
                                                                      children=[
                                                                          dmc.Stack(
                                                                              gap=0,
                                                                              children=[
                                                                                  dmc.Text(
                                                                                      "ADHOC TEST CASE RUN CONTEXT",
                                                                                      fw=800,
                                                                                      size="11px",
                                                                                      c="indigo.9",
                                                                                      tt="uppercase",
                                                                                      lts="0.05em",
                                                                                  ),
                                                                                  dmc.Select(
                                                                                      id=Ids.TC_AGENT_SELECT,
                                                                                      placeholder=(
                                                                                          "Select Agent"
                                                                                      ),
                                                                                      data=[],
                                                                                      searchable=True,
                                                                                      size="sm",
                                                                                      w=250,
                                                                                      allowDeselect=False,
                                                                                      styles={
                                                                                          "input": {
                                                                                              "backgroundColor": (
                                                                                                  "white"
                                                                                              )
                                                                                          }
                                                                                      },
                                                                                      mt="xs",
                                                                                  ),
                                                                              ],
                                                                          ),
                                                                      ],
                                                                  ),
                                                                  dmc.Group(
                                                                      gap="md",
                                                                      align="center",
                                                                      children=[
                                                                          dmc.Button(
                                                                              "Run Test"
                                                                              " Case",
                                                                              id=Ids.TC_RUN_BTN,
                                                                              leftSection=DashIconify(
                                                                                  icon="material-symbols:refresh",
                                                                                  width=20,
                                                                              ),
                                                                              size="md",
                                                                              color="indigo",
                                                                          ),
                                                                      ],
                                                                  ),
                                                              ],
                                                          ),
                                                          # Dynamic Context / Stats
                                                          html.Div(
                                                              id=Ids.SIM_CONTEXT_CONTAINER
                                                          ),
                                                          # Store to trigger processing after skeleton load
                                                          dash.dcc.Store(
                                                              id=Ids.STORE_START_RUN
                                                          ),
                                                      ],
                                                  ),
                                                  # Suggestions Accordion
                                                  dmc.Accordion(
                                                      id=Ids.SUG_ACCORDION,
                                                      mb="lg",
                                                      variant="contained",
                                                      radius="md",
                                                      style={"display": "none"},
                                                      styles={
                                                          "control": {
                                                              "padding": (
                                                                  "8px 16px"
                                                              ),
                                                              "&:hover": {
                                                                  "backgroundColor": (
                                                                      "var(--mantine-color-grape-0)"
                                                                  )
                                                              },
                                                          },
                                                          "item": {
                                                              "border": (
                                                                  "1px solid"
                                                                  " var(--mantine-color-grape-2)"
                                                              ),
                                                              "backgroundColor": (
                                                                  "var(--mantine-color-grape-0)"
                                                              ),
                                                          },
                                                      },
                                                      children=[
                                                          dmc.AccordionItem(
                                                              value=(
                                                                  "suggestions"
                                                              ),
                                                              children=[
                                                                  dmc.AccordionControl(
                                                                      children=dmc.Group(
                                                                          id=Ids.SUG_ACCORDION_HEADER,
                                                                          gap="xs",
                                                                          children=[
                                                                              DashIconify(
                                                                                  icon="bi:lightbulb",
                                                                                  width=20,
                                                                                  color="var(--mantine-color-grape-6)",
                                                                              ),
                                                                              dmc.Text(
                                                                                  "Suggested Assertions",
                                                                                  fw=700,
                                                                                  size="lg",
                                                                              ),
                                                                          ],
                                                                      )
                                                                  ),
                                                                  dmc.AccordionPanel(
                                                                      p="md",
                                                                      children=dmc.Stack(
                                                                          id=Ids.SUG_LIST,
                                                                          gap="sm",
                                                                      ),
                                                                      bg="white",
                                                                  ),
                                                              ],
                                                          )
                                                      ],
                                                  ),
                                                  dmc.Stack(
                                                      id=Ids.TC_ASSERT_LIST,
                                                      gap="md",
                                                      mb="xl",
                                                      children=[],
                                                  ),
                                                  # Add Assertion Placeholder
                                                  html.Div(
                                                      id=Ids.ASSERT_MODAL_OPEN_BTN,
                                                      children=dmc.Paper(
                                                          p="lg",
                                                          radius="md",
                                                          withBorder=True,
                                                          style={
                                                              "borderStyle": (
                                                                  "dashed"
                                                              ),
                                                              "cursor": (
                                                                  "pointer"
                                                              ),
                                                              "backgroundColor": (
                                                                  "#f8fafc"
                                                              ),
                                                          },
                                                          className=(
                                                              "hover:bg-gray-100"
                                                              " transition-colors"
                                                          ),
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
                                                                              "Add New"
                                                                              " Assertion",
                                                                              fw=500,
                                                                              c="dimmed",
                                                                          ),
                                                                      ]
                                                                  )
                                                              )
                                                          ],
                                                      ),
                                                  ),
                                                  # Simulation Area
                                                  dash.html.Div(
                                                      id=Ids.TC_RESULT_CONTAINER
                                                  ),
                                              ],
                                          )
                                      ],
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          ),
          # Hidden Stores
          dash.dcc.Store(
              id=Ids.STORE_BUILDER, data=[]
          ),  # Local state of questions
          dash.dcc.Store(id=Ids.STORE_SELECTED_INDEX, data=None),
          dash.dcc.Store(id=Ids.STORE_PLAYGROUND_RESULT, data=None),
          dash.dcc.Store(id=Ids.STORE_DELETE_TEST_CASE_INDEX, data=None),
          dash.dcc.Store(id=Ids.STORE_DELETE_ASSERTION_INDEX, data=None),
          # Delete Modal
          dmc.Modal(
              id=Ids.MODAL_DELETE,
              zIndex=10000,
              children=[
                  dmc.Text(
                      "Are you sure you want to delete this test case?",
                      id=Ids.MODAL_DELETE_BODY,
                  ),
                  dmc.Group(
                      justify="flex-end",
                      mt="md",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=Ids.MODAL_DELETE_CANCEL_BTN,
                              variant="default",
                              size="sm",
                              radius="md",
                          ),
                          dmc.Button(
                              "Delete",
                              id=Ids.MODAL_CONFIRM_REMOVE_BTN,
                              color="red",
                              size="sm",
                              radius="md",
                          ),
                      ],
                  ),
              ],
              title="Confirm Deletion",
              radius="md",
          ),
          render_bulk_add_modal(),
          # Validation Msg (Hidden)
          dash.html.Div(id=Ids.VAL_MSG, style={"display": "none"}),
          # Stores for Suggestions
          dash.dcc.Store(id=Ids.STORE_SUGGESTIONS, data=[]),
          dash.dcc.Store(id=Ids.STORE_SUG_EDIT_CONTEXT, data=None),
          # Suggestion Modal
          dmc.Modal(
              id=Ids.SUGGESTION_MODAL,
              size="lg",
              radius="md",
              children=[
                  dmc.Stack([
                      dash.dcc.Loading(
                          dmc.Stack(id=Ids.SUGGESTION_LIST),
                          id=Ids.TC_SUGGEST_LOADING,
                      ),
                      dmc.Group(
                          justify="flex-end",
                          mt="md",
                          children=[
                              dmc.Button(
                                  "Add Selected",
                                  id=Ids.SUGGESTION_ADD_BTN,
                                  disabled=True,
                                  radius="md",
                              )
                          ],
                      ),
                  ])
              ],
              title="Suggestions from Recent Runs",
          ),
          # Suggestion Edit Modal
          dmc.Modal(
              id=Ids.SUG_EDIT_MODAL,
              size="80%",
              radius="md",
              title="Edit Suggestion",
              children=[
                  # Scrollable Content
                  dmc.Box(
                      p="lg",
                      style={"maxHeight": "70vh", "overflowY": "auto"},
                      children=render_assertion_form_content(
                          ids_class=type(
                              "SuggestionEditIds",
                              (),
                              {
                                  "ASSERT_TYPE": Ids.SUG_EDIT_TYPE,
                                  "ASSERT_WEIGHT": Ids.SUG_EDIT_WEIGHT,
                                  "ASSERT_VALUE": Ids.SUG_EDIT_VALUE,
                                  "ASSERT_YAML": Ids.SUG_EDIT_YAML,
                                  "ASSERT_CHART_TYPE": Ids.SUG_EDIT_CHART_TYPE,
                                  "ASSERT_GUIDE_CONTAINER": (
                                      Ids.SUG_EDIT_GUIDE_CONTAINER
                                  ),
                                  "ASSERT_GUIDE_TITLE": (
                                      Ids.SUG_EDIT_GUIDE_TITLE
                                  ),
                                  "ASSERT_GUIDE_DESC": Ids.SUG_EDIT_GUIDE_DESC,
                                  "ASSERT_EXAMPLE_CONTAINER": (
                                      Ids.SUG_EDIT_EXAMPLE_CONTAINER
                                  ),
                                  "ASSERT_EXAMPLE_VALUE": (
                                      Ids.SUG_EDIT_EXAMPLE_VALUE
                                  ),
                                  "ASSERT_EXAMPLE_YAML": (
                                      Ids.SUG_EDIT_EXAMPLE_YAML
                                  ),
                                  "VAL_MSG": Ids.ASSERT_VAL_MSG,
                              },
                          ),
                          is_edit=True,
                          is_suggestion=True,
                      ),
                  ),
                  # Footer
                  dmc.Group(
                      justify="flex-end",
                      p="lg",
                      style={
                          "borderTop": "1px solid #f1f5f9",
                          "backgroundColor": "white",
                      },
                      children=[
                          dmc.Button(
                              "Save & Update Trial",
                              id=Ids.SUG_EDIT_SAVE_BTN,
                              color="indigo",
                              radius="md",
                          ),
                      ],
                  ),
              ],
          ),
          # Assertion Modal
          dmc.Modal(
              id=Ids.ASSERT_MODAL,
              size="80%",
              radius="md",
              title="Manage Assertion",
              children=[
                  # Custom Header
                  dmc.Group(
                      justify="space-between",
                      px="lg",
                      py="md",
                      style={"borderBottom": "1px solid #f1f5f9"},
                      children=[
                          dmc.Stack(
                              gap=2,
                              children=[
                                  dmc.Text(
                                      "Configure Assertion",
                                      id=Ids.ASSERT_MODAL_TITLE_TEXT,
                                      fw=700,
                                      size="lg",
                                      c="#111318",
                                  ),
                                  dmc.Text(
                                      "Define validation rules for agent"
                                      " response",
                                      size="sm",
                                      c="dimmed",
                                  ),
                              ],
                          ),
                          # Delete Button (replacing Close button)
                          dmc.Button(
                              "Delete",
                              id=Ids.ASSERT_MODAL_DELETE_BTN,
                              variant="subtle",
                              color="red",
                              size="sm",
                              leftSection=DashIconify(
                                  icon="material-symbols:delete-outline",
                                  width=18,
                              ),
                              style={"display": "none"},  # Hidden by default
                          ),
                      ],
                  ),
                  # Scrollable Content
                  dmc.Box(
                      p="lg",
                      style={"maxHeight": "70vh", "overflowY": "auto"},
                      children=render_assertion_form_content(
                          ids_class=type(
                              "AssertionModalIds",
                              (),
                              {
                                  "ASSERT_TYPE": Ids.TC_ASSERT_TYPE,
                                  "ASSERT_WEIGHT": Ids.TC_ASSERT_WEIGHT,
                                  "ASSERT_VALUE": Ids.TC_ASSERT_VALUE,
                                  "ASSERT_YAML": Ids.TC_ASSERT_YAML,
                                  "ASSERT_CHART_TYPE": Ids.ASSERT_CHART_TYPE,
                                  "ASSERT_GUIDE_CONTAINER": (
                                      Ids.ASSERT_GUIDE_CONTAINER
                                  ),
                                  "ASSERT_GUIDE_TITLE": Ids.ASSERT_GUIDE_TITLE,
                                  "ASSERT_GUIDE_DESC": Ids.ASSERT_GUIDE_DESC,
                                  "ASSERT_EXAMPLE_CONTAINER": (
                                      Ids.ASSERT_EXAMPLE_CONTAINER
                                  ),
                                  "ASSERT_EXAMPLE_VALUE": (
                                      Ids.ASSERT_EXAMPLE_VALUE
                                  ),
                                  "ASSERT_EXAMPLE_YAML": (
                                      Ids.ASSERT_EXAMPLE_YAML
                                  ),
                                  "VAL_MSG": Ids.ASSERT_VAL_MSG,
                              },
                          )
                      ),
                  ),
                  # Footer
                  dmc.Group(
                      justify="flex-end",
                      p="lg",
                      style={
                          "borderTop": "1px solid #f1f5f9",
                          "backgroundColor": "white",
                      },
                      children=[
                          dmc.Button(
                              "Cancel",
                              id="modal-cancel-btn-footer",  # internal use
                              variant="subtle",
                              color="gray",
                          ),
                          dmc.Button(
                              "Save Assertion",
                              id=Ids.ASSERT_MODAL_CONFIRM_BTN,
                              leftSection=DashIconify(
                                  icon="material-symbols:check"
                              ),
                              color="indigo",
                          ),
                      ],
                  ),
              ],
          ),
          dash.dcc.Store(id=Ids.STORE_ASSERT_EDIT_INDEX, data=None),
          # Hidden stubs for callbacks shared with Dataset View
          html.Button(id=Ids.MODAL_SAVE_BTN, style={"display": "none"}),
          html.Button(id=Ids.BULK_ADD_BTN, style={"display": "none"}),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/test_suites/edit/<suite_id>",
      title="Prism | Edit Test Cases",
      layout=layout,
  )
