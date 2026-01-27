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

"""Home page layout."""

import dash
from dash import dcc
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.home_ids import HomeIds


def layout():
  return render_page(
      title="Welcome back",
      description=(
          "Prism provides a comprehensive toolkit for evaluating and monitoring"
          " Gemini Data Analytics agents."
      ),
      actions=[
          dmc.Anchor(
              dmc.Button(
                  "Getting Started",
                  leftSection=DashIconify(icon="bi:info-circle"),
                  variant="light",
                  radius="md",
              ),
              href="/getting-started",
              underline=False,
          )
      ],
      children=[
          dcc.Interval(
              id=HomeIds.INTERVAL, interval=30000, n_intervals=0
          ),  # Refresh every 30s
          # Hero: Getting Started
          dmc.Alert(
              title="New to Prism?",
              children=[
                  dmc.Group(
                      [
                          dmc.Text(
                              "Check out our comprehensive Getting Started"
                              " guide to learn the ropes of Agent Evaluation.",
                              size="sm",
                          ),
                          dmc.Anchor(
                              dmc.Button(
                                  "Go to Guide",
                                  variant="white",
                                  color="indigo",
                                  size="xs",
                                  leftSection=DashIconify(
                                      icon="bi:arrow-right-circle"
                                  ),
                              ),
                              href="/getting-started",
                              underline=False,
                          ),
                      ],
                      justify="space-between",
                      align="center",
                  )
              ],
              color="indigo",
              variant="filled",
              radius="md",
              withCloseButton=True,
              mb="xl",
              icon=DashIconify(icon="bi:stars", width=24),
              id=HomeIds.GETTING_STARTED_CARD,
          ),
          # Charts Grid
          dmc.Grid(
              children=[
                  dmc.GridCol(
                      children=[
                          html.Div(
                              id=HomeIds.CHART_CONTAINER,
                              style={"minHeight": "400px"},
                          )
                      ],
                      span={"base": 12, "lg": 6},
                  ),
                  dmc.GridCol(
                      children=[
                          html.Div(
                              id=HomeIds.VOLUME_CHART_CONTAINER,
                              style={"minHeight": "400px"},
                          )
                      ],
                      span={"base": 12, "lg": 6},
                  ),
              ],
              gutter="md",
              mb="xl",
          ),
          # Recent Runs
          html.Div(
              children=[
                  dmc.Group(
                      [
                          dmc.Title("Recent Evaluation Runs", order=4),
                          dmc.Anchor(
                              "View all history", href="/evaluations", size="sm"
                          ),
                      ],
                      justify="space-between",
                      mb="md",
                  ),
                  dmc.Paper(
                      children=[html.Div(id=HomeIds.RECENT_RUNS_CONTAINER)],
                      p=0,
                      withBorder=True,
                      radius="md",
                      shadow="sm",
                      style={"overflow": "hidden"},
                  ),
              ]
          ),
      ],
  )


def register_page():
  dash.register_page(__name__, path="/", layout=layout)
