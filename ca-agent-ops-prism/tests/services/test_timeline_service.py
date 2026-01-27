"""Tests for TimelineService."""

from prism.server.services.timeline_service import TimelineService


class TestTimelineService:
  """Unit tests for TimelineService."""

  def test_create_timeline_empty(self):
    """Verifies that an empty trace returns an empty timeline."""
    service = TimelineService()
    timeline = service.create_timeline_from_trace(
        trace=[], ttfr_ms=100, total_duration_ms=500
    )
    assert timeline.total_duration_ms == 500
    assert not timeline.events

  def test_create_timeline_basic(self):
    """Verifies basic timeline creation with thought and response."""
    service = TimelineService()
    trace = [
        # Note: timestamps must be ISO format
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

    # First event
    e1 = timeline.events[0]
    assert e1.duration_ms == 50  # TTFR
    assert "thought" in e1.title.lower()
    assert e1.content == "Hello"
    assert e1.icon == "bi:lightbulb"

    # Second event
    e2 = timeline.events[1]
    assert e2.duration_ms == 1000  # 1s diff
    assert "response" in e2.title.lower()
    assert e2.content == "World"
    assert e2.icon == "bi:chat-left-text"

  def test_parse_json_content(self):
    """Verifies parsing of JSON content in schema events."""
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
    """Verifies parsing of SQL content in data events."""
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

  def test_parse_new_event_types(self):
    """Verifies parsing of newly added event types."""
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
            "system_message": {"keyDriverAnalysis": {"name": "kda"}},
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

    assert timeline.events[3].title == "Key Driver Analysis"
    assert timeline.events[3].icon == "bi:diagram-3"
