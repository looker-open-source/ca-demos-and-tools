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

"""Page for creating a new test suite."""

import dash
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
from prism.ui.components.page_layout import render_page
from prism.ui.ids import TestSuiteIds as Ids


def layout():
  """Renders the Create New Test Suite layout."""
  return render_page(
      title="Create New Test Suite",
      description="Configure the initial details for your new test suite.",
      breadcrumbs=dmc.Breadcrumbs(
          separator="/",
          children=[
              dmc.Anchor(
                  "Test Suites",
                  href="/test_suites",
                  size="sm",
                  fw=500,
              ),
              dmc.Text("New Test Suite", size="sm", fw=500, c="dimmed"),
          ],
      ),
      actions=[
          dmc.Anchor(
              dmc.Button(
                  "Cancel",
                  id=Ids.CANCEL_NEW_BTN,
                  variant="subtle",
                  color="gray",
                  fw=500,
              ),
              href="/test_suites",
              underline=False,
          ),
          dmc.Button(
              "Save & Continue",
              id=Ids.SAVE_NEW_BTN,
              leftSection=DashIconify(icon="bi:arrow-right", width=18),
              radius="md",
              size="md",
              className="shadow-md shadow-indigo-500/20",
          ),
      ],
      children=[
          # Main Content Card
          dmc.Paper(
              radius="md",
              withBorder=True,
              className="max-w-[1000px] mx-auto overflow-hidden",
              children=[
                  # Section 1: Configuration
                  dmc.Stack(
                      p=40,
                      gap="xl",
                      style={
                          "borderBottom": (
                              "1px solid var(--mantine-color-gray-3)"
                          )
                      },
                      children=[
                          dmc.Text("Configuration", fw=700, size="lg"),
                          dmc.TextInput(
                              id=Ids.NAME,
                              label="Test Suite Name",
                              placeholder="e.g., Marketing Q4 Evaluation",
                              required=True,
                              size="md",
                          ),
                          dmc.Textarea(
                              id=Ids.DESC,
                              label="Description",
                              placeholder="What is this test suite for?",
                              minRows=4,
                              size="md",
                          ),
                      ],
                  ),
              ],
          ),
          # Hidden stores & placeholders
          dash.dcc.Store(id=Ids.STORE_BUILDER, data=[]),
          dash.dcc.Store(id=Ids.STORE_MODAL, data={}),
          html.Div(id=Ids.SAVE_EDIT_BTN, style={"display": "none"}),
          html.Div(id=Ids.CANCEL_EDIT_BTN, style={"display": "none"}),
          html.Div(id=Ids.PLACEHOLDER_SAVE_BTN, style={"display": "none"}),
      ],
  )


def register_page():
  dash.register_page(
      __name__,
      path="/test_suites/new",
      title="Prism | New Test Suite",
      layout=layout,
  )
