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

"""Page for monitoring an existing GCP agent."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.agent_ids import AgentIds


def _discovery_form():
  """Returns the discovery form."""
  return dmc.Paper(
      withBorder=True,
      shadow="sm",
      radius="md",
      children=[
          dmc.Stack(
              p="xl",
              gap="md",
              children=[
                  dmc.SimpleGrid(
                      cols={"base": 1, "sm": 2},
                      spacing="xl",
                      children=[
                          dmc.Select(
                              label="GCP Project",
                              description=(
                                  "The Google Cloud project ID containing the"
                                  " agent resources."
                              ),
                              placeholder="Select project",
                              id=AgentIds.Monitor.INPUT_PROJECT,
                              required=True,
                              withAsterisk=True,
                              data=[],  # Populated via callback
                              size="md",
                          ),
                          dmc.TextInput(
                              label="GCP Location",
                              description=(
                                  "The Google Cloud region where the agent"
                                  " resources are located."
                              ),
                              placeholder="e.g. us-central1",
                              id=AgentIds.Monitor.INPUT_LOCATION,
                              required=True,
                              withAsterisk=True,
                              value="global",
                              size="md",
                          ),
                      ],
                  ),
                  dmc.Button(
                      "Discover Agents",
                      id=AgentIds.Monitor.BTN_FETCH,
                      leftSection=DashIconify(icon="bi:search", width=20),
                      fullWidth=True,
                      radius="md",
                  ),
              ],
          ),
          # Results area
          dmc.Box(
              style={"borderTop": "1px solid var(--mantine-color-gray-3)"},
              children=[
                  html.Div(
                      id=AgentIds.Monitor.TABLE_ROOT,
                      style={"minHeight": "100px"},
                      children=[
                          dmc.Center(
                              dmc.Text(
                                  "Enter project and location to discover"
                                  " agents.",
                                  c="dimmed",
                                  py=100,
                              )
                          )
                      ],
                  )
              ],
          ),
          # State storage
          dash.dcc.Store(id="discovered-agents-store"),
          dash.dcc.Store(id=AgentIds.Monitor.STORE_FETCH_TRIGGER),
      ],
  )


def layout():
  return render_page(
      title="Discover Existing Agents",
      description=(
          "Discover and connect to agents already deployed in your Google Cloud"
          " projects."
      ),
      breadcrumbs=dmc.Breadcrumbs(
          children=[
              dmc.Anchor("Agents", href="/agents", size="sm", fw=500),
              dmc.Text("Onboarding", size="sm", fw=500, c="dimmed"),
              dmc.Text("Discover", size="sm", fw=500, c="dimmed"),
          ],
      ),
      children=[
          _discovery_form(),
      ],
  )


def register_page():
  dash.register_page(__name__, path="/agents/onboard/existing", layout=layout)
