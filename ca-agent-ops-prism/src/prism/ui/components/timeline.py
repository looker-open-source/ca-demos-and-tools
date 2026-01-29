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

"""Components for rendering execution timelines."""

import json
from typing import Any, Dict, List, Optional

from dash import dcc
from dash import html
from dash_iconify import DashIconify
import dash_mantine_components as dmc
import dash_vega_components as dvc


def render_timeline(
    timeline_data: Dict[str, Any], raw_payload: Optional[List[Any]] = None
):
  """Renders the visual timeline component from a Timeline DTO.

  Args:
    timeline_data: A dictionary containing timeline events and metadata.
    raw_payload: Optional raw trace payload for the copy-to-clipboard button.

  Returns:
    A Dash layout component for the timeline.
  """

  if not timeline_data or not timeline_data.get("events"):
    return dmc.Alert(
        "No trace data available for this trial.",
        color="orange",
        variant="light",
    )

  total_duration = timeline_data.get("total_duration_ms", 0)

  accordion_items = []
  for i, event in enumerate(timeline_data["events"]):
    content_type = event.get("content_type", "text")
    item_value = f"event-{i}"

    if content_type == "text":
      content_display = dmc.Blockquote(event["content"], color="gray", mt="sm")
    elif content_type in ["json", "code", "sql"]:
      content_display = dmc.Code(
          event["content"],
          block=True,
          mt="sm",
          style={"whiteSpace": "pre-wrap"},
      )
    elif content_type == "vegalite":
      try:
        spec = (
            json.loads(event["content"])
            if isinstance(event["content"], str)
            else event["content"]
        )
        if isinstance(spec, dict):
          spec["width"] = "container"
          spec["autosize"] = {"type": "fit", "contains": "padding"}

        content_display = dvc.Vega(
            spec=spec,
            opt={"renderer": "svg", "actions": False},
            style={"width": "100%", "marginTop": "10px"},
        )
      except Exception:  # pylint: disable=broad-exception-caught
        content_display = dmc.Code(
            event["content"],
            block=True,
            mt="sm",
            style={"whiteSpace": "pre-wrap"},
            color="red",
        )
    else:
      # Fallback
      content_display = dmc.Text(event["content"])

    # Calculate progress bar values
    if total_duration > 0:
      step_duration_pct = (event.get("duration_ms", 0) / total_duration) * 100
      prev_duration_pct = (
          (event.get("cumulative_duration_ms", 0) - event.get("duration_ms", 0))
          / total_duration
      ) * 100
    else:
      step_duration_pct = 0
      prev_duration_pct = 0

    # Cap at 100% just in case
    if step_duration_pct + prev_duration_pct > 100:
      step_duration_pct = max(0, 100 - prev_duration_pct)

    progress_bar = dmc.ProgressRoot(
        size=6,
        children=[
            dmc.ProgressSection(
                value=prev_duration_pct,
                color="gray.2",
            ),
            dmc.ProgressSection(
                value=step_duration_pct,
                color="blue.6",
                style={"borderRadius": "var(--mantine-radius-md)"},
            ),
        ],
        style={"backgroundColor": "var(--mantine-color-gray-1)"},
    )

    accordion_items.append(
        dmc.AccordionItem(
            [
                dmc.AccordionControl(
                    html.Div(
                        [
                            dmc.Group(
                                justify="space-between",
                                mb="xs",
                                children=[
                                    dmc.Group([
                                        dmc.ThemeIcon(
                                            DashIconify(
                                                icon=event.get(
                                                    "icon", "bi:circle"
                                                ),
                                                width=20,
                                            ),
                                            size="lg",
                                            radius="md",
                                            variant="light",
                                            color="blue",
                                        ),
                                        dmc.Text(
                                            event["title"], fw=600, size="sm"
                                        ),
                                    ]),
                                    dmc.Text(
                                        f"+{event.get('duration_ms', 0)}ms",
                                        c="dimmed",
                                        size="xs",
                                    ),
                                ],
                            ),
                            progress_bar,
                        ],
                    )
                ),
                dmc.AccordionPanel(content_display),
            ],
            value=item_value,
        )
    )

  if raw_payload:
    copy_button = dmc.Tooltip(
        label="Copy Full Trace",
        children=dcc.Clipboard(
            content=json.dumps(raw_payload, indent=2),
            className="button is-small",
            style={
                "display": "inline-block",
                "verticalAlign": "middle",
                "marginLeft": "10px",
                "cursor": "pointer",
            },
        ),
    )
  else:
    copy_button = html.Div()

  return html.Div([
      dmc.Group(
          [
              dmc.Group(
                  [
                      copy_button,
                      dmc.Tooltip(
                          label="Expand All",
                          children=dmc.ActionIcon(
                              DashIconify(icon="bi:arrows-expand"),
                              id="expand-all-button",
                              variant="transparent",
                              color="gray",
                          ),
                      ),
                      dmc.Tooltip(
                          label="Collapse All",
                          children=dmc.ActionIcon(
                              DashIconify(icon="bi:arrows-collapse"),
                              id="collapse-all-button",
                              variant="transparent",
                              color="gray",
                          ),
                      ),
                  ],
                  gap="xs",
              ),
          ],
          justify="flex-end",
          mb="xs",
      ),
      dmc.Accordion(
          id="timeline-accordion",
          multiple=True,
          children=accordion_items,
          value=[],  # Start collapsed
          variant="separated",
          radius="md",
      ),
  ])


def render_trace_timeline(timeline_data: Dict[str, Any]):
  """Renders a vertical trace timeline matching the mockup.

  Args:
    timeline_data: Timeline DTO as a dict.

  Returns:
    A Dash component.
  """
  if not timeline_data or not timeline_data.get("events"):
    return dmc.Alert(
        "No execution trace available.",
        color="gray",
        variant="light",
    )

  total_duration = timeline_data.get("total_duration_ms", 0)
  timeline_items = []
  for event in timeline_data["events"]:
    timestamp = event.get("cumulative_duration_ms", 0) / 1000
    timestamp_str = f"+{timestamp:.1f}s"

    title_row = dmc.Group(
        justify="space-between",
        children=[
            dmc.Text(event["title"], fw=700, size="sm"),
            dmc.Badge(
                timestamp_str,
                variant="light",
                color="gray",
                size="sm",
                radius="sm",
                tt="none",
            ),
        ],
    )

    # Progress bar calculation
    if total_duration > 0:
      duration_ms = event.get("duration_ms", 0)
      cum_duration_ms = event.get("cumulative_duration_ms", 0)
      prev_pct = max(0, (cum_duration_ms - duration_ms) / total_duration * 100)
      curr_pct = max(0, duration_ms / total_duration * 100)
    else:
      prev_pct = 0
      curr_pct = 0

    # Ensure cumulative + current does not exceed 100% due to rounding
    if prev_pct + curr_pct > 100:
      curr_pct = 100 - prev_pct

    progress_bar = dmc.ProgressRoot(
        children=[
            dmc.ProgressSection(
                value=prev_pct,
                color="transparent",
            ),
            dmc.ProgressSection(
                value=curr_pct,
                color="blue.6",
                style={"borderRadius": "var(--mantine-radius-md)"},
            ),
        ],
        size=6,
        mb="sm",
        style={"backgroundColor": "var(--mantine-color-gray-2)"},
    )

    content_type = event.get("content_type", "text")
    content = event.get("content", "")

    # Custom rendering based on content and type
    if event["title"] in ["Test Case", "Final Response", "Agent Thought"]:
      content_box = dmc.Paper(
          p="md",
          radius="md",
          withBorder=True,
          children=dmc.Text(
              content,
              size="sm",
              fs="italic" if event["title"] == "Agent Thought" else None,
          ),
          bg="var(--mantine-color-blue-0)"
          if event["title"] == "Final Response"
          else "var(--mantine-color-gray-0)",
          style={"border": "1px solid var(--mantine-color-blue-1)"}
          if event["title"] == "Final Response"
          else {},
      )
    elif content_type == "json":
      try:
        # Try to parse and re-format if it's already a string.
        if isinstance(content, str):
          json_obj = json.loads(content)
          content = json.dumps(json_obj, indent=2)
      except Exception:  # pylint: disable=broad-exception-caught
        pass

      content_box = dmc.Accordion(
          variant="contained",
          radius="md",
          children=[
              dmc.AccordionItem(
                  [
                      dmc.AccordionControl(
                          dmc.Text("Details", size="sm", fw=500),
                      ),
                      dmc.AccordionPanel(
                          dmc.Code(
                              content,
                              block=True,
                              fz="xs",
                              style={"whiteSpace": "pre-wrap"},
                          )
                      ),
                  ],
                  value="details",
              )
          ],
      )
    elif content_type == "vegalite":
      try:
        spec = json.loads(content) if isinstance(content, str) else content
        if isinstance(spec, dict):
          spec["width"] = "container"
          spec["autosize"] = {"type": "fit", "contains": "padding"}

        content_box = dmc.Paper(
            p="md",
            radius="md",
            withBorder=True,
            children=dvc.Vega(
                spec=spec,
                opt={"renderer": "svg", "actions": False},
                style={"width": "100%"},
            ),
        )
      except Exception:  # pylint: disable=broad-exception-caught
        content_box = dmc.Code(
            content,
            block=True,
            fz="xs",
            style={"whiteSpace": "pre-wrap"},
            color="red",
        )
    elif content_type in ["sql", "python", "code"]:
      content_box = dmc.Code(
          content,
          block=True,
          fz="xs",
          style={"whiteSpace": "pre-wrap"},
          color="gray",
      )
    else:
      content_box = dmc.Text(content, size="sm")

    # Determine bullet color/icon
    bullet_icon = event.get("icon", "bi:circle")

    # Map colors to match mockup more closely
    icon_color = "gray"
    if "database" in bullet_icon:
      icon_color = "blue"
    elif "chat" in bullet_icon:
      icon_color = "green"
    elif "lightbulb" in bullet_icon or "psychology" in bullet_icon:
      icon_color = "violet"
    elif "exclamation" in bullet_icon:
      icon_color = "red"
    elif "person" in bullet_icon:
      icon_color = "gray"

    timeline_items.append(
        dmc.TimelineItem(
            title=title_row,
            bullet=dmc.ThemeIcon(
                DashIconify(icon=bullet_icon, width=18),
                size=32,
                radius="md",
                variant="light",
                color=icon_color,
            ),
            children=html.Div(
                [progress_bar, content_box],
                style={"marginTop": 8},
            ),
        )
    )

  return dmc.Timeline(
      active=-1,  # Prevent primary color highlighting of the spine
      bulletSize=32,
      lineWidth=3,
      children=timeline_items,
      color="gray",
      styles={
          "itemBullet": {
              "backgroundColor": "white",
              "border": "none",
              "boxShadow": "none",
          }
      },
  )


def render_chart_carousel(timeline_data: Dict[str, Any], minimal: bool = False):
  """Renders a carousel of agent-generated charts.

  Args:
    timeline_data: Timeline DTO as a dict.
    minimal: If True, returns only the carousel/content without card wrapper.

  Returns:
    A Dash component or None if no charts exist.
  """
  charts = [
      e
      for e in timeline_data.get("events", [])
      if e.get("content_type") == "vegalite"
  ]
  if not charts:
    return None

  slides = []
  for i, event in enumerate(charts):
    content = event.get("content", "")
    try:
      spec = json.loads(content) if isinstance(content, str) else content
      if isinstance(spec, dict):
        spec["width"] = "container"
        spec["height"] = 350
        spec["autosize"] = {"type": "fit", "contains": "padding"}

      slides.append(
          dmc.CarouselSlide(
              dmc.Stack(
                  [
                      dmc.Text(
                          f"CHART {i + 1} OF {len(charts)}",
                          fw=700,
                          size="xs",
                          ta="center",
                          c="dimmed",
                          lts="0.05em",
                      ),
                      dvc.Vega(
                          spec=spec,
                          opt={"renderer": "svg", "actions": False},
                          style={"width": "100%", "height": "350px"},
                      ),
                  ],
                  gap="md",
                  px="xl",
                  py="xl",
              )
          )
      )
    except Exception:  # pylint: disable=broad-exception-caught
      continue

  if not slides:
    return None

  if len(slides) > 1:
    carousel_content = dmc.Carousel(
        children=slides,
        withIndicators=True,
        withControls=True,
        emblaOptions={"loop": True, "align": "start"},
        slideSize="100%",
        id="generated-charts-carousel",
    )
  else:
    carousel_content = slides[0].children

  if minimal:
    return carousel_content

  return dmc.Card(
      withBorder=True,
      radius="md",
      shadow="none",
      padding="lg",
      mt="md",
      children=[
          dmc.CardSection(
              withBorder=True,
              inheritPadding=True,
              py="md",
              bg="gray.0",
              children=[
                  dmc.Group(
                      justify="space-between",
                      children=[
                          dmc.Group(
                              gap="xs",
                              children=[
                                  DashIconify(
                                      icon="bi:graph-up",
                                      width=20,
                                      color="#94a3b8",
                                  ),
                                  dmc.Text(
                                      "GENERATED CHARTS", fw=600, size="md"
                                  ),
                              ],
                          ),
                          dmc.Badge(
                              f"{len(slides)} Charts",
                              variant="light",
                              color="gray",
                              size="xs",
                          ),
                      ],
                  ),
              ],
          ),
          dmc.CardSection(
              children=carousel_content,
          ),
      ],
  )
