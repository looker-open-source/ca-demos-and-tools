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

"""Tests for TimelineService."""

from prism.server.services.timeline_service import TimelineService


class TestTimelineService:
  """Unit tests for TimelineService."""

  def test_create_timeline_empty(self):
    service = TimelineService()
    timeline = service.create_timeline_from_trace(
        trace=[], ttfr_ms=100, total_duration_ms=500
    )
    assert timeline.total_duration_ms == 500
    assert not timeline.events

  def test_create_timeline_basic(self):
    service = TimelineService()
    trace = [
        # Timestamps must be ISO format.
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "text": {"parts": ["Hello"], "text_type": "THOUGHT"}
            },
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {
                "text": {"parts": ["World"], "text_type": "FINAL_RESPONSE"}
            },
        },
    ]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=50, total_duration_ms=2000
    )

    assert len(timeline.events) == 2

    e1 = timeline.events[0]
    assert e1.duration_ms == 50  # TTFR
    assert "thought" in e1.title.lower()
    assert e1.content == "Hello"
    assert e1.icon == "bi:lightbulb"

    e2 = timeline.events[1]
    assert e2.duration_ms == 1000  # 1s diff
    assert "response" in e2.title.lower()
    assert e2.content == "World"
    assert e2.icon == "bi:chat-left-text"

  def test_parse_json_content(self):
    """A schema event's content is parsed as JSON."""
    service = TimelineService()
    trace = [{
        "timestamp": "2023-10-27T10:00:00Z",
        "system_message": {"schema": {"query": {"sql": "SELECT 1"}}},
    }]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=100
    )
    assert len(timeline.events) == 1
    e1 = timeline.events[0]
    assert e1.content_type == "json"
    assert "SELECT 1" in e1.content
    assert e1.icon == "bi:database-check"

  def test_parse_sql_content(self):
    """A data event's generated_sql is parsed as SQL."""
    service = TimelineService()
    trace = [{
        "timestamp": "2023-10-27T10:00:00Z",
        "system_message": {"data": {"generated_sql": "SELECT * FROM table"}},
    }]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=100
    )
    assert len(timeline.events) == 1
    e1 = timeline.events[0]
    assert e1.content_type == "sql"
    assert e1.content == "SELECT * FROM table"
    assert e1.icon == "bi:code-slash"

  def test_an_event_with_a_null_message_is_still_an_event(self):
    """A trace can carry an event whose message key is present and null.

    The fallback chain ended on event.get("system_message", {}), which is
    reached only when system_message is falsy. An explicit null came back out
    of it as None, and the membership test below it raised TypeError, taking
    the whole timeline with it.
    """
    service = TimelineService()
    trace = [{"timestamp": "2023-10-27T10:00:00Z", "system_message": None}]

    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=100
    )

    assert len(timeline.events) == 1

  def test_a_camel_case_server_message_is_read(self):
    """The trace arrives as JSON from the API, so the keys are camelCase."""
    service = TimelineService()
    trace = [{
        "timestamp": "2023-10-27T10:00:00Z",
        "serverMessage": {
            "text": {"parts": ["Hello"], "textType": "FINAL_RESPONSE"}
        },
    }]

    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=100
    )

    assert timeline.events[0].content == "Hello"
    assert timeline.events[0].title == "Final Response"

  def test_parse_new_event_types(self):
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "chart": {
                    "query": {
                        "instructions": "Generate a chart",
                        "dataResultName": "res",
                    }
                }
            },
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {
                "analysis": {"query": {"question": "Analyze this"}}
            },
        },
        {
            "timestamp": "2023-10-27T10:00:02Z",
            "system_message": {
                "text": {"parts": ["Starting..."], "text_type": "PROGRESS"}
            },
        },
        {
            "timestamp": "2023-10-27T10:00:03Z",
            "system_message": {
                "data": {"generated_looker_query": {"model": "thelook"}}
            },
        },
    ]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=4000
    )
    assert len(timeline.events) == 4

    assert timeline.events[0].title == "Chart Request"
    assert timeline.events[0].icon == "bi:graph-up"

    assert timeline.events[1].title == "Analysis Request"
    assert timeline.events[1].icon == "bi:calculator"

    assert timeline.events[2].title == "Agent Progress"
    assert timeline.events[2].icon == "bi:info-circle"

    assert timeline.events[3].title == "Generated Looker Query"
    assert timeline.events[3].icon == "bi:funnel"

  def test_trace_grouping_heuristic(self):
    """A thought takes the title of the call that follows it."""
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "text": {
                    "parts": ["Thinking about schema..."],
                    "text_type": "THOUGHT",
                }
            },
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {"schema": {"query": {"sql": "DESCRIBE table"}}},
        },
        {
            "timestamp": "2023-10-27T10:00:02Z",
            "system_message": {
                "text": {
                    "parts": ["Thinking about data..."],
                    "text_type": "THOUGHT",
                }
            },
        },
        {
            "timestamp": "2023-10-27T10:00:03Z",
            "system_message": {
                "data": {"generated_sql": "SELECT * FROM table"}
            },
        },
    ]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=4000
    )
    assert len(timeline.events) == 4

    assert timeline.events[0].group_title == "Agent Reasoning - Schema Fetch"
    assert timeline.events[1].group_title == "Agent Reasoning - Schema Fetch"
    assert timeline.events[2].group_title == "Agent Reasoning - Data Query"
    assert timeline.events[3].group_title == "Agent Reasoning - Data Query"

  def test_trace_grouping_request_vs_result(self):
    """The request joins the reasoning group, the result starts its own."""
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "text": {
                    "parts": ["Thinking..."],
                    "text_type": "THOUGHT",
                }
            },
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {"schema": {"query": {"sql": "SELECT 1"}}},
        },
        {
            "timestamp": "2023-10-27T10:00:02Z",
            "system_message": {"schema": {"result": {"tables": []}}},
        },
    ]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=3000
    )
    assert len(timeline.events) == 3

    # Reasoning + Request grouped together
    assert timeline.events[0].group_title == "Agent Reasoning - Schema Fetch"
    assert timeline.events[1].group_title == "Agent Reasoning - Schema Fetch"

    # Result is a separate phase
    assert timeline.events[2].group_title == "Schema Fetch"

  def test_trace_grouping_explicit_id(self):
    """An explicit group_id wins over the heuristic."""
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "text": {"parts": ["Thought"], "text_type": "THOUGHT"},
                "group_id": 42,
            },
        },
    ]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=1000
    )
    assert len(timeline.events) == 1
    assert timeline.events[0].group_title == "Group 42"

  def test_clarification_and_error(self):
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {"clarification": {"text": "What do you mean?"}},
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {"error": {"text": "Query failed"}},
        },
    ]
    timeline = service.create_timeline_from_trace(
        trace=trace, ttfr_ms=0, total_duration_ms=2000
    )
    assert len(timeline.events) == 2
    assert timeline.events[0].title == "Clarification Question"
    assert timeline.events[0].icon == "bi:question-circle-fill"
    assert timeline.events[1].title == "Error"
    assert timeline.events[1].content == "Query failed"

  def test_calculate_tool_timings_grouped(self):
    """Tool timings aggregate by group_title."""
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "text": {"parts": ["Thinking..."], "text_type": "THOUGHT"}
            },
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {
                "data": {"generated_sql": "SELECT * FROM table"}
            },
        },
        {
            "timestamp": "2023-10-27T10:00:02Z",
            "system_message": {"data": {"result": {"data": "some data"}}},
        },
        {
            "timestamp": "2023-10-27T10:00:03Z",
            "system_message": {
                "text": {"parts": ["Done"], "text_type": "FINAL_RESPONSE"}
            },
        },
    ]

    # total_duration_ms = 4000
    # ttfr_ms = 500
    # Groups:
    # 1: Agent Reasoning - Data Query (Event 0-1).
    #    Duration = e0.dur (ttfr) + e1.dur (gap) = 500 + 1000 = 1500
    # 2: Data Query (Event 2). Duration = e2.dur (gap) = 1000
    # 3: Final Response (Event 3).
    #    Duration = e3.dur (gap) + final_gap = 1000 + 500 = 1500
    timings = service.calculate_tool_timings(
        trace=trace, ttfr_ms=500, total_duration_ms=4000
    )

    assert timings == {
        "Agent Reasoning - Data Query": 1500,
        "Data Query": 1000,
        "Final Response": 1500,
    }

  def test_a_run_that_ends_on_its_last_event_gets_no_padding(self):
    """The last group used to be given 100ms so its bar had a width.

    calculate_tool_timings sums the same groups, so the padding was charged to
    whichever tool went last and the run detail page printed it as a measured
    duration. Here the events account for the whole run, so there is nothing
    left to hand out.
    """
    service = TimelineService()
    trace = [
        {
            "timestamp": "2023-10-27T10:00:00Z",
            "system_message": {
                "text": {"parts": ["Thinking..."], "text_type": "THOUGHT"}
            },
        },
        {
            "timestamp": "2023-10-27T10:00:01Z",
            "system_message": {
                "text": {"parts": ["Done"], "text_type": "FINAL_RESPONSE"}
            },
        },
    ]

    # ttfr 500 for the first event, a 1000ms gap to the second, so the trace
    # fills all 1500ms of the run and the final gap is zero.
    timings = service.calculate_tool_timings(
        trace=trace, ttfr_ms=500, total_duration_ms=1500
    )

    assert timings == {"Agent Thought": 500, "Final Response": 1000}
