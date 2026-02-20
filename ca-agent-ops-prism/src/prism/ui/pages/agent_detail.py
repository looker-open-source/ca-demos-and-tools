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

"""Agent Detail Page."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.agent_ids import AgentIds


def _edit_modal():
  """Returns the edit modal for agent details."""
  return dmc.Modal(
      title="Edit Agent Details",
      id=AgentIds.Detail.MODAL_EDIT,
      zIndex=10000,
      size="lg",
      radius="md",
      padding="xl",
      children=[
          html.Div(
              style={"position": "relative"},
              children=[
                  dmc.LoadingOverlay(
                      visible=False,
                      id=AgentIds.Detail.EDIT_LOADING_OVERLAY,
                      overlayProps={"blur": 2},
                  ),
                  dmc.Stack(
                      gap="lg",
                      children=[
                          dmc.Alert(
                              "Updating System Instructions or Datasource"
                              " Configuration here will also update the agent's"
                              " published context in Gemini Data Analytics. The"
                              " agent name and Looker credentials are updated"
                              " locally within Prism.",
                              title="Synchronization Info",
                              icon=DashIconify(
                                  icon="material-symbols:info-outline"
                              ),
                              color="blue",
                              radius="md",
                              mb="lg",
                          ),
                          # --- Top Section: Basic Info ---
                          dmc.Stack(
                              gap="md",
                              children=[
                                  dmc.TextInput(
                                      label="Agent Name",
                                      placeholder="e.g. Sales Assistant",
                                      id=AgentIds.Detail.INPUT_EDIT_NAME,
                                      required=True,
                                      radius="md",
                                  ),
                                  dmc.Textarea(
                                      label="System Instruction",
                                      placeholder=(
                                          "Define how the agent should"
                                          " behave..."
                                      ),
                                      id=AgentIds.Detail.TEXTAREA_EDIT_INSTRUCTION,
                                      minRows=6,
                                      radius="md",
                                      autosize=True,
                                      maxRows=12,
                                  ),
                              ],
                          ),
                          dmc.Divider(),
                          # --- Golden Queries ---
                          dmc.Stack(
                              gap="sm",
                              children=[
                                  dmc.Group(
                                      justify="space-between",
                                      children=[
                                          dmc.Group(
                                              children=[
                                                  DashIconify(
                                                      icon="material-symbols:lightbulb",
                                                      width=24,
                                                      color="yellow",
                                                  ),
                                                  dmc.Text(
                                                      "Golden Queries",
                                                      fw=600,
                                                      size="lg",
                                                  ),
                                                  dmc.Badge(
                                                      "Optional",
                                                      color="gray",
                                                      variant="light",
                                                  ),
                                              ]
                                          ),
                                          dmc.Button(
                                              "Fix with AI",
                                              id=AgentIds.Detail.BTN_FIX_GOLDEN_QUERIES_AI,
                                              leftSection=DashIconify(
                                                  icon="material-symbols:magic-button",
                                                  width=16,
                                              ),
                                              variant="light",
                                              color="violet",
                                              size="xs",
                                          ),
                                      ],
                                  ),
                                  dash.dcc.Loading(
                                      id="loading-golden-queries",
                                      children=[
                                          dmc.Textarea(
                                              label="Golden Queries (JSON)",
                                              description=(
                                                  "List of golden queries to"
                                                  " guide the agent. Format:"
                                                  " JSON list of objects."
                                              ),
                                              placeholder=(
                                                  '[{"natural_language_questions":'
                                                  ' ["..."], "looker_query":'
                                                  " {...}}]"
                                              ),
                                              id=AgentIds.Detail.INPUT_EDIT_GOLDEN_QUERIES,
                                              radius="md",
                                              minRows=5,
                                              autosize=True,
                                              maxRows=15,
                                          ),
                                      ],
                                  ),
                                  dmc.Text(
                                      id=AgentIds.Detail.ERROR_GOLDEN_QUERIES,
                                      c="red",
                                      size="xs",
                                  ),
                              ],
                          ),
                          dmc.Divider(),
                          # --- Datasource Config ---
                          dmc.Stack(
                              gap="sm",
                              children=[
                                  dmc.Stack(
                                      gap=0,
                                      children=[
                                          dmc.Text(
                                              "Datasource Configuration",
                                              fw=600,
                                              size="lg",
                                          ),
                                          dmc.Text(
                                              "Configure your connection to"
                                              " BigQuery or Looker.",
                                              size="sm",
                                              c="dimmed",
                                          ),
                                      ],
                                  ),
                                  # BigQuery Config Card
                                  html.Div(
                                      id=AgentIds.Detail.CONTAINER_EDIT_BQ_CONFIG,
                                      style={"display": "none"},
                                      children=dmc.Paper(
                                          withBorder=True,
                                          p="lg",
                                          radius="md",
                                          bg="gray.0",
                                          children=dmc.Stack(
                                              children=[
                                                  dmc.Group(
                                                      children=[
                                                          DashIconify(
                                                              icon=(
                                                                  "bi:database"
                                                              ),
                                                              width=24,
                                                              color="orange",
                                                          ),
                                                          dmc.Text(
                                                              "BigQuery Config",
                                                              fw=600,
                                                              size="sm",
                                                          ),
                                                      ]
                                                  ),
                                                  dmc.Textarea(
                                                      label="BigQuery Tables",
                                                      description=(
                                                          "Enter full paths"
                                                          " (proj.ds.tab), one"
                                                          " per line"
                                                      ),
                                                      placeholder="project.dataset.table_1\nproject.dataset.table_2",
                                                      id=AgentIds.Detail.INPUT_EDIT_BQ_TABLES,
                                                      radius="md",
                                                      minRows=3,
                                                      autosize=True,
                                                  ),
                                                  dmc.Group(
                                                      id=AgentIds.Detail.INPUT_EDIT_BQ_TABLES_PREVIEW,
                                                      gap="xs",
                                                      mt="xs",
                                                  ),
                                              ]
                                          ),
                                      ),
                                  ),
                                  # Looker Config Card
                                  # We wrap this in a div to control
                                  # visibility via callback
                                  html.Div(
                                      id=AgentIds.Detail.CONTAINER_EDIT_LOOKER_CONFIG,
                                      style={"display": "none"},
                                      children=dmc.Paper(
                                          withBorder=True,
                                          p="lg",
                                          radius="md",
                                          bg="gray.0",  # Light gray background
                                          children=dmc.Stack(
                                              children=[
                                                  dmc.Group(
                                                      children=[
                                                          DashIconify(
                                                              icon="material-symbols:analytics",
                                                              width=24,
                                                              color="blue",
                                                          ),
                                                          dmc.Text(
                                                              "Looker"
                                                              " Configuration",
                                                              fw=600,
                                                              size="sm",
                                                          ),
                                                      ]
                                                  ),
                                                  dmc.TextInput(
                                                      label="Looker URI",
                                                      placeholder="https://your-looker.com",
                                                      id=AgentIds.Detail.INPUT_EDIT_LOOKER_URI,
                                                      radius="md",
                                                  ),
                                                  dmc.Textarea(
                                                      label="Looker Explores",
                                                      description=(
                                                          "e.g., model.exp, one"
                                                          " per line"
                                                      ),
                                                      placeholder="model_1.explore_1\nmodel_2.explore_2",
                                                      id=AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES,
                                                      radius="md",
                                                      minRows=3,
                                                      autosize=True,
                                                  ),
                                                  dmc.Group(
                                                      id=AgentIds.Detail.INPUT_EDIT_LOOKER_EXPLORES_PREVIEW,
                                                      gap="xs",
                                                      mt="xs",
                                                  ),
                                                  dmc.SimpleGrid(
                                                      cols={"base": 1, "md": 2},
                                                      spacing="lg",
                                                      children=[
                                                          dmc.TextInput(
                                                              label="Client ID",
                                                              placeholder=(
                                                                  "Enter ID"
                                                              ),
                                                              id=AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_ID,
                                                              radius="md",
                                                          ),
                                                          dmc.PasswordInput(
                                                              label=(
                                                                  "Client"
                                                                  " Secret"
                                                              ),
                                                              placeholder=(
                                                                  "Enter Secret"
                                                              ),
                                                              id=AgentIds.Detail.INPUT_EDIT_LOOKER_CLIENT_SECRET,
                                                              radius="md",
                                                          ),
                                                      ],
                                                  ),
                                                  dmc.Group(
                                                      justify="flex-end",
                                                      mt="md",
                                                      children=[
                                                          dmc.Button(
                                                              "Test Connection",
                                                              id=AgentIds.Detail.BTN_TEST_LOOKER,
                                                              variant="subtle",
                                                              size="sm",
                                                              radius="md",
                                                              leftSection=DashIconify(
                                                                  icon="material-symbols:vpn-key"
                                                              ),
                                                          ),
                                                      ],
                                                  ),
                                                  dmc.Alert(
                                                      id=AgentIds.Detail.ALERT_LOOKER_TEST,
                                                      hide=True,
                                                      radius="md",
                                                  ),
                                              ]
                                          ),
                                      ),
                                  ),
                              ],
                          ),
                          # --- Footer Actions ---
                          dmc.Group(
                              justify="flex-end",
                              mt="md",
                              children=[
                                  dmc.Button(
                                      "Save Changes",
                                      id=AgentIds.Detail.BTN_EDIT_SUBMIT,
                                      leftSection=DashIconify(
                                          icon="material-symbols:save"
                                      ),
                                      radius="md",
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          )
      ],
  )


def _duplicate_modal():
  """Returns the duplication modal."""
  return dmc.Modal(
      title="Duplicate Agent",
      id=AgentIds.Detail.MODAL_DUPLICATE,
      zIndex=10000,
      radius="md",
      padding="xl",
      children=[
          html.Div(
              style={"position": "relative"},
              children=[
                  dmc.LoadingOverlay(
                      visible=False,
                      id=AgentIds.Detail.DUPLICATE_LOADING_OVERLAY,
                      overlayProps={"blur": 2},
                  ),
                  dmc.Stack(
                      gap="lg",
                      children=[
                          dmc.Text(
                              "Create a copy of this agent. This will create a"
                              " new agent on Gemini Data Analytics with the"
                              " same configuration.",
                              size="sm",
                              c="dimmed",
                          ),
                          dmc.TextInput(
                              label="New Agent Name",
                              placeholder="e.g. Sales Assistant (Copy)",
                              id=AgentIds.Detail.INPUT_DUPLICATE_NAME,
                              required=True,
                              radius="md",
                          ),
                          dmc.Group(
                              justify="flex-end",
                              mt="md",
                              children=[
                                  dmc.Button(
                                      "Duplicate Agent",
                                      id=AgentIds.Detail.BTN_DUPLICATE_SUBMIT,
                                      leftSection=DashIconify(
                                          icon="material-symbols:content-copy"
                                      ),
                                      radius="md",
                                  ),
                              ],
                          ),
                      ],
                  ),
              ],
          )
      ],
  )


def layout(agent_id: str | None = None):  # pylint: disable=unused-argument
  """Returns the agent detail page layout."""
  return render_page(
      title="Agent Details",
      title_id=AgentIds.Detail.TITLE,
      description="Loading agent details...",
      description_id=AgentIds.Detail.DESCRIPTION,
      actions_id=AgentIds.Detail.ACTIONS,
      container_id=AgentIds.Detail.ROOT,
      breadcrumbs=dmc.Breadcrumbs(
          id=AgentIds.Detail.BREADCRUMBS,
          children=[
              dmc.Anchor("Agents", href="/agents", size="sm", fw=500),
              dmc.Text("Agent Details", size="sm", fw=500, c="dimmed"),
          ],
      ),
      children=[
          dash.dcc.Store(id=AgentIds.Detail.STORE_GCP_CONFIG),
          dash.dcc.Store(id=AgentIds.Detail.STORE_REMOTE_TRIGGER),
          dash.dcc.Store(id=AgentIds.Detail.STORE_REFRESH_TRIGGER),
          html.Div(
              style={"position": "relative"},
              children=[
                  dmc.LoadingOverlay(
                      visible=True,
                      id="agent-detail-loading",
                      zIndex=1000,
                      overlayProps={"blur": 2},
                  ),
                  html.Div(
                      id=AgentIds.Detail.CONTENT,
                      style={"minHeight": "200px"},
                  ),
              ],
          ),
          _edit_modal(),
          _duplicate_modal(),
      ],
  )


def register_page():
  dash.register_page(
      __name__, path_template="/agents/view/<agent_id>", layout=layout
  )
