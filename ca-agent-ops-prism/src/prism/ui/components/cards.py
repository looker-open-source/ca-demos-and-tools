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

"""Reusable card components for detail pages."""

from typing import Any

from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc


def render_detail_card(
    title: str,
    icon: str | None = None,
    children: Any = None,
    description: str | None = None,
    action: Any = None,
    card_id: str | dict[str, Any] | None = None,
    icon_color: str = "#94a3b8",
    **kwargs,
) -> dmc.Card:
  """Renders a standardized detail card with a header and content body.

  Args:
    title: The title text to display in the header.
    icon: Optional icon string (e.g., "bi:info-circle") for the header.
    children: The content to display in the card body.
    description: Optional subtitle/description text.
    action: Optional component to display on the right side of the header.
    card_id: Optional ID for the card component.
    icon_color: Optional color for the header icon.
    **kwargs: Additional arguments passed to dmc.Card.

  Returns:
    A dmc.Card component.
  """
  if card_id:
    kwargs["id"] = card_id

  header_content = dmc.Stack(
      gap=0,
      children=[
          dmc.Group(
              gap="xs",
              children=[
                  DashIconify(icon=icon, width=20, color=icon_color)
                  if icon
                  else None,
                  dmc.Text(title, fw=700, size="lg"),
              ],
          ),
          dmc.Text(description, c="dimmed", size="sm") if description else None,
      ],
  )

  return dmc.Card(
      **kwargs,
      withBorder=True,
      radius="md",
      shadow="sm",
      padding="lg",
      children=[
          dmc.CardSection(
              withBorder=False,
              inheritPadding=True,
              py="md",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          header_content,
                          action,
                      ],
                  )
              ],
          ),
          dmc.CardSection(
              inheritPadding=True,
              py="lg",
              children=children,
          ),
      ],
  )


def render_error_card(
    message: str, traceback_str: str | None = None, stage: str | None = None
) -> dmc.Card:
  """Renders a dedicated error card for failed trials.

  Args:
    message: The error message to display.
    traceback_str: Optional full stack trace.
    stage: Optional failure stage (e.g., 'EXECUTING').

  Returns:
    A dmc.Card component.
  """
  title = f"Failed during {stage}" if stage else "Trial Execution Failed"

  # Parse the message to handle escaped and real newlines
  clean_message = message.replace("\\n", "\n")
  parts = clean_message.split("\n")
  summary = parts[0]
  details = "\n".join(parts[1:]).strip() if len(parts) > 1 else None

  children = [
      dmc.Alert(
          summary,
          title="Error Summary",
          color="red",
          variant="light",
          radius="md",
          icon=DashIconify(icon="bi:exclamation-triangle-fill"),
          mb="md" if details or traceback_str else 0,
      )
  ]

  if details:
    children.append(
        dmc.Stack(
            gap=4,
            children=[
                dmc.Text("Details", fw=600, size="sm", c="red.9"),
                dmc.Code(
                    details,
                    block=True,
                    fz="xs",
                    color="red.0",
                    p="xs",
                    style={
                        "border": "1px solid var(--mantine-color-red-1)",
                        "color": "var(--mantine-color-red-9)",
                    },
                ),
            ],
            mb="md" if traceback_str else 0,
        )
    )

  if traceback_str:
    children.append(
        dmc.Accordion(
            variant="separated",
            radius="md",
            children=[
                dmc.AccordionItem(
                    [
                        dmc.AccordionControl(
                            "View Full Stack Trace",
                            icon=DashIconify(
                                icon="bi:bug",
                                color="var(--mantine-color-red-6)",
                            ),
                        ),
                        dmc.AccordionPanel(
                            dmc.ScrollArea(
                                h=300,
                                children=dmc.Code(
                                    traceback_str,
                                    block=True,
                                    fz="xs",
                                    color="gray.1",
                                ),
                            )
                        ),
                    ],
                    value="traceback",
                )
            ],
        )
    )

  return render_detail_card(
      title=title.upper(),
      icon="bi:x-circle",
      children=dmc.Stack(children, gap=0),
      className="error-card",
      style={"border": "1px solid var(--mantine-color-red-2)"},
  )


def render_stat_card(
    title: str,
    value: str,
    icon: str,
    color: str = "blue",
    value_href: str | None = None,
    sub_buttons: list[dict[str, Any]] | None = None,
) -> dmc.Paper:
  """Renders a standardized stat card for overview metrics.

  Args:
    title: The title of the stat (e.g., 'Avg Accuracy').
    value: The main value to display (e.g., '95.5%').
    icon: The icon to display.
    color: The color theme for the icon and accent.
    value_href: Optional URL to make the value clickable.
    sub_buttons: Optional list of dictionaries with 'label', 'href', and
      optional 'id' and 'variant' for buttons at the bottom.

  Returns:
    A dmc.Paper component.
  """
  buttons = []
  if sub_buttons:
    for btn in sub_buttons:
      button_kwargs = {
          "variant": btn.get("variant", "default"),
          "radius": "md",
          "fw": 600,
          "size": "xs",
      }
      if "id" in btn:
        button_kwargs["id"] = btn["id"]

      button_comp = dmc.Button(btn["label"], **button_kwargs)
      if btn.get("href"):
        buttons.append(dmc.Anchor(button_comp, href=btn["href"]))
      else:
        buttons.append(button_comp)

  if value_href:
    value_display = dmc.Anchor(
        dmc.Box(
            value,
            style={
                "padding": "4px 8px",
                "borderRadius": "var(--mantine-radius-md)",
                "backgroundColor": "var(--mantine-color-gray-0)",
                "border": "1px solid var(--mantine-color-gray-2)",
                "display": "inline-block",
                "cursor": "pointer",
                "transition": (
                    "background-color 0.2s ease, border-color 0.2s ease"
                ),
                "&:hover": {
                    "backgroundColor": "var(--mantine-color-gray-1)",
                    "borderColor": "var(--mantine-color-gray-3)",
                },
            },
            fw=700,
            className="hover:bg-gray-100 transition-colors",
        ),
        href=value_href,
        underline=False,
        c="dark",
    )
  else:
    value_display = dmc.Text(
        value,
        fw=700,
        size="xl",
        c="dark",
        truncate="end",
    )

  return dmc.Paper(
      p="md",
      radius="md",
      withBorder=True,
      children=[
          dmc.Group(
              [
                  dmc.ThemeIcon(
                      DashIconify(
                          icon=icon,
                          width=18,
                      ),
                      variant="light",
                      color=color,
                      size="md",
                      radius="md",
                  ),
                  dmc.Text(
                      title,
                      c="dimmed",
                      size="xs",
                      tt="uppercase",
                      fw=700,
                  ),
              ],
              gap="xs",
              mb="xs",
          ),
          value_display,
          (
              dmc.Group(gap="xs", mt="sm", children=buttons)
              if buttons
              else html.Div()
          ),
      ],
  )
