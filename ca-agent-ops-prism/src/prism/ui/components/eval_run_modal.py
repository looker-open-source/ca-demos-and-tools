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

"""Run Evaluation Modal Component."""

from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common.schemas.suite import Suite
from prism.ui.components.badges import render_coverage_badge
from prism.ui.pages.agent_ids import AgentIds


def get_quality_badge(suite: Suite):
  """Returns the quality badge based on assertion coverage."""
  total_questions = len(suite.examples)
  questions_with_asserts = sum(1 for e in suite.examples if e.asserts)

  if total_questions == 0:
    return render_coverage_badge("No Test Cases", "gray")

  if questions_with_asserts == total_questions:
    return render_coverage_badge("Full Coverage", "green")
  elif questions_with_asserts > 0:
    return render_coverage_badge("Partial Coverage", "yellow")
  else:
    return render_coverage_badge("No Coverage", "red")


def render_dataset_card(suite: Suite | None):
  """Renders the dataset details card."""
  if not suite:
    return None

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p=0,
      children=[
          # Header
          dmc.Group(
              justify="space-between",
              p="md",
              bg="gray.0",
              style={"borderBottom": "1px solid #e9ecef"},
              children=[
                  dmc.Text(suite.name, fw=600, size="sm"),
                  get_quality_badge(suite),
              ],
          ),
          # Grid
          dmc.SimpleGrid(
              cols=2,
              p="md",
              spacing="md",
              children=[
                  html.Div([
                      dmc.Text(
                          "TEST CASES",
                          size="xs",
                          c="dimmed",
                          fw=600,
                          tt="uppercase",
                      ),
                      dmc.Text(
                          f"{len(suite.examples)} test cases", size="sm", fw=500
                      ),
                  ]),
                  html.Div([
                      dmc.Text(
                          "LAST UPDATED",
                          size="xs",
                          c="dimmed",
                          fw=600,
                          tt="uppercase",
                      ),
                      # Timestamp formatting should happen here or passed in
                      dmc.Text(
                          suite.modified_at.strftime("%b %d, %Y")
                          if suite.modified_at
                          else "N/A",
                          size="sm",
                          fw=500,
                      ),
                  ]),
              ],
          ),
          # Description
          dmc.Box(
              p="md",
              style={"borderTop": "1px solid #e9ecef"},
              children=[
                  dmc.Text(
                      "DESCRIPTION",
                      size="xs",
                      c="dimmed",
                      fw=600,
                      tt="uppercase",
                      mb=4,
                  ),
                  dmc.Text(
                      suite.description or "No description provided.",
                      size="sm",
                      c="dimmed",
                      style={"lineHeight": 1.5},
                  ),
              ],
          ),
      ],
  )


def render_modal():
  """Renders the Run Evaluation Modal structure."""
  return dmc.Modal(
      id=AgentIds.Detail.EvalModal.ROOT,
      title=None,  # Custom header
      withCloseButton=False,
      padding=0,
      size="xl",
      radius="md",
      centered=True,
      children=[
          # Header
          dmc.Group(
              justify="space-between",
              p="lg",
              style={"borderBottom": "1px solid #e9ecef"},
              children=[
                  html.Div([
                      dmc.Title("Evaluate Agent on Dataset", order=3),
                      dmc.Text(
                          "Select a test dataset to assess the performance of"
                          " your agent.",
                          c="dimmed",
                          size="sm",
                      ),
                  ]),
                  dmc.ActionIcon(
                      DashIconify(icon="material-symbols:close", width=24),
                      variant="subtle",
                      color="gray",
                      radius="md",
                      id=AgentIds.Detail.EvalModal.BTN_CANCEL + "-x",
                      n_clicks=0,
                  ),
              ],
          ),
          # Body
          dmc.Stack(
              p="lg",
              gap="lg",
              children=[
                  # Validation Alert
                  html.Div(id=AgentIds.Detail.EvalModal.ALERT_VALIDATION),
                  # Select Dataset
                  dmc.Stack(
                      gap=4,  # Close gap between label and select
                      children=[
                          dmc.Group(
                              justify="space-between",
                              children=[
                                  dmc.Text(
                                      "Select a Dataset", fw=500, size="sm"
                                  ),
                                  dmc.Anchor(
                                      "Manage Test Suites",
                                      href="/test_suites",
                                      size="xs",
                                      c="blue",
                                      underline=False,
                                  ),
                              ],
                          ),
                          dmc.Select(
                              id=AgentIds.Detail.EvalModal.SELECT_DATASET,
                              placeholder="Search or select a dataset...",
                              data=[],  # Populated via callback
                              searchable=True,
                              nothingFoundMessage=(
                                  "No compatible datasets found"
                              ),
                              leftSection=DashIconify(
                                  icon="material-symbols:dataset"
                              ),
                          ),
                      ],
                  ),
                  # Dataset Details
                  html.Div(
                      id=AgentIds.Detail.EvalModal.DATASET_DETAILS,
                      children=dmc.Alert(
                          "Select a dataset to view details.",
                          color="blue",
                          variant="light",
                      ),
                  ),
              ],
          ),
          # Footer
          dmc.Group(
              justify="flex-end",
              p="lg",
              bg="gray.0",
              style={"borderTop": "1px solid #e9ecef"},
              children=[
                  dmc.Button(
                      "Cancel",
                      variant="default",
                      id=AgentIds.Detail.EvalModal.BTN_CANCEL,
                      n_clicks=0,
                  ),
                  dmc.Button(
                      "Start Evaluation",
                      id=AgentIds.Detail.EvalModal.BTN_START,
                      leftSection=DashIconify(
                          icon="material-symbols:play-arrow"
                      ),
                      n_clicks=0,
                      disabled=True,
                  ),
              ],
          ),
      ],
  )
