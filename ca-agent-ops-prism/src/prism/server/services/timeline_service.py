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


class TimelineService:
  """Service for transforming raw agent traces into a structured timeline."""

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
          event_data["data"], hide_query_schema=hide_query_schema
      )

      timeline_events.append(
          TimelineEvent(
              icon=icon,
              title=title,
              content=content,
              content_type=content_type,
              duration_ms=duration_ms,
              cumulative_duration_ms=cumulative_duration,
              timestamp=current_time,
          )
      )
      prev_time = current_time

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

    return Timeline(total_duration_ms=total_duration_ms, events=timeline_events)
