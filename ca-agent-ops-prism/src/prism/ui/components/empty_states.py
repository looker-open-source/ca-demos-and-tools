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

"""Reusable empty state components."""

from dash_iconify import DashIconify
import dash_mantine_components as dmc


def render_empty_state(
    title: str,
    description: str,
    button_label: str | None = None,
    href: str | None = None,
    icon: str = "bi:inbox",
):
  """Renders a centered empty state card."""
  children = [
      dmc.ThemeIcon(
          variant="light",
          color="gray",
          size=60,
          radius="md",
          children=DashIconify(icon=icon, width=30),
          mb="md",
      ),
      dmc.Title(title, order=3, fw=600, mb="sm"),
      dmc.Text(description, c="dimmed", size="md", mb="xl", maw=500),
  ]

  if button_label and href:
    children.append(
        dmc.Anchor(
            dmc.Button(
                button_label,
                leftSection=DashIconify(icon="bi:plus-lg"),
                size="md",
            ),
            href=href,
            underline=False,
        )
    )

  return dmc.Center(
      style={"height": "60vh", "gridColumn": "1 / -1"},
      children=[
          dmc.Paper(
              withBorder=True,
              radius="md",
              shadow="none",
              p="xl",
              children=dmc.Stack(
                  align="center",
                  justify="center",
                  children=children,
              ),
          )
      ],
  )
