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

"""Presentational components for the application shell."""

from dash_iconify import DashIconify
import dash_mantine_components as dmc


def _header_link(label: str, href: str, link_id: str = None):
  """Renders a single navigation link for the header."""
  return dmc.Anchor(
      label,
      href=href,
      id=link_id,
      underline=False,
      size="sm",
      fw=500,
      c="black",
      style={
          "&:hover": {"color": "black"},
      },
      px="sm",
  )


def render_header():
  """Renders the global header with top navigation."""
  return dmc.AppShellHeader(
      px="md",
      children=[
          dmc.Group(
              justify="space-between",
              h="100%",
              children=[
                  # Left: Brand
                  dmc.Anchor(
                      href="/",
                      underline=False,
                      style={"textDecoration": "none", "color": "inherit"},
                      children=[
                          dmc.Group(
                              gap="sm",
                              children=[
                                  dmc.ThemeIcon(
                                      variant="light",
                                      color="blue",
                                      size="lg",
                                      radius="md",
                                      children=DashIconify(
                                          icon="bi:bar-chart-fill", width=20
                                      ),
                                  ),
                                  dmc.Text(
                                      "Prism",
                                      fw=700,
                                      size="md",
                                      lh=1,
                                  ),
                              ],
                          ),
                      ],
                  ),
                  # Right: Navigation
                  dmc.Group(
                      gap="sm",
                      children=[
                          _header_link("Overview", "/", link_id="nav-overview"),
                          _header_link(
                              "Agents", "/agents", link_id="nav-agents"
                          ),
                          _header_link(
                              "Test Suites",
                              "/test_suites",
                              link_id="nav-test-suites",
                          ),
                          _header_link(
                              "Evaluations",
                              "/evaluations",
                              link_id="nav-evaluations",
                          ),
                          _header_link(
                              "Compare",
                              "/compare",
                              link_id="nav-comparison",
                          ),
                      ],
                  ),
              ],
          )
      ],
  )
