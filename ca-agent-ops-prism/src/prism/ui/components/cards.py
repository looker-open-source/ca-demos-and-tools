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


def error_summary_line(message: str) -> str:
  r"""The one line of a stored error message that may go on a page.

  Everything after the first line used to be rendered in a Details block, and
  that block is what a writer who forgets to sanitise leaks through. The first
  line is what the services compose on purpose, and it ends with the reference
  id that finds the rest in the server log.

  The services store the newline escaped, so a multi-line error arrives as
  one line with a literal \n in it.
  """
  return (message or "").replace("\\n", "\n").split("\n")[0].strip()


def render_error_card(
    message: str, traceback_str: str | None = None, stage: str | None = None
) -> dmc.Card:
  """Renders a dedicated error card for failed trials.

  The traceback is never rendered. prism has no authentication, so this page
  is readable by anyone who can reach the port and it goes into the
  screenshots attached to bugs, and a stored traceback carries the container's
  filesystem layout and the installed library versions. The message the
  services store now ends with a reference id that finds the traceback in the
  server log.

  Args:
    message: The stored error message. Only its first line is rendered. See
      error_summary_line.
    traceback_str: Accepted and ignored. The call site still passes what is on
      the trial row, and trials that failed before this changed still have a
      trace stored there.
    stage: Optional failure stage (e.g., 'EXECUTING').

  Returns:
    A dmc.Card component.
  """
  del traceback_str  # Not rendered. See above.
  title = f"Failed during {stage}" if stage else "Trial Execution Failed"

  children = [
      dmc.Alert(
          error_summary_line(message),
          title="Error Summary",
          color="red",
          variant="light",
          radius="md",
          icon=DashIconify(icon="bi:exclamation-triangle-fill"),
          mb="md",
      )
  ]

  children.append(
      dmc.Text(
          "The full details, including the traceback, are in the server log.",
          size="xs",
          c="dimmed",
      )
  )

  return render_detail_card(
      title=title.upper(),
      icon="bi:x-circle",
      children=dmc.Stack(children, gap=0),
      # The red border is the style below. There used to be a
      # className="error-card" here as well, and no stylesheet in the app
      # defines that class, so it styled nothing.
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
