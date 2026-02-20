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

"""Service for transforming raw agent traces into a structured timeline."""

import copy
import datetime
import json
import logging
from typing import Any, Dict, List, Tuple

from prism.common.schemas.timeline import Timeline
from prism.common.schemas.timeline import TimelineEvent
from prism.common.schemas.timeline import TimelineGroup


class TimelineService:
  """Service for transforming raw agent traces into a structured timeline."""

  PHASE_CONFIG = {
      "SCHEMA": {
          "reasoning_titles": ["Schema Query"],
          "action_titles": ["Schema Result"],
          "reasoning_label": "Agent Reasoning - Schema Fetch",
          "action_label": "Schema Fetch",
      },
      "DATA": {
          "reasoning_titles": [
              "Data Query",
              "Generated SQL",
              "BigQuery Execution",
          ],
          "action_titles": ["Query Result"],
          "reasoning_label": "Agent Reasoning - Data Query",
          "action_label": "Data Query",
      },
      "CHART": {
          "reasoning_titles": ["Chart Request"],
          "action_titles": ["Chart Generated"],
          "reasoning_label": "Agent Reasoning - Chart Generation",
          "action_label": "Chart Generation",
      },
      "ANALYSIS": {
          "reasoning_titles": ["Analysis Request"],
          "action_titles": ["Data Analysis"],
          "reasoning_label": "Agent Reasoning - Data Analysis",
          "action_label": "Data Analysis",
      },
      "ADVANCED": {
          "reasoning_titles": [
              "Key Driver Analysis",
              "Outlier Detection",
              "Period Comparison",
          ],
          "action_titles": ["Advanced Insight"],
          "reasoning_label": "Agent Reasoning - Advanced Insight",
          "action_label": "Advanced Insight",
      },
  }

  def _parse_event(
      self, event: Dict[str, Any], hide_query_schema: bool = False
  ) -> Tuple[str, str, str, str]:
    """Parses a raw trace event and returns its icon, title, content, and content_type."""
    # Support both snake_case (Python) and camelCase (JSON/Proto)
    message = event.get("system_message") or event.get("systemMessage") or {}

    if not message:
      # Fallback checks for other potential keys
      message = (
          event.get("server_message")
          or event.get("serverMessage")
          or event.get("system_message", {})
      )

    # TextMessage (THOUGHT or FINAL_RESPONSE)
    if "text" in message:
      text_content = message["text"]
      text_type = text_content.get("text_type") or text_content.get("textType")
      # Safely get the first part or empty string
      parts = text_content.get("parts", [""])
      content = parts[0] if parts else ""

      if text_type == "THOUGHT":
        return "bi:lightbulb", "Agent Thought", content, "text"
      elif text_type == "PROGRESS":
        return "bi:info-circle", "Agent Progress", content, "text"
      else:
        return "bi:chat-left-text", "Final Response", content, "text"

    # SchemaMessage (query or result)
    if "schema" in message:
      schema_content = message["schema"]
      if "query" in schema_content:
        return (
            "bi:database-check",
            "Schema Query",
            json.dumps(schema_content["query"], indent=2),
            "json",
        )
      if "result" in schema_content:
        return (
            "bi:database",
            "Schema Result",
            json.dumps(schema_content["result"], indent=2),
            "json",
        )

    # DataMessage (query, generated_sql, result, big_query_job)
    if "data" in message:
      data_content = message["data"]
      if "query" in data_content:
        query_content = data_content["query"]
        if hide_query_schema:
          # Deep copy to avoid mutating the original event if it's reused
          try:
            # query_content is likely a dict, but let's be safe
            if isinstance(query_content, dict):
              query_content = copy.deepcopy(query_content)
              if "datasources" in query_content and isinstance(
                  query_content["datasources"], list
              ):
                for ds in query_content["datasources"]:
                  if isinstance(ds, dict) and "schema" in ds:
                    ds["schema"] = "...hidden..."
          except Exception:  # pylint: disable=broad-exception-caught
            # If anything fails during hiding, just proceed with original
            # content
            pass

        return (
            "bi:database-add",
            "Data Query",
            json.dumps(query_content, indent=2),
            "json",
        )

      gen_sql = data_content.get("generated_sql") or data_content.get(
          "generatedSql"
      )
      if gen_sql:
        return (
            "bi:code-slash",
            "Generated SQL",
            gen_sql,
            "sql",
        )

      bq_job = data_content.get("big_query_job") or data_content.get(
          "bigQueryJob"
      )
      if bq_job:
        return (
            "bi:play-circle",
            "BigQuery Execution",
            json.dumps(bq_job, indent=2),
            "json",
        )
      if "result" in data_content:
        # Safely access the 'data' key within the result
        result_data = data_content["result"].get(
            "data", "No data returned in result."
        )
        return (
            "bi:table",
            "Query Result",
            json.dumps(result_data, indent=2),
            "json",
        )

    # ChartMessage
    if "chart" in message:
      chart_content = message["chart"]
      if "query" in chart_content:
        return (
            "bi:graph-up",
            "Chart Request",
            json.dumps(chart_content["query"], indent=2),
            "json",
        )
      result = chart_content.get("result", {})
      vega_config = result.get("vega_config") or result.get("vegaConfig")

      if vega_config:
        return (
            "bi:bar-chart-line-fill",
            "Chart Generated",
            json.dumps(vega_config, indent=2),
            "vegalite",
        )

    # AnalysisMessage
    if "analysis" in message:
      analysis_content = message["analysis"]
      if "query" in analysis_content:
        return (
            "bi:calculator",
            "Analysis Request",
            json.dumps(analysis_content["query"], indent=2),
            "json",
        )
      progress_event = analysis_content.get(
          "progress_event"
      ) or analysis_content.get("progressEvent")

      if progress_event and "code" in progress_event:
        return (
            "bi:bar-chart-line",
            "Data Analysis",
            progress_event["code"],
            "python",
        )
      else:
        return (
            "bi:bar-chart-line",
            "Data Analysis",
            json.dumps(analysis_content, indent=2),
            "json",
        )

    # Advanced Insights
    if "key_driver_analysis" in message or "keyDriverAnalysis" in message:
      content = message.get("key_driver_analysis") or message.get(
          "keyDriverAnalysis"
      )
      return (
          "bi:diagram-3",
          "Key Driver Analysis",
          json.dumps(content, indent=2),
          "json",
      )

    if "outlier_detection" in message or "outlierDetection" in message:
      content = message.get("outlier_detection") or message.get(
          "outlierDetection"
      )
      return (
          "bi:exclamation-diamond",
          "Outlier Detection",
          json.dumps(content, indent=2),
          "json",
      )

    if "period_comparison" in message or "periodComparison" in message:
      content = message.get("period_comparison") or message.get(
          "periodComparison"
      )
      return (
          "bi:calendar-range",
          "Period Comparison",
          json.dumps(content, indent=2),
          "json",
      )

    # Example Queries
    if "example_queries" in message or "exampleQueries" in message:
      content = message.get("example_queries") or message.get("exampleQueries")
      return (
          "bi:lightbulb-fill",
          "Suggested Queries",
          json.dumps(content, indent=2),
          "json",
      )

    # ClarificationMessage
    if "clarification" in message:
      return (
          "bi:question-circle-fill",
          "Clarification Question",
          json.dumps(message["clarification"], indent=2),
          "json",
      )

    # AdvancedInsightMessage
    if "advanced_insight" in message or "advancedInsight" in message:
      content = message.get("advanced_insight") or message.get(
          "advancedInsight"
      )
      return (
          "bi:journal-text",
          "Advanced Insight",
          json.dumps(content, indent=2),
          "json",
      )

    # ErrorMessage
    if "error" in message:
      return (
          "bi:exclamation-triangle",
          "Error",
          json.dumps(message["error"], indent=2),
          "json",
      )

    logging.warning(
        "Unknown event structure: %s (%s)", message.keys(), str(message)
    )
    return (
        "bi:question-circle",
        "Unknown Event",
        json.dumps(event, indent=2),
        "json",
    )

  def create_timeline_from_trace(
      self,
      trace: List[Dict[str, Any]],
      ttfr_ms: int,
      total_duration_ms: int,
      hide_query_schema: bool = False,
      start_time_baseline: datetime.datetime | None = None,
  ) -> Timeline:
    """Parses a raw list of trace events and calculates durations."""
    if not trace:
      return Timeline(total_duration_ms=total_duration_ms, events=[])

    if start_time_baseline and start_time_baseline.tzinfo is None:
      start_time_baseline = start_time_baseline.replace(
          tzinfo=datetime.timezone.utc
      )

    parsed_events = []
    for item in trace:
      try:
        ts = datetime.datetime.fromisoformat(
            item["timestamp"].replace("Z", "+00:00")
        )
        parsed_events.append({"timestamp": ts, "data": item})
      except (KeyError, ValueError):
        continue

    parsed_events.sort(key=lambda x: x["timestamp"])

    if not parsed_events:
      return Timeline(total_duration_ms=total_duration_ms, events=[])

    start_time = start_time_baseline or parsed_events[0]["timestamp"]

    prev_time = start_time
    cumulative_duration = 0
    is_first_event = True

    timeline_events: list[TimelineEvent] = []

    for event_data in parsed_events:
      current_time = event_data["timestamp"]
      raw_data = event_data["data"]

      if is_first_event:
        if start_time_baseline:
          duration_ms = int(
              (current_time - start_time_baseline).total_seconds() * 1000
          )
        else:
          duration_ms = ttfr_ms
        is_first_event = False
      else:
        duration_ms = int((current_time - prev_time).total_seconds() * 1000)

      cumulative_duration += duration_ms
      icon, title, content, content_type = self._parse_event(
          raw_data, hide_query_schema=hide_query_schema
      )

      # Check for group_id in system_message
      message = (
          raw_data.get("system_message") or raw_data.get("systemMessage") or {}
      )
      group_id = message.get("group_id") or message.get("groupId")
      group_title = f"Group {group_id}" if group_id is not None else None

      timeline_events.append(
          TimelineEvent(
              icon=icon,
              title=title,
              content=content,
              content_type=content_type,
              duration_ms=duration_ms,
              cumulative_duration_ms=cumulative_duration,
              timestamp=current_time,
              group_title=group_title,
          )
      )
      prev_time = current_time

    # Apply grouping heuristic for events without an explicit group_title
    current_phase = None
    for i, event in enumerate(timeline_events):
      if event.group_title:
        # Respect group_id if already set
        continue

      if event.title == "Agent Thought":
        # Look ahead for the next non-thought action to determine group
        for j in range(i + 1, len(timeline_events)):
          next_event = timeline_events[j]
          found_phase = False
          for phase_key, phase in self.PHASE_CONFIG.items():
            if (
                next_event.title in phase["reasoning_titles"]
                or next_event.title in phase["action_titles"]
            ):
              event.group_title = phase["reasoning_label"]
              current_phase = phase_key
              found_phase = True
              break
          if found_phase:
            break
          elif next_event.title != "Agent Thought":
            break

        if not event.group_title and current_phase:
          event.group_title = self.PHASE_CONFIG[current_phase][
              "reasoning_label"
          ]

      elif current_phase:
        phase = self.PHASE_CONFIG[current_phase]
        if event.title in phase["reasoning_titles"]:
          event.group_title = phase["reasoning_label"]
        elif event.title in phase["action_titles"]:
          event.group_title = phase["action_label"]
          current_phase = None  # Reset after action result
        else:
          # Check if it's a new phase starting without a thought
          for phase_key, p in self.PHASE_CONFIG.items():
            if event.title in p["reasoning_titles"]:
              event.group_title = p["reasoning_label"]
              current_phase = phase_key
              break
            elif event.title in p["action_titles"]:
              event.group_title = p["action_label"]
              current_phase = None
              break
          else:
            # Not a known action, keep current group or reset?
            # Assign to current reasoning group if we are in one
            event.group_title = phase["reasoning_label"]

      else:
        # No active phase, check if this event starts one
        for phase_key, phase in self.PHASE_CONFIG.items():
          if event.title in phase["reasoning_titles"]:
            event.group_title = phase["reasoning_label"]
            current_phase = phase_key
            break
          elif event.title in phase["action_titles"]:
            event.group_title = phase["action_label"]
            break

    # Ensure total_duration_ms is at least cumulative duration of last event.
    # This renders the timeline correctly even if trial's duration_ms is 0.
    last_cumulative = (
        timeline_events[-1].cumulative_duration_ms if timeline_events else 0
    )
    if total_duration_ms <= 0:
      total_duration_ms = last_cumulative
    elif total_duration_ms < last_cumulative:
      # If reported latency is less than trace sum, clamp to trace sum.
      total_duration_ms = last_cumulative

    timeline = Timeline(
        total_duration_ms=total_duration_ms, events=timeline_events
    )
    timeline.groups = self._group_events(timeline.events, total_duration_ms)
    return timeline

  def _group_events(
      self,
      events: list[TimelineEvent],
      total_duration_ms: int,
  ) -> list[TimelineGroup]:
    """Groups sequential events with the same group_title."""
    timeline_groups = []
    if not events:
      return timeline_groups

    current_group_title = events[0].group_title or events[0].title
    current_events = []
    group_duration = 0

    for i, event in enumerate(events):
      title = event.group_title or event.title
      if title != current_group_title:
        # Finish current group
        timeline_groups.append(
            TimelineGroup(
                title=current_group_title,
                duration_ms=group_duration,
                icon=current_events[0].icon if current_events else "bi:circle",
                events=current_events,
            )
        )
        current_group_title = title
        current_events = []
        group_duration = 0

      current_events.append(event)
      group_duration += event.duration_ms

    # Final group: add duration from last event to total_duration_ms
    if current_events:
      last_event = current_events[-1]
      final_gap = total_duration_ms - last_event.cumulative_duration_ms
      if final_gap > 0:
        group_duration += final_gap
      else:
        # Give at least some padding if it's the very last thing
        group_duration += 100

      timeline_groups.append(
          TimelineGroup(
              title=current_group_title,
              duration_ms=group_duration,
              icon=current_events[0].icon if current_events else "bi:circle",
              events=current_events,
          )
      )

    return timeline_groups

  def calculate_tool_timings(
      self,
      trace: List[Dict[str, Any]],
      ttfr_ms: int = 0,
      total_duration_ms: int = 0,
  ) -> Dict[str, int]:
    """Calculates tool timings from a raw trace."""
    timeline = self.create_timeline_from_trace(
        trace, ttfr_ms, total_duration_ms
    )

    tool_timings = {}
    for group in timeline.groups:
      tool_timings[group.title] = (
          tool_timings.get(group.title, 0) + group.duration_ms
      )

    return tool_timings
