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

"""Layout for Run Comparison Page."""

import dash
from dash import dcc
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.comparison_ids import ComparisonIds


def layout(**_kwargs):
  """Layout for the Run Comparison page."""
  return render_page(
      title="Run Comparison",
      description=[
          (
              "Analyze performance deltas, identify regressions, and track"
              " improvements between evaluation runs."
          ),
      ],
      actions=[
          dmc.Button(
              "Select Runs",
              id=ComparisonIds.BTN_OPEN_SELECT_RUNS,
              leftSection=DashIconify(
                  icon="material-symbols:tune",
                  width=20,
              ),
              radius="md",
          ),
      ],
      children=[
          # Local Location for Page Scoped Callbacks
          dcc.Location(id=ComparisonIds.LOC_URL, refresh=False),
          _render_select_runs_modal(),
          # Empty State (Hidden when runs are selected)
          html.Div(
              id=ComparisonIds.EMPTY_STATE,
              style={"display": "none"},
              children=[
                  dmc.Center(
                      style={"height": "60vh"},
                      children=dmc.Stack(
                          align="center",
                          children=[
                              DashIconify(
                                  icon="material-symbols:compare",
                                  width=80,
                                  color="dimmed",
                              ),
                              dmc.Title(
                                  "No runs selected", order=2, c="dimmed"
                              ),
                              dmc.Text(
                                  "Select two evaluation runs to compare their"
                                  " performance and spot regressions.",
                                  c="dimmed",
                                  ta="center",
                                  maw=400,
                              ),
                              dmc.Button(
                                  "Select Runs",
                                  id=ComparisonIds.BTN_EMPTY_SELECT_RUNS,
                                  size="lg",
                                  radius="md",
                                  mt="md",
                              ),
                          ],
                      ),
                  )
              ],
          ),
          # Summary Section
          html.Div(
              id=ComparisonIds.SUMMARY_SECTION,
              children=[
                  html.Div(
                      id=ComparisonIds.SUBTITLE_TEXT,
                      style={"marginBottom": "1.5rem"},
                  ),
                  # Top Metrics
                  dmc.SimpleGrid(
                      cols=4,
                      spacing="md",
                      id=ComparisonIds.METRICS_CARDS,
                      mb="xl",
                  ),
                  # Charts
                  dmc.Grid(
                      gutter="md",
                      mb="xl",
                      align="stretch",
                      children=[
                          dmc.GridCol(
                              span=8,
                              style={"display": "flex"},
                              children=dmc.Paper(
                                  withBorder=True,
                                  p="lg",
                                  radius="md",
                                  shadow="sm",
                                  style={
                                      "height": "100%",
                                      "width": "100%",
                                      "display": "flex",
                                      "flexDirection": "column",
                                  },
                                  children=[
                                      dmc.Group(
                                          justify="space-between",
                                          mb="xl",
                                          children=[
                                              dmc.Text(
                                                  "Performance Delta",
                                                  fw=700,
                                                  size="lg",
                                              ),
                                              dmc.Badge(
                                                  "Trials Accuracy",
                                                  variant="light",
                                                  color="gray",
                                              ),
                                          ],
                                      ),
                                      html.Div(
                                          id=ComparisonIds.PERFORMANCE_DELTA_CHART,
                                          style={
                                              "flex": 1,
                                              "display": "flex",
                                              "flexDirection": "column",
                                          },
                                      ),
                                  ],
                              ),
                          ),
                          dmc.GridCol(
                              span=4,
                              style={"display": "flex"},
                              children=dmc.Paper(
                                  withBorder=True,
                                  p="lg",
                                  radius="md",
                                  shadow="sm",
                                  style={
                                      "height": "100%",
                                      "width": "100%",
                                      "display": "flex",
                                      "flexDirection": "column",
                                  },
                                  children=[
                                      dmc.Text(
                                          "Avg Delta by Assertion",
                                          fw=700,
                                          size="lg",
                                          mb="xl",
                                      ),
                                      dmc.Stack(
                                          id=ComparisonIds.ASSERTION_DELTA_CHART,
                                          gap="xl",
                                      ),
                                  ],
                              ),
                          ),
                      ],
                  ),
              ],
          ),
          # Agent Context Diff Section
          dmc.Accordion(
              chevronPosition="right",
              variant="separated",
              radius="md",
              mt="xl",
              id=ComparisonIds.CONTEXT_DIFF_ACCORDION,
              value="context-diff",
              styles={
                  "content": {"padding": 0},
                  "item": {"border": "1px solid var(--mantine-color-gray-2)"},
                  "control": {
                      "padding": (
                          "var(--mantine-spacing-md) var(--mantine-spacing-xl)"
                      )
                  },
              },
              children=[
                  dmc.AccordionItem(
                      value="context-diff",
                      style={
                          "overflow": "hidden",
                          "backgroundColor": "white",
                      },
                      children=[
                          dmc.AccordionControl(
                              dmc.Group(
                                  justify="space-between",
                                  children=[
                                      dmc.Group(
                                          gap="sm",
                                          children=[
                                              dmc.Text(
                                                  "Agent Context Diff",
                                                  fw=700,
                                                  size="lg",
                                              ),
                                              dmc.Badge(
                                                  "CONTEXT DIFF",
                                                  id=ComparisonIds.CONTEXT_DIFF_BADGE,
                                                  color="gray",
                                                  variant="light",
                                                  radius="sm",
                                                  size="sm",
                                              ),
                                          ],
                                      ),
                                  ],
                              )
                          ),
                          dmc.AccordionPanel(
                              p=0,
                              children=[
                                  # Info Banner
                                  dmc.Box(
                                      p="lg",
                                      bg="var(--mantine-color-gray-0)",
                                      style={
                                          "borderBottom": (
                                              "1px solid"
                                              " var(--mantine-color-gray-2)"
                                          ),
                                          "borderTop": (
                                              "1px solid"
                                              " var(--mantine-color-gray-2)"
                                          ),
                                      },
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
                                                  "Agent context includes"
                                                  " datasources, system"
                                                  " instructions, examples,"
                                                  " and knowledge used to"
                                                  " guide the agent. A"
                                                  " snapshot of this context is"
                                                  " captured at the moment an"
                                                  " evaluation run starts to"
                                                  " ensure consistent and"
                                                  " reproducible results.",
                                                  size="sm",
                                                  c="dimmed",
                                                  lh=1.5,
                                              ),
                                          ],
                                      ),
                                  ),
                                  # Unified View Header
                                  dmc.Group(
                                      justify="space-between",
                                      px="lg",
                                      py="xs",
                                      bg="var(--mantine-color-gray-1)",
                                      style={
                                          "borderBottom": (
                                              "1px solid"
                                              " var(--mantine-color-gray-2)"
                                          )
                                      },
                                      children=[
                                          dmc.Text(
                                              "Unified View",
                                              size="xs",
                                              fw=700,
                                              c="dimmed",
                                              tt="uppercase",
                                          ),
                                      ],
                                  ),
                                  # Diff Content
                                  dmc.Box(
                                      id=ComparisonIds.CONTEXT_DIFF_CONTENT,
                                      style={"overflowX": "auto"},
                                      children=[
                                          dmc.Text(
                                              "Select two runs to compare"
                                              " their configurations.",
                                              c="dimmed",
                                              ta="center",
                                              size="sm",
                                              py="xl",
                                          )
                                      ],
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          ),
          # Filter Bar
          dmc.Box(id=ComparisonIds.FILTER_BAR),
          # Comparison List
          dmc.Stack(
              id=ComparisonIds.COMPARISON_LIST,
              gap="md",
              children=[
                  # Populated by callback
                  dmc.Loader(color="blue", variant="dots")
              ],
          ),
      ],
  )


def _render_select_runs_modal():
  """Renders the modal for selecting runs."""
  return dmc.Modal(
      id=ComparisonIds.SELECT_RUNS_MODAL,
      title="Select Runs to Compare",
      size="lg",
      radius="md",
      children=[
          dmc.Stack(
              children=[
                  dmc.Select(
                      label="Evaluation Dataset",
                      placeholder="Select a Dataset first",
                      id=ComparisonIds.DATASET_SELECT,
                      data=[],
                      searchable=True,
                      leftSection=DashIconify(
                          icon="material-symbols:database",
                          width=20,
                      ),
                  ),
                  dmc.Grid(
                      children=[
                          dmc.GridCol(
                              span=5,
                              children=dmc.Select(
                                  label="Base Run (Baseline)",
                                  placeholder="Select Base Run",
                                  id=ComparisonIds.BASE_RUN_SELECT,
                                  data=[],
                                  searchable=True,
                                  leftSection=DashIconify(
                                      icon="material-symbols:flag",
                                      width=20,
                                  ),
                              ),
                          ),
                          dmc.GridCol(
                              span=2,
                              children=dmc.Center(
                                  mt="xl",
                                  children=dmc.ActionIcon(
                                      DashIconify(
                                          icon="material-symbols:swap-horiz",
                                          width=24,
                                      ),
                                      id=ComparisonIds.BTN_SWAP_RUNS,
                                      variant="default",
                                      radius="md",
                                      size="lg",
                                  ),
                              ),
                          ),
                          dmc.GridCol(
                              span=5,
                              children=dmc.Select(
                                  label="Challenger Run (Candidate)",
                                  placeholder="Select Challenger Run",
                                  id=ComparisonIds.CHALLENGE_RUN_SELECT,
                                  data=[],
                                  searchable=True,
                                  leftSection=DashIconify(
                                      icon="material-symbols:science",
                                      width=20,
                                  ),
                              ),
                          ),
                      ]
                  ),
                  dmc.Group(
                      justify="flex-end",
                      mt="xl",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=ComparisonIds.BTN_CLOSE_SELECT_RUNS,
                              variant="subtle",
                              color="gray",
                          ),
                          dmc.Button(
                              "Compare Runs",
                              id=ComparisonIds.BTN_APPLY_SELECT_RUNS,
                              radius="md",
                          ),
                      ],
                  ),
              ]
          )
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path="/compare",
      title="Run Comparison | Prism",
      layout=layout,
  )
