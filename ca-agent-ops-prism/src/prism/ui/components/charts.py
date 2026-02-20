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

"""UI components for rendering charts and profiling data."""

import dash_mantine_components as dmc


TOOL_COLORS = {
    "Agent Reasoning": "grape.6",
    "Search": "blue.6",
    "Calculator": "green.6",
    "Schema Fetch": "orange.6",
    "Query Execution": "indigo.6",
    "Data Exploration": "teal.6",
}

FALLBACK_COLORS = [
    "red.6",
    "pink.6",
    "violet.6",
    "cyan.6",
    "lime.6",
    "yellow.6",
]


def render_tool_timing_chart(
    tool_timings: dict[str, int], title: str = "Tool Timing Distribution"
) -> dmc.Paper:
  """Renders a bar chart showing time spent in each tool category."""
  if not tool_timings:
    return dmc.Paper(
        dmc.Text("No timing data available", c="dimmed", size="sm"),
        p="md",
        withBorder=True,
        radius="md",
    )

  # Transform dict to list of dicts for dmc.BarChart
  # Filter out tools with 0 duration to keep chart clean
  data = [{"tool": k, "duration": v} for k, v in tool_timings.items() if v > 0]
  # Sort by duration descending
  data.sort(key=lambda x: x["duration"], reverse=True)

  if not data:
    return dmc.Paper(
        dmc.Text("No active tool durations recorded.", c="dimmed", size="sm"),
        p="md",
        withBorder=True,
        radius="md",
    )

  return dmc.Paper(
      withBorder=True,
      radius="md",
      p="lg",
      shadow="sm",
      children=[
          dmc.Stack(
              gap="xs",
              children=[
                  dmc.Text(title, fw=700, size="sm"),
                  dmc.BarChart(
                      h=max(200, len(data) * 40),
                      data=data,
                      dataKey="tool",
                      series=[{
                          "name": "duration",
                          "color": "blue.6",
                          "label": "Duration (ms)",
                      }],
                      orientation="vertical",
                      yAxisProps={"width": 180},
                      gridAxis="y",
                      tickLine="y",
                      withTooltip=True,
                      barProps={"radius": [0, 4, 4, 0]},
                  ),
              ],
          )
      ],
  )


def render_trial_profiling(
    tool_timings: dict[str, int], title: str = "Trial Profiling"
) -> dmc.Paper:
  """Renders a comprehensive profiling card with timeline and bar chart."""
  if not tool_timings:
    return dmc.Paper(
        dmc.Text("No profiling data available", c="dimmed", size="sm"),
        p="md",
        withBorder=True,
        radius="md",
    )

  total_duration = sum(tool_timings.values())
  if total_duration == 0:
    return dmc.Paper(
        dmc.Text("Total duration is zero.", c="dimmed", size="sm"),
        p="md",
        withBorder=True,
        radius="md",
    )

  bar_data = []
  bar_series = []
  for tool, duration in tool_timings.items():
    bar_data.append({"tool": tool, "duration": duration})

  # Sort by total duration descending
  bar_data.sort(key=lambda x: x["duration"], reverse=True)

  # Standard series with single blue color
  bar_series = [{"name": "duration", "color": "blue", "label": "Duration (ms)"}]

  bar_chart_content = [
      dmc.Text("Aggregate Durations", fw=700, size="sm", mt="md"),
      dmc.BarChart(
          h=max(200, len(bar_data) * 40),
          data=bar_data,
          dataKey="tool",
          series=bar_series,
          orientation="vertical",
          gridAxis="y",
          barProps={"radius": [0, 4, 4, 0]},
          xAxisLabel="Total Duration (milliseconds)",
          yAxisProps={"width": 150},
          tooltipProps={"content": {"variant": "subtle"}},
          withLegend=False,
      ),
  ]

  return dmc.Paper(
      dmc.Stack(
          [
              dmc.Group(
                  [
                      dmc.Text(title, fw=700, size="lg"),
                      dmc.Badge(
                          f"{len(tool_timings)} tools",
                          color="blue",
                          variant="light",
                      ),
                  ],
                  justify="space-between",
              ),
              *bar_chart_content,
          ],
          gap="md",
      ),
      withBorder=True,
      shadow="sm",
      radius="md",
      p="xl",
  )
