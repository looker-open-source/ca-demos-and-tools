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

"""Monitoring Dashboard (Agent Management Home)."""

# pylint: disable=unused-import
import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.agent_ids import AgentIds


def _choice_modal():
  """Returns the modal for choosing between new or existing agents."""
  return dmc.Modal(
      title=None,
      id=AgentIds.Home.ChoiceModal.ROOT,
      zIndex=10000,
      centered=True,
      size=480,
      padding=32,
      radius="md",
      withCloseButton=True,
      children=[
          dmc.Stack(
              align="center",
              gap="xs",
              mb=32,
              children=[
                  dmc.Title("Choose Onboarding Type", order=3, fw=750),
                  dmc.Text(
                      "Select how you would like to proceed with your agent"
                      " setup.",
                      size="sm",
                      c="dimmed",
                      ta="center",
                  ),
              ],
          ),
          dmc.Stack(
              gap="md",
              children=[
                  # Create New Agent
                  dmc.Anchor(
                      dmc.UnstyledButton(
                          id=AgentIds.Home.ChoiceModal.BTN_CREATE,
                          w="100%",
                          children=dmc.Paper(
                              withBorder=True,
                              p="md",
                              radius="md",
                              children=dmc.Group(
                                  wrap="nowrap",
                                  justify="space-between",
                                  children=[
                                      dmc.Group(
                                          wrap="nowrap",
                                          children=[
                                              dmc.ThemeIcon(
                                                  DashIconify(
                                                      icon=(
                                                          "bi:plus-circle-fill"
                                                      ),
                                                      width=24,
                                                  ),
                                                  size=48,
                                                  radius="md",
                                                  color="blue",
                                                  variant="light",
                                              ),
                                              dmc.Stack(
                                                  gap=0,
                                                  children=[
                                                      dmc.Text(
                                                          "Create New Agent",
                                                          fw=700,
                                                          size="md",
                                                      ),
                                                      dmc.Text(
                                                          "Start fresh with new"
                                                          " configuration",
                                                          size="xs",
                                                          c="dimmed",
                                                      ),
                                                  ],
                                              ),
                                          ],
                                      ),
                                      DashIconify(
                                          icon="bi:arrow-right",
                                          width=18,
                                          color="var(--mantine-color-gray-4)",
                                      ),
                                  ],
                              ),
                          ),
                      ),
                      href="/agents/onboard/new",
                      underline=False,
                  ),
                  # Monitor Existing
                  dmc.Anchor(
                      dmc.UnstyledButton(
                          id=AgentIds.Home.ChoiceModal.BTN_EXISTING,
                          w="100%",
                          children=dmc.Paper(
                              withBorder=True,
                              p="md",
                              radius="md",
                              children=dmc.Group(
                                  wrap="nowrap",
                                  justify="space-between",
                                  children=[
                                      dmc.Group(
                                          wrap="nowrap",
                                          children=[
                                              dmc.ThemeIcon(
                                                  DashIconify(
                                                      icon="bi:robot",
                                                      width=24,
                                                  ),
                                                  size=48,
                                                  radius="md",
                                                  color="blue",
                                                  variant="light",
                                              ),
                                              dmc.Stack(
                                                  gap=0,
                                                  children=[
                                                      dmc.Text(
                                                          "Monitor Existing"
                                                          " Agents",
                                                          fw=700,
                                                          size="md",
                                                      ),
                                                      dmc.Text(
                                                          "Connect to already"
                                                          " active agents",
                                                          size="xs",
                                                          c="dimmed",
                                                      ),
                                                  ],
                                              ),
                                          ],
                                      ),
                                      DashIconify(
                                          icon="bi:arrow-right",
                                          width=18,
                                          color="var(--mantine-color-gray-4)",
                                      ),
                                  ],
                              ),
                          ),
                      ),
                      href="/agents/onboard/existing",
                      underline=False,
                  ),
              ],
          ),
          dmc.Center(
              mt="xl",
              children=dmc.Button(
                  "Cancel",
                  variant="subtle",
                  color="gray",
                  size="xs",
                  id=AgentIds.Home.ChoiceModal.BTN_CANCEL,
              ),
          ),
      ],
  )


def layout():
  """Returns the monitoring dashboard layout."""
  return render_page(
      title="Monitored Agents",
      description=(
          "Manage, configure, and monitor your conversational AI fleet."
      ),
      actions=[
          dmc.Button(
              "Onboard New Agent",
              leftSection=DashIconify(icon="bi:plus-lg"),
              id=AgentIds.Home.BTN_MONITOR,
              radius="md",
          ),
      ],
      children=[
          dmc.Group(
              justify="flex-end",
              mb="md",
              children=[
                  dmc.Switch(
                      id=AgentIds.Home.SWITCH_ARCHIVED,
                      label="Show Archived",
                      size="sm",
                      radius="md",
                      checked=False,
                  ),
              ],
          ),
          dmc.Paper(
              id=AgentIds.Home.CARD_GRID,
              withBorder=True,
              radius="md",
              p=0,
              shadow="none",
              bg="white",
              w="100%",
              style={"overflow": "hidden"},
          ),
          _choice_modal(),
      ],
  )


def register_page():
  dash.register_page(
      __name__, path="/agents", title="Prism | Agents", layout=layout
  )
