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

"""Page for adding a new agent."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.common.schemas.agent import AgentEnv
from prism.ui.components.page_layout import render_page
from prism.ui.pages.agent_ids import AgentIds


def _create_form():
  """Returns the agent creation form."""
  return dmc.Paper(
      withBorder=True,
      radius="md",
      style={"position": "relative"},
      className="max-w-[1000px] mx-auto overflow-hidden",
      children=[
          dmc.LoadingOverlay(
              visible=False,
              id="agent-add-loading-overlay",
              overlayProps={"blur": 2},
          ),
          # Section 1: Agent Identity
          dmc.Stack(
              p=40,
              gap="xl",
              style={"borderBottom": "1px solid var(--mantine-color-gray-3)"},
              children=[
                  dmc.Text("Agent Identity", fw=700, size="lg"),
                  dmc.TextInput(
                      label="Agent Name",
                      placeholder="e.g., Customer Support Bot V1",
                      id=AgentIds.Form.INPUT_NAME,
                      required=True,
                      size="md",
                  ),
                  dmc.Stack(
                      gap=4,
                      children=[
                          dmc.Text("System Instruction", size="sm", fw=500),
                          dmc.Textarea(
                              placeholder=(
                                  "Define the persona, tone, and behavioral"
                                  " instructions for the agent..."
                              ),
                              id=AgentIds.Form.TEXTAREA_INSTRUCTION,
                              minRows=6,
                              autosize=True,
                              size="md",
                          ),
                      ],
                  ),
              ],
          ),
          # Section 2: Infrastructure
          dmc.Box(
              p=40,
              style={
                  "backgroundColor": "rgba(248, 249, 250, 0.5)",
                  "borderBottom": "1px solid var(--mantine-color-gray-3)",
              },
              children=[
                  dmc.Text("Infrastructure", fw=700, size="lg", mb="xl"),
                  dmc.SimpleGrid(
                      cols=2,
                      spacing="xl",
                      children=[
                          dmc.Select(
                              label="GCP Project",
                              description=(
                                  "The Google Cloud project ID containing the"
                                  " agent resources."
                              ),
                              placeholder="Select project",
                              id=AgentIds.Form.INPUT_PROJECT,
                              required=True,
                              size="md",
                              data=[],  # Populated via callback
                          ),
                          dmc.TextInput(
                              label="GCP Location",
                              description=(
                                  "The Google Cloud region where the agent"
                                  " resources are located."
                              ),
                              placeholder="global",
                              id=AgentIds.Form.INPUT_LOCATION,
                              value="global",
                              required=True,
                              size="md",
                          ),
                      ],
                  ),
                  dmc.Select(
                      label="GDA Environment",
                      description=(
                          "The Gemini Data Analytics environment where this"
                          " agent is hosted."
                      ),
                      data=[
                          {
                              "label": (
                                  "production"
                                  if e == AgentEnv.PROD
                                  else e.name.lower()
                              ),
                              "value": e.value,
                          }
                          for e in AgentEnv
                      ],
                      value=AgentEnv.PROD.value,
                      id=AgentIds.Form.SELECT_ENV,
                      required=True,
                      mt="xl",
                      size="md",
                  ),
              ],
          ),
          # Section 3: Datasource Configuration
          dmc.Stack(
              p=40,
              gap="xl",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Text(
                              "Datasource Configuration", fw=700, size="lg"
                          ),
                          dmc.SegmentedControl(
                              id=AgentIds.Form.SELECT_DATASOURCE_TYPE,
                              data=[
                                  {"label": "BigQuery", "value": "bq"},
                                  {"label": "Looker", "value": "looker"},
                              ],
                              value="bq",
                              size="sm",
                              radius="md",
                          ),
                      ],
                  ),
                  dmc.Text(
                      "Choose the source of truth for your agent's analytics.",
                      size="sm",
                      c="dimmed",
                      mt=-15,
                  ),
                  # BigQuery Configuration
                  html.Div(
                      id="bq-datasource-container",
                      children=[
                          dmc.Stack(
                              gap="md",
                              children=[
                                  dmc.Textarea(
                                      label="BigQuery Tables",
                                      description=(
                                          "Enter full table paths"
                                          " (project.dataset.table), one per"
                                          " line."
                                      ),
                                      placeholder="project.dataset.table_1\nproject.dataset.table_2",
                                      id=AgentIds.Form.INPUT_BQ_TABLES,
                                      required=True,
                                      size="md",
                                      minRows=3,
                                      autosize=True,
                                  ),
                                  dmc.Group(
                                      id=AgentIds.Form.INPUT_BQ_TABLES_PREVIEW,
                                      gap="xs",
                                      mt="xs",
                                  ),
                              ],
                          )
                      ],
                  ),
                  # Looker Configuration
                  html.Div(
                      id="looker-datasource-container",
                      style={"display": "none"},
                      children=[
                          dmc.Stack(
                              gap="md",
                              children=[
                                  dmc.TextInput(
                                      label="Looker Instance URI",
                                      placeholder="https://your-looker.com",
                                      id=AgentIds.Form.INPUT_LOOKER_URI,
                                      required=True,
                                      size="md",
                                  ),
                                  dmc.Textarea(
                                      label="Looker Explores",
                                      description=(
                                          "Enter model.explore paths, one per"
                                          " line."
                                      ),
                                      placeholder=(
                                          "model_1.explore_1\nmodel_2.explore_2"
                                      ),
                                      id=AgentIds.Form.INPUT_LOOKER_EXPLORES,
                                      required=True,
                                      size="md",
                                      minRows=3,
                                      autosize=True,
                                  ),
                                  dmc.Group(
                                      id=AgentIds.Form.INPUT_LOOKER_EXPLORES_PREVIEW,
                                      gap="xs",
                                      mt="xs",
                                  ),
                                  dmc.SimpleGrid(
                                      cols=2,
                                      spacing="xl",
                                      children=[
                                          dmc.TextInput(
                                              label="Looker Client ID",
                                              id=AgentIds.Form.INPUT_LOOKER_CLIENT_ID,
                                              size="md",
                                          ),
                                          dmc.PasswordInput(
                                              label="Looker Client Secret",
                                              id=AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET,
                                              size="md",
                                          ),
                                      ],
                                  ),
                                  dmc.Group(
                                      justify="flex-end",
                                      mt="md",
                                      children=[
                                          dmc.Button(
                                              "Test Connection",
                                              id=AgentIds.Form.BTN_TEST_LOOKER,
                                              variant="subtle",
                                              size="sm",
                                              radius="md",
                                              leftSection=DashIconify(
                                                  icon=(
                                                      "material-symbols:vpn-key"
                                                  )
                                              ),
                                          ),
                                      ],
                                  ),
                                  dmc.Alert(
                                      id=AgentIds.Form.ALERT_LOOKER_TEST,
                                      hide=True,
                                      radius="md",
                                  ),
                              ],
                          )
                      ],
                  ),
              ],
          ),
          # Footer
          dmc.Group(
              p=40,
              justify="flex-end",
              style={
                  "backgroundColor": "rgba(248, 249, 250, 0.5)",
                  "borderTop": "1px solid var(--mantine-color-gray-3)",
              },
              children=[
                  dmc.Anchor(
                      dmc.Button(
                          "Cancel",
                          variant="subtle",
                          color="gray",
                          id=AgentIds.Add.BTN_CANCEL,
                          fw=500,
                      ),
                      href="/agents",
                      underline=False,
                  ),
                  dmc.Button(
                      "Create Agent",
                      id=AgentIds.Add.BTN_SUBMIT,
                      leftSection=DashIconify(icon="bi:plus-circle", width=18),
                      radius="md",
                      className="shadow-md shadow-indigo-500/20",
                  ),
              ],
          ),
      ],
  )


def layout():
  return render_page(
      title="Onboard New Agent",
      description="Configure your agent's identity and data connections.",
      breadcrumbs=dmc.Breadcrumbs(
          children=[
              dmc.Anchor(
                  "Agents",
                  href="/agents",
                  size="sm",
                  fw=500,
              ),
              dmc.Text("Onboarding", size="sm", c="dimmed", fw=500),
              dmc.Text("New", size="sm", c="dimmed", fw=500),
          ],
      ),
      children=[
          _create_form(),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path="/agents/onboard/new",
      title="Prism | New Agent",
      layout=layout,
  )
