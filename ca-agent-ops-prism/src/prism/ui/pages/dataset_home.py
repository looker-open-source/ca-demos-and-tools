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

"""Datasets dashboard page."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.pages.dataset_ids import DatasetHomeIds


def layout():
  """Renders the Datasets dashboard layout."""
  return render_page(
      title="Test Suites",
      description=(
          "Create and manage standardized test suites to evaluate agent"
          " performance across different scenarios."
      ),
      actions=[
          dmc.Anchor(
              dmc.Button(
                  "Create Test Suite",
                  leftSection=DashIconify(icon="bi:plus-lg"),
                  radius="md",
              ),
              href="/test_suites/new",
              underline=False,
          ),
      ],
      children=[
          dmc.Group(
              children=[
                  dmc.Select(
                      id=DatasetHomeIds.FILTER_COVERAGE,
                      label="Filter by Coverage",
                      placeholder="All Coverage",
                      data=[
                          {"label": "Full Coverage", "value": "FULL"},
                          {"label": "Partial Coverage", "value": "PARTIAL"},
                          {"label": "No Coverage", "value": "NONE"},
                      ],
                      clearable=True,
                      style={"width": 200},
                  ),
              ],
              gap="md",
              mb="lg",
          ),
          html.Div(
              style={"position": "relative"},
              children=[
                  dmc.LoadingOverlay(
                      visible=False,
                      id=DatasetHomeIds.LOADING,
                      overlayProps={"blur": 2},
                  ),
                  dmc.Paper(
                      id=DatasetHomeIds.DATASETS_LIST,
                      withBorder=True,
                      radius="md",
                      p=0,
                      shadow="none",
                      bg="white",
                      w="100%",
                      style={"overflow": "hidden"},
                  ),
              ],
          ),
          # Hidden div for redirect
          html.Div(id="datasets-redirect-div"),
      ],
  )


def register_page():
  dash.register_page(
      __name__, path="/test_suites", title="Prism | Test Suites", layout=layout
  )
