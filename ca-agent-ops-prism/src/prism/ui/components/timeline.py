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

import datetime
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
                                    dmc.Group(
                                        gap="xs",
                                        children=[
                                            dmc.Text(
                                                f"{event.get('duration_ms', 0)}ms",
                                                size="xs",
                                                fw=500,
                                            ),
                                            dmc.Text(
                                                f"{step_duration_pct:.1f}%",
                                                size="xs",
                                                c="dimmed",
                                            ),
                                            dmc.Badge(
                                                f"+{event.get('cumulative_duration_ms', 0) / 1000:.1f}s",
                                                variant="light",
                                                color="gray",
                                                size="xs",
                                                radius="sm",
                                                tt="none",
                                            ),
                                        ],
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


def render_trace_timeline(timeline_data: dict[str, Any]) -> dmc.Timeline:
  """Renders the execution trace timeline with grouped events."""
  groups = timeline_data.get("groups", [])
  total_duration = timeline_data.get("total_duration_ms", 0)

  if not groups:
    return dmc.Text("No trace data available.", c="dimmed", size="sm")

  timeline_items = []
  for group in groups:
    group_title = group["title"]
    total_group_duration = group["duration_ms"]
    event_list = group["events"]
    bullet_icon = group["icon"]

    # Calculate timestamps for the group
    first_event = event_list[0]
    ts = first_event.get("timestamp")
    timestamp_str = ""
    if ts:
      if isinstance(ts, str):
        try:
          ts_dt = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))
          timestamp_str = ts_dt.strftime("%H:%M:%S.%f")[:-3]
        except ValueError:
          timestamp_str = ts
      elif isinstance(ts, datetime.datetime):
        timestamp_str = ts.strftime("%H:%M:%S.%f")[:-3]

    # Progress bar for the whole group
    start_ms = first_event.get("cumulative_duration_ms", 0) - first_event.get(
        "duration_ms", 0
    )
    if total_duration > 0:
      prev_pct = max(0, start_ms / total_duration * 100)
      curr_pct = max(0, total_group_duration / total_duration * 100)
    else:
      prev_pct = 0
      curr_pct = 0

    if prev_pct + curr_pct > 100:
      curr_pct = 100 - prev_pct

    title_row = dmc.Group(
        justify="space-between",
        children=[
            dmc.Text(group_title, fw=800, size="sm", c="blue.7"),
            dmc.Group(
                gap="xs",
                children=[
                    dmc.Text(f"{total_group_duration}ms", size="xs", fw=500),
                    dmc.Text(f"{curr_pct:.1f}%", size="xs", c="dimmed"),
                    dmc.Badge(
                        timestamp_str,
                        variant="light",
                        color="gray",
                        size="sm",
                        radius="sm",
                        tt="none",
                    ),
                ],
            ),
        ],
    )

    progress_bar = dmc.ProgressRoot(
        children=[
            dmc.ProgressSection(value=prev_pct, color="transparent"),
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

    # Render all events in the group
    group_children = []
    for event in event_list:
      group_children.append(
          html.Div(
              [
                  dmc.Text(event["title"], fw=600, size="xs", mt="xs", mb=4),
                  _render_event_content(event),
              ],
              style={},
          )
      )

    icon_color = _get_icon_color(bullet_icon)

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
                [progress_bar] + group_children, style={"marginTop": 8}
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


def _render_event_content(event: dict[str, Any]) -> html.Div:
  """Helper to render individual event content."""
  content_type = event.get("content_type", "text")
  content = event.get("content", "")

  # Custom rendering based on content and type
  if event["title"] in ["Test Case", "Final Response", "Agent Thought"]:
    return dmc.Paper(
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
      if isinstance(content, str):
        json_obj = json.loads(content)
        content = json.dumps(json_obj, indent=2)
    except Exception:  # pylint: disable=broad-exception-caught
      pass

    return dmc.Accordion(
        variant="contained",
        radius="md",
        children=[
            dmc.AccordionItem(
                [
                    dmc.AccordionControl(
                        dmc.Text("Details", size="sm", fw=500)
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

      return dmc.Paper(
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
      return dmc.Code(
          content,
          block=True,
          fz="xs",
          style={"whiteSpace": "pre-wrap"},
          color="red",
      )
  elif content_type in ["sql", "python", "code"]:
    return dmc.Code(
        content,
        block=True,
        fz="xs",
        style={"whiteSpace": "pre-wrap"},
        color="gray",
    )
  else:
    return dmc.Text(content, size="sm")


def _get_icon_color(bullet_icon: str) -> str:
  """Helper to map icons to colors."""
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
  return icon_color
