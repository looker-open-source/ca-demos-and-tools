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

  # dmc.BarChart wants a list of dicts. Drop tools with 0 duration so the
  # chart stays readable.
  data = [{"tool": k, "duration": v} for k, v in tool_timings.items() if v > 0]
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
  """Renders a profiling card with a bar chart of tool durations."""
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

  # Drop tools with 0 duration, like render_tool_timing_chart does. Keeping
  # them drew a labelled zero-width bar here for a tool the run detail page
  # left out of the same chart.
  bar_data = [
      {"tool": tool, "duration": duration}
      for tool, duration in tool_timings.items()
      if duration > 0
  ]

  bar_data.sort(key=lambda x: x["duration"], reverse=True)

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
                          # bar_data, not tool_timings. The badge counted the
                          # zero-duration tools the chart below it drops, so a
                          # trial with one idle tool read "4 tools" over three
                          # bars.
                          f"{len(bar_data)} tools",
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
