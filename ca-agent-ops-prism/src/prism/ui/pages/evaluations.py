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

"""Evaluations list page."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.ids import EvaluationIds as Ids


def layout(**kwargs):  # pylint: disable=unused-argument
  """Renders the Evaluations list layout."""
  return render_page(
      title="Evaluations",
      description=(
          "Track the history and status of evaluation runs across your agent"
          " fleet."
      ),
      actions=[
          dmc.Button(
              "Start New Evaluation",
              id=Ids.BTN_NEW_EVAL,
              leftSection=DashIconify(icon="bi:plus"),
              radius="md",
          ),
      ],
      children=[
          dmc.Stack(
              gap="lg",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Group(
                              children=[
                                  dmc.Select(
                                      id=Ids.FILTER_AGENT,
                                      label="Filter by Agent",
                                      placeholder="All Agents",
                                      data=[],
                                      clearable=True,
                                      style={"width": 250},
                                  ),
                                  dmc.Select(
                                      id=Ids.FILTER_SUITE,
                                      label="Filter by Test Suite",
                                      placeholder="All Test Suites",
                                      data=[],
                                      clearable=True,
                                      style={"width": 250},
                                  ),
                                  dmc.Select(
                                      id=Ids.FILTER_STATUS,
                                      label="Filter by Status",
                                      placeholder="All Statuses",
                                      data=[
                                          {
                                              "label": "Pending",
                                              "value": "PENDING",
                                          },
                                          {
                                              "label": "Running",
                                              "value": "RUNNING",
                                          },
                                          {
                                              "label": "Completed",
                                              "value": "COMPLETED",
                                          },
                                          {
                                              "label": "Failed",
                                              "value": "FAILED",
                                          },
                                          {
                                              "label": "Cancelled",
                                              "value": "CANCELLED",
                                          },
                                      ],
                                      clearable=True,
                                      style={"width": 200},
                                  ),
                              ],
                          ),
                          dmc.Switch(
                              id=Ids.SWITCH_ARCHIVED,
                              label="Show Archived",
                              size="sm",
                              checked=False,
                          ),
                      ],
                      gap="md",
                  ),
                  dmc.Paper(
                      withBorder=True,
                      radius="md",
                      p=0,
                      shadow="sm",
                      style={"overflow": "hidden"},
                      children=[
                          html.Div(
                              id=Ids.RUN_LIST_CONTAINER,
                              children=[
                                  dmc.Center(
                                      children=[dmc.Loader(variant="dots")],
                                      py="xl",
                                  )
                              ],
                          )
                      ],
                  ),
              ],
          ),
          render_new_run_modal(),
      ],
  )


def render_new_run_modal():
  """Renders the New Evaluation Run modal."""
  return dmc.Modal(
      id=Ids.MODAL_NEW_EVAL,
      title="Start New Evaluation",
      size="md",
      children=[
          dmc.Stack(
              children=[
                  dmc.Text(
                      "Select an agent and a compatible test suite to"
                      " evaluate.",
                      size="sm",
                      mb="md",
                  ),
                  dmc.Select(
                      id=Ids.NEW_EVAL_AGENT_SELECT,
                      label="Select Agent",
                      placeholder="Pick an agent",
                      searchable=True,
                      data=[],  # Populated when modal opens
                      mb="sm",
                  ),
                  dmc.Select(
                      id=Ids.NEW_EVAL_SUITE_SELECT,
                      label="Select Test Suite",
                      placeholder="Pick a test suite",
                      searchable=True,
                      data=[],  # Populated when agent selected
                      mb="sm",
                  ),
                  dmc.Switch(
                      id=Ids.TOGGLE_SUGGESTIONS,
                      label="Generate Suggested Assertions",
                      description=(
                          "Automatically suggest new assertions based on trace"
                          " results (Uses LLM)."
                      ),
                      checked=False,
                      mb="sm",
                  ),
                  dmc.NumberInput(
                      id=Ids.NEW_EVAL_INPUT_CONCURRENCY,
                      label="Concurrency",
                      description="Number of trials to run in parallel.",
                      value=2,
                      min=1,
                      max=100,
                      step=1,
                      mb="xl",
                  ),
                  dmc.Group(
                      justify="flex-end",
                      children=[
                          dmc.Button(
                              "Cancel",
                              id=Ids.BTN_CANCEL_NEW_EVAL,
                              variant="subtle",
                              color="gray",
                          ),
                          dmc.Button(
                              "Start Run",
                              id=Ids.BTN_START_NEW_EVAL,
                              color="green",
                              leftSection=DashIconify(icon="bi:play-fill"),
                          ),
                      ],
                  ),
              ]
          )
      ],
  )


def register_page():
  dash.register_page(
      __name__, path="/evaluations", title="Prism | Evaluations", layout=layout
  )
