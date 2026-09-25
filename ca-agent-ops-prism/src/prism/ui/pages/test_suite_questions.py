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
from prism.ui.components.assertion_components import (
    render_assertion_form_content,
)
from prism.ui.components.cards import render_detail_card
from prism.ui.components.page_layout import render_page
from prism.ui.constants import ASSERTS_GUIDE
from prism.ui.ids import TestSuiteIds as Ids


def render_bulk_add_guide():
  """Renders a collapsible guide for assertion types in bulk add."""

  items = []
  for guide in ASSERTS_GUIDE:
    example_content = str(guide["example"])

    # The branch used to key off a list of type names, but the two types that
    # carry a YAML block (looker-query-match, data-check-row) are the two with
    # a multiline example, and the other arm was byte-identical to this one.
    if "\n" in example_content:
      indented = example_content.replace("\n", "\n  ")
      code_text = f"- type: {guide['name']}\n  {indented}"
    else:
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
                                                      id=Ids.BULK_ADD_INPUT_TITLE,
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
                                              id=Ids.BULK_ADD_GUIDE_WRAPPER,
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


def _breadcrumbs():
  """Renders the breadcrumb trail back to the suite."""
  return dmc.Breadcrumbs(
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
  )


def _sidebar_footer():
  """Renders the add and bulk add buttons under the test case list."""
  return dmc.Box(
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
                      leftSection=DashIconify(icon="bi:plus-lg"),
                      variant="outline",
                      color="gray",
                      c="dark",
                      radius="md",
                  ),
                  dmc.Button(
                      "Bulk Add",
                      id=Ids.TC_BULK_ADD_BTN,
                      leftSection=DashIconify(icon="bi:list-ul"),
                      variant="outline",
                      color="gray",
                      c="dark",
                      radius="md",
                  ),
              ],
          )
      ],
  )


def _sidebar():
  """Renders the scrolling test case list down the left of the page."""
  return dmc.Box(
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
                  _sidebar_footer(),
              ],
          )
      ],
  )


def _editor_empty_state():
  """Renders the prompt shown until a test case is picked.

  Visible on first paint, because nothing has been picked yet.
  sync_editor_selection hides it once a selection arrives. The two defaults
  used to be the other way round, and on a suite with no test cases at all
  that callback never fires: load_playground_data writes selected_index=None,
  the value the store already holds, so the prop does not change. The page
  opened on an empty Test Case box, an assertion panel and a Save bar that
  save_test_case_text returns early out of.
  """
  return dmc.Center(
      id=Ids.TC_EDITOR_EMPTY,
      style={
          "height": "100%",
          "width": "100%",
          "display": "flex",
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
  )


def _change_actions_group():
  """Renders the revert and save bar for an edited prompt."""
  return dmc.Group(
      id=Ids.TC_CHANGE_ACTIONS_GROUP,
      justify="flex-end",
      gap="xs",
      mt="xs",
      style={"display": "none"},
      children=[
          dmc.Button(
              "Revert",
              id=Ids.TC_REVERT_BTN,
              leftSection=DashIconify(icon="bi:arrow-counterclockwise"),
              variant="outline",
              color="gray",
              size="sm",
              radius="md",
          ),
          dmc.Button(
              "Save Change",
              id=Ids.TC_SAVE_BTN,
              leftSection=DashIconify(icon="bi:check-lg"),
              color="indigo",
              size="sm",
              radius="md",
          ),
      ],
  )


def _test_case_card():
  """Renders the prompt editor card for the selected test case."""
  return render_detail_card(
      title="Test Case",
      description="Prompt sent to GDA Agent",
      mb="3rem",
      action=dmc.Button(
          "Delete Test Case",
          id={"type": Ids.TC_REMOVE_TEST_CASE_BTN, "index": "current"},
          leftSection=DashIconify(icon="bi:trash"),
          color="red",
          variant="subtle",
          fw=600,
          size="xs",
      ),
      children=[
          dmc.Box(
              style={"position": "relative"},
              children=[
                  dmc.Textarea(
                      id=Ids.TC_INPUT_TEST_CASE,
                      placeholder=(
                          "E.g., Did the agent verify the user's identity?"
                      ),
                      autosize=True,
                      minRows=3,
                      styles={
                          "input": {
                              "paddingBottom": "2rem",
                              "fontSize": "1rem",
                              "lineHeight": "1.5",
                          }
                      },
                  ),
                  dmc.Text(
                      "",
                      id=Ids.VAL_MSG + "-char-count",
                      size="xs",
                      c="dimmed",
                      style={
                          "position": "absolute",
                          "bottom": 8,
                          "right": 12,
                          "backgroundColor": "rgba(255,255,255,0.8)",
                          "padding": "2px 6px",
                          "borderRadius": "4px",
                      },
                  ),
              ],
          ),
          _change_actions_group(),
      ],
  )


def _assertions_header():
  """Renders the assertions heading, count and suggestions button."""
  return dmc.Group(
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
                          dmc.Text("Assertions", fw=600, size="lg"),
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
                      "Define logic to automatically validate this test case.",
                      size="sm",
                      c="dimmed",
                  ),
                  dmc.Text(
                      "Changes to assertions are automatically saved",
                      size="xs",
                      c="blue.6",
                      fw=500,
                      style={"fontStyle": "italic"},
                  ),
              ],
          ),
          dmc.Button(
              "Suggestions from recent runs",
              id=Ids.TC_HISTORY_SUGGESTIONS_BTN,
              variant="light",
              size="compact-sm",
              radius="md",
              leftSection=DashIconify(
                  icon="material-symbols:history",
                  width=16,
              ),
          ),
      ],
  )


def _run_context_picker():
  """Renders the agent picker that scopes an ad-hoc run."""
  return dmc.Group(
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
                      placeholder="Select Agent",
                      data=[],
                      searchable=True,
                      size="sm",
                      w=250,
                      allowDeselect=False,
                      styles={"input": {"backgroundColor": "white"}},
                      mt="xs",
                  ),
              ],
          ),
      ],
  )


def _simulation_controls():
  """Renders the bar that launches an ad-hoc run of the test case."""
  return dmc.Paper(
      radius="md",
      withBorder=True,
      mb="lg",
      p="sm",
      bg="gray.0",
      children=[
          dmc.Group(
              justify="space-between",
              children=[
                  _run_context_picker(),
                  dmc.Group(
                      gap="md",
                      align="center",
                      children=[
                          dmc.Button(
                              "Run Test Case",
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
          html.Div(id=Ids.SIM_CONTEXT_CONTAINER),
          # Store to trigger processing after skeleton load
          dash.dcc.Store(id=Ids.STORE_START_RUN),
      ],
  )


def _suggestions_accordion():
  """Renders the panel holding assertions suggested from past runs."""
  return dmc.Accordion(
      id=Ids.SUG_ACCORDION,
      mb="lg",
      variant="contained",
      radius="md",
      style={"display": "none"},
      styles={
          "control": {
              "padding": "8px 16px",
              "&:hover": {"backgroundColor": "var(--mantine-color-grape-0)"},
          },
          "item": {
              "border": "1px solid var(--mantine-color-grape-2)",
              "backgroundColor": "var(--mantine-color-grape-0)",
          },
      },
      children=[
          dmc.AccordionItem(
              value="suggestions",
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
  )


def _add_assertion_placeholder():
  """Renders the dashed card that opens the assertion modal."""
  return html.Div(
      id=Ids.ASSERT_MODAL_OPEN_BTN,
      children=dmc.Paper(
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
                              "Add New Assertion",
                              fw=500,
                              c="dimmed",
                          ),
                      ]
                  )
              )
          ],
      ),
  )


def _editor_container():
  """Renders the scrolling editor for the selected test case.

  Hidden on first paint. sync_editor_selection shows it, with this same style
  plus display flex, when a selection arrives. See _editor_empty_state.
  """
  return dmc.Box(
      id=Ids.TC_EDITOR_CONTAINER,
      style={
          "height": "100%",
          "display": "none",
          "flexDirection": "column",
          "overflow": "hidden",
          "boxSizing": "border-box",
      },
      children=[
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
                          _test_case_card(),
                          _assertions_header(),
                          _simulation_controls(),
                          _suggestions_accordion(),
                          dmc.Stack(
                              id=Ids.TC_ASSERT_LIST,
                              gap="md",
                              mb="xl",
                              children=[],
                          ),
                          _add_assertion_placeholder(),
                          html.Div(id=Ids.TC_RESULT_CONTAINER),
                      ],
                  )
              ],
          ),
      ],
  )


def _editor_shell():
  """Renders the sidebar and editor side by side."""
  return dmc.Flex(
      h="calc(100vh - 280px)",
      style={"height": "calc(100vh - 280px)", "overflow": "hidden"},
      children=[
          _sidebar(),
          dmc.Box(
              style={
                  "flex": 1,
                  "minHeight": 0,
                  "display": "flex",
                  "flexDirection": "column",
                  "overflow": "hidden",
              },
              children=[
                  _editor_empty_state(),
                  _editor_container(),
              ],
          ),
      ],
  )


def _delete_modal():
  """Renders the confirmation modal for deleting a test case."""
  return dmc.Modal(
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
  )


def _suggestion_modal():
  """Renders the modal listing suggestions drawn from recent runs."""
  return dmc.Modal(
      id=Ids.SUGGESTION_MODAL,
      size="lg",
      radius="md",
      children=[
          dmc.Stack([
              # Why the modal is empty, when it is. This used to sit
              # out here under display:none, so the four messages
              # show_history_suggestions writes to it reached nobody
              # and every empty modal said the same generic thing.
              html.Div(id=Ids.VAL_MSG),
              dash.dcc.Loading(
                  dmc.Stack(id=Ids.SUGGESTION_LIST),
                  id=Ids.TC_SUGGEST_LOADING,
              ),
              dmc.Group(
                  justify="flex-end",
                  mt="md",
                  children=[
                      # Not disabled. Nothing re-enables it, and
                      # confirm_suggestions already no-ops when
                      # nothing is checked.
                      dmc.Button(
                          "Add Selected",
                          id=Ids.SUGGESTION_ADD_BTN,
                          radius="md",
                      )
                  ],
              ),
          ])
      ],
      title="Suggestions from Recent Runs",
  )


def _assertion_modal_header():
  """Renders the assertion modal title row and its delete button."""
  return dmc.Group(
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
                      "Define validation rules for agent response",
                      size="sm",
                      c="dimmed",
                  ),
              ],
          ),
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
              style={"display": "none"},
          ),
      ],
  )


def _assertion_modal():
  """Renders the modal for adding or editing an assertion."""
  return dmc.Modal(
      id=Ids.ASSERT_MODAL,
      size="80%",
      radius="md",
      title="Manage Assertion",
      children=[
          _assertion_modal_header(),
          dmc.Box(
              p="lg",
              style={"maxHeight": "70vh", "overflowY": "auto"},
              children=render_assertion_form_content(),
          ),
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
                      # test_suite_questions_callbacks closes the
                      # assertion modal on this id.
                      id=Ids.ASSERT_MODAL_CANCEL_BTN_FOOTER,
                      variant="subtle",
                      color="gray",
                  ),
                  dmc.Button(
                      "Save Assertion",
                      id=Ids.ASSERT_MODAL_CONFIRM_BTN,
                      leftSection=DashIconify(icon="material-symbols:check"),
                      color="indigo",
                  ),
              ],
          ),
      ],
  )


def layout(suite_id: str | None = None, **_):
  return render_page(
      title="Edit Test Cases",
      description="Interactively edit test cases and run ad-hoc simulations.",
      fluid=True,
      breadcrumbs=_breadcrumbs(),
      children=[
          _editor_shell(),
          dash.dcc.Store(id=Ids.STORE_BUILDER, data=[]),
          dash.dcc.Store(id=Ids.STORE_SELECTED_INDEX, data=None),
          dash.dcc.Store(id=Ids.STORE_PLAYGROUND_RESULT, data=None),
          dash.dcc.Store(id=Ids.STORE_DELETE_TEST_CASE_INDEX, data=None),
          dash.dcc.Store(id=Ids.STORE_DELETE_ASSERTION_INDEX, data=None),
          _delete_modal(),
          render_bulk_add_modal(),
          dash.dcc.Store(id=Ids.STORE_SUGGESTIONS, data=[]),
          # Separate from STORE_SUGGESTIONS, which holds what the last ad-hoc
          # run proposed. One store held both, and the two readers are
          # different panels: opening Suggestions from recent runs replaced the
          # inline accordion's contents with historical suggestions from other
          # trials and other agents, and adding one from the modal left a live
          # Accept button on the same suggestion in the accordion behind it.
          dash.dcc.Store(id=Ids.STORE_HISTORY_SUGGESTIONS, data=[]),
          _suggestion_modal(),
          _assertion_modal(),
          dash.dcc.Store(id=Ids.STORE_ASSERT_EDIT_INDEX, data=None),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path_template="/test_suites/edit/<suite_id>",
      title="Prism | Edit Test Cases",
      layout=layout,
  )
