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

import datetime
import json
import logging
from typing import Any

from prism.common.schemas.timeline import Timeline
from prism.common.schemas.timeline import TimelineEvent
from prism.common.schemas.timeline import TimelineGroup

logger = logging.getLogger(__name__)


def _camel_case(field: str) -> str:
  """The JSON spelling of a proto field name."""
  head, *rest = field.split("_")
  return head + "".join(word.title() for word in rest)


class TimelineService:
  """Turns trace events into timed events, grouped by agent phase."""

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
              "Generated Looker Query",
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
          "reasoning_titles": [
              "Analysis Request",
              "Analysis Plan",
              "Analysis Instruction",
          ],
          "action_titles": [
              "Data Analysis",
              "Analysis Code",
              "Analysis Output",
              "Analysis Error",
              "Analysis Chart",
              "Analysis Result",
              "Analysis Data",
              "Analysis Reference Data",
          ],
          "reasoning_label": "Agent Reasoning - Data Analysis",
          "action_label": "Data Analysis",
      },
  }

  # One AnalysisEvent carries one of these, so the first present is the event.
  # Ordered the way an analysis runs: plan it, write the code, run it, report.
  # Everything but the code used to render as a dump of the whole message under
  # one title, so ten rows reading "Data Analysis" hid what each of them was.
  ANALYSIS_EVENT_FIELDS = (
      ("planner_reasoning", "bi:lightbulb", "Analysis Plan", "text"),
      ("coder_instruction", "bi:pencil-square", "Analysis Instruction", "text"),
      ("code", "bi:code-square", "Analysis Code", "python"),
      ("execution_output", "bi:terminal", "Analysis Output", "text"),
      ("execution_error", "bi:exclamation-triangle", "Analysis Error", "text"),
      (
          "result_vega_chart_json",
          "bi:bar-chart-line-fill",
          "Analysis Chart",
          "vegalite",
      ),
      (
          "result_natural_language",
          "bi:chat-left-text",
          "Analysis Result",
          "text",
      ),
      ("result_csv_data", "bi:table", "Analysis Data", "text"),
      (
          "result_reference_data",
          "bi:link-45deg",
          "Analysis Reference Data",
          "json",
      ),
      ("error", "bi:exclamation-triangle", "Analysis Error", "text"),
  )

  def _parse_event(self, event: dict[str, Any]) -> tuple[str, str, str, str]:
    """Parses a trace event into its icon, title, content and content type."""
    # Support both snake_case (Python) and camelCase (JSON/Proto)
    message = event.get("system_message") or event.get("systemMessage") or {}

    if not message:
      message = event.get("server_message") or event.get("serverMessage") or {}

    # TextMessage (THOUGHT, FINAL_RESPONSE, etc.)
    if "text" in message:
      text_content = message["text"]
      text_type = text_content.get("text_type") or text_content.get("textType")

      parts = text_content.get("parts", [""])

      content = "\n\n".join(str(p) for p in parts) if parts else ""

      if text_type in ("FINAL_RESPONSE", 1):
        return "bi:chat-left-text", "Final Response", content, "text"
      elif text_type in ("THOUGHT", 2):
        return "bi:lightbulb", "Agent Thought", content, "text"
      elif text_type in ("PROGRESS", 3):
        return "bi:info-circle", "Agent Progress", content, "text"
      else:
        # Everything the published enum does not name. That covers the zero
        # value, which the wire format drops so an unset type arrives as no
        # type at all, and it covers the types the service sends that the
        # installed client library is too old to name. A BigQuery run ends on
        # one of those today, and a row reading "Unknown Text Type (4)" put the
        # last word of every run on a defect the agent did not have.
        return "bi:chat-left", "Agent Message", content, "text"

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

    # DataMessage (query, generated_sql, generated_looker_query, result,
    # big_query_job)
    if "data" in message:
      data_content = message["data"]
      if "query" in data_content:
        query_content = data_content["query"]
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

      looker_query = data_content.get(
          "generated_looker_query"
      ) or data_content.get("generatedLookerQuery")
      if looker_query:
        # What a Looker agent sends where a BigQuery agent sends SQL. Nothing
        # read it, so every Looker run had one event reading "Unknown Event"
        # with the whole message dumped underneath.
        return (
            "bi:funnel",
            "Generated Looker Query",
            json.dumps(looker_query, indent=2),
            "json",
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

      if isinstance(progress_event, dict):
        for field, icon, title, content_type in self.ANALYSIS_EVENT_FIELDS:
          value = progress_event.get(field) or progress_event.get(
              _camel_case(field)
          )
          if not value:
            continue
          if content_type in ("json", "vegalite") and not isinstance(
              value, str
          ):
            value = json.dumps(value, indent=2)
          return icon, title, str(value), content_type

      return (
          "bi:bar-chart-line",
          "Data Analysis",
          json.dumps(analysis_content, indent=2),
          "json",
      )

    # ExampleQueries
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

    # ErrorMessage
    if "error" in message:
      error_content = message["error"]
      text = (
          error_content.get("text") if isinstance(error_content, dict) else None
      )
      if text:
        # The message is the whole of a public ErrorMessage. Dumping the
        # wrapper put the text on one line with its newlines escaped, which is
        # the one event nobody can afford to have to squint at.
        return "bi:exclamation-triangle", "Error", text, "text"
      return (
          "bi:exclamation-triangle",
          "Error",
          json.dumps(error_content, indent=2),
          "json",
      )

    # The keys, not the body. This runs in production, and the body carries
    # the question and whatever rows came back with it.
    logger.warning("Unknown event structure: %s", sorted(message.keys()))
    return (
        "bi:question-circle",
        "Unknown Event",
        json.dumps(event, indent=2),
        "json",
    )

  def create_timeline_from_trace(
      self,
      trace: list[dict[str, Any]],
      ttfr_ms: int,
      total_duration_ms: int,
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
      icon, title, content, content_type = self._parse_event(raw_data)

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

    # Whatever is left has no group of its own, so it is grouped by what it
    # sits next to. A thought looks forward, because it describes the work it
    # is about to do and not the work that has just finished. Everything else
    # joins the phase the last thought opened.
    current_phase = None
    for i, event in enumerate(timeline_events):
      if event.group_title:
        continue

      if event.title == "Agent Thought":
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
          # The action closes the phase, so the next thought opens a new one.
          current_phase = None
        else:
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
            # Not a title in any phase, so leave the event in the reasoning
            # group that is already open.
            event.group_title = phase["reasoning_label"]

      else:
        for phase_key, phase in self.PHASE_CONFIG.items():
          if event.title in phase["reasoning_titles"]:
            event.group_title = phase["reasoning_label"]
            current_phase = phase_key
            break
          elif event.title in phase["action_titles"]:
            event.group_title = phase["action_label"]
            break

    # At least the last event's cumulative duration, so a trial whose stored
    # duration_ms is 0 still has a scale to draw the bars against.
    last_cumulative = (
        timeline_events[-1].cumulative_duration_ms if timeline_events else 0
    )
    if total_duration_ms <= 0:
      total_duration_ms = last_cumulative
    elif total_duration_ms < last_cumulative:
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

    for event in events:
      title = event.group_title or event.title
      if title != current_group_title:
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

    # The loop closes a group when the next one opens, so the last one is
    # still open here.
    if current_events:
      last_event = current_events[-1]
      final_gap = total_duration_ms - last_event.cumulative_duration_ms
      if final_gap > 0:
        group_duration += final_gap
      # A gap of zero used to have 100ms added to give the last bar something
      # to draw. calculate_tool_timings sums these groups, so the padding was
      # charged to whichever tool went last and the run detail page printed it
      # as a real measurement.

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
      trace: list[dict[str, Any]],
      ttfr_ms: int = 0,
      total_duration_ms: int = 0,
  ) -> dict[str, int]:
    """Sums the timeline group durations by title.

    A title the agent visits more than once is one entry holding the total,
    not one entry per visit.
    """
    timeline = self.create_timeline_from_trace(
        trace, ttfr_ms, total_duration_ms
    )

    tool_timings = {}
    for group in timeline.groups:
      tool_timings[group.title] = (
          tool_timings.get(group.title, 0) + group.duration_ms
      )

    return tool_timings
