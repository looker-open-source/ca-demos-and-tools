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

"""Reusable component for rendering the Asserts Guide."""

from dash import dcc
from dash import html
import dash_mantine_components as dmc
from prism.ui.constants import ASSERTS_GUIDE


def render_asserts_guide(guide_data=None):
  """Renders the list of assert descriptions."""
  if guide_data is None:
    guide_data = ASSERTS_GUIDE

  return html.Div([
      html.Div(
          [
              dmc.Text(
                  item["label"],
                  fw=700,
                  size="sm",
              ),
              dmc.Text(item["description"], size="sm", mb="xs"),
          ],
          className="mb-4",
      )
      for item in guide_data
  ])


def render_asserts_guide_accordion():
  """Renders the Asserts Guide inside a collapsible Accordion."""
  return dmc.Accordion(
      children=[
          dmc.AccordionItem(
              [
                  dmc.AccordionControl("Assertion Help Guide"),
                  dmc.AccordionPanel(
                      html.Div(
                          render_asserts_guide(),
                          style={"maxHeight": "70vh", "overflowY": "auto"},
                      )
                  ),
              ],
              value="asserts-guide",
          )
      ],
      className="mt-3",
  )
