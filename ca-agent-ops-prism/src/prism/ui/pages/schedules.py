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

"""Scheduled Evaluations management page."""

import dash
from dash import dcc
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components import schedule_components
from prism.ui.components.page_layout import render_page
from prism.ui.ids import ScheduleIds as Ids

_STATUS_FILTER_OPTIONS = [
    {"label": "Active", "value": "active"},
    {"label": "Paused", "value": "paused"},
]


def layout(**_kwargs):
  return render_page(
      title="Schedules",
      description=(
          "Configure recurring evaluations across your agents and test suites."
      ),
      actions=[
          dmc.Button(
              "New Schedule",
              # A pattern id because the create callback also lives on the
              # detail page's modal, which has no New Schedule button. Dash
              # treats a missing ALL match as empty, not as a missing input.
              id={"type": Ids.BTN_OPEN_CREATE, "index": "header"},
              leftSection=DashIconify(icon="bi:plus-lg", width=16),
              radius="md",
          ),
      ],
      children=[
          dcc.Interval(id=Ids.POLL_INTERVAL, interval=5000, n_intervals=0),
          dcc.Store(id=Ids.UPDATE_SIGNAL),
          dmc.Stack(
              gap="lg",
              children=[
                  html.Div(id=Ids.KPI_CONTAINER),
                  dmc.Group(
                      justify="space-between",
                      gap="md",
                      wrap="wrap",
                      children=[
                          dmc.Group(
                              gap="md",
                              wrap="wrap",
                              children=[
                                  dmc.Select(
                                      id=Ids.FILTER_AGENT,
                                      label="Filter by Agent",
                                      placeholder="All Agents",
                                      data=[],
                                      clearable=True,
                                      style={"width": 240},
                                  ),
                                  dmc.Select(
                                      id=Ids.FILTER_SUITE,
                                      label="Filter by Test Suite",
                                      placeholder="All Test Suites",
                                      data=[],
                                      clearable=True,
                                      style={"width": 240},
                                  ),
                                  dmc.Select(
                                      id=Ids.FILTER_STATUS,
                                      label="Filter by Status",
                                      placeholder="All Statuses",
                                      data=_STATUS_FILTER_OPTIONS,
                                      clearable=True,
                                      style={"width": 180},
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
                  ),
                  html.Div(
                      id=Ids.LIST_CONTAINER,
                      children=[
                          dmc.Center(
                              children=[dmc.Loader(variant="dots")],
                              py="xl",
                          )
                      ],
                  ),
              ],
          ),
          schedule_components.render_schedule_modal(),
      ],
  )


def register_page():
  dash.register_page(
      __name__, path="/schedules", title="Prism | Schedules", layout=layout
  )
