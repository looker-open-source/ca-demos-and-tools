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

"""The trace viewer against the public Gemini Data Analytics API.

The viewer reads dicts, and the dicts come from ``MessageToDict`` over the
messages the chat stream returns. Nothing tied the two together, so the parser
drifted: it grew branches for fields the published API does not have, and it
never learned ``generated_looker_query``, which is what a Looker agent sends
where a BigQuery agent sends SQL. Every Looker run had an event reading
"Unknown Event".

These tests build real protos from the installed client library and serialize
them exactly the way the client does. The public descriptor is the list of
things the viewer has to handle, and it is also the whole list.
"""

from google.cloud import geminidataanalytics_v1beta as gda
from google.protobuf import json_format
from prism.server.services.timeline_service import TimelineService
import pytest

_TIMESTAMP = "2023-10-27T10:00:00Z"

# For the one test that needs two events in a fixed order.
_LATER_TIMESTAMP = "2023-10-27T10:00:01Z"


def _fields(message_type) -> list[str]:
  """The field names of a public message, straight off its descriptor."""
  return [f.name for f in message_type.pb(message_type()).DESCRIPTOR.fields]


# group_id labels an event, it is not one, so it has no rendering of its own.
_PAYLOAD_FIELDS = [f for f in _fields(gda.SystemMessage) if f != "group_id"]

# One populated SystemMessage per payload field. Written out rather than
# generated, because a message full of default values serializes to nothing and
# would assert that the parser handles an empty dict.
_SYSTEM_MESSAGES = {
    "text": gda.SystemMessage(
        text=gda.TextMessage(
            parts=["Hello"], text_type=gda.TextMessage.TextType.THOUGHT
        )
    ),
    "schema": gda.SystemMessage(
        schema=gda.SchemaMessage(query=gda.SchemaQuery(question="what tables"))
    ),
    "data": gda.SystemMessage(data=gda.DataMessage(generated_sql="SELECT 1")),
    "analysis": gda.SystemMessage(
        analysis=gda.AnalysisMessage(
            query=gda.AnalysisQuery(question="why did it drop")
        )
    ),
    "chart": gda.SystemMessage(
        chart=gda.ChartMessage(
            query=gda.ChartQuery(instructions="draw a bar chart")
        )
    ),
    "error": gda.SystemMessage(error=gda.ErrorMessage(text="it broke")),
    "example_queries": gda.SystemMessage(
        example_queries=gda.ExampleQueries(
            example_queries=[
                gda.ExampleQuery(natural_language_question="how many orders")
            ]
        )
    ),
    "clarification": gda.SystemMessage(
        clarification=gda.ClarificationMessage(
            questions=[gda.ClarificationQuestion(question="which year")]
        )
    ),
}


def _trace(system_message: gda.SystemMessage) -> list[dict]:
  """One event, serialized the way GeminiDataAnalyticsClient stores it."""
  message = gda.Message(system_message=system_message)
  event = json_format.MessageToDict(
      message._pb,  # pylint: disable=protected-access
      preserving_proto_field_name=True,
  )
  event["timestamp"] = _TIMESTAMP
  return [event]


def _parse(system_message: gda.SystemMessage):
  """The one timeline event a single system message produces."""
  timeline = TimelineService().create_timeline_from_trace(
      trace=_trace(system_message), ttfr_ms=0, total_duration_ms=100
  )
  assert len(timeline.events) == 1
  return timeline.events[0]


def test_the_public_message_has_no_field_without_a_fixture():
  """A new field in the API shows up here before it shows up as a bug."""
  assert set(_SYSTEM_MESSAGES) == set(_PAYLOAD_FIELDS)


@pytest.mark.parametrize("field", _PAYLOAD_FIELDS)
def test_every_public_field_is_understood(field):
  """Anything the API can send has to render as itself, not as a dump."""
  event = _parse(_SYSTEM_MESSAGES[field])

  assert event.title != "Unknown Event"
  assert event.content


def test_a_field_the_parser_does_not_know_is_reported_as_unknown():
  """There is no catch-all, so the tests above are worth something.

  It also means an unpublished field renders as an unknown event rather than
  as a feature the viewer claims to support.
  """
  trace = [{"timestamp": _TIMESTAMP, "system_message": {"not_a_field": {}}}]

  timeline = TimelineService().create_timeline_from_trace(
      trace=trace, ttfr_ms=0, total_duration_ms=100
  )

  assert timeline.events[0].title == "Unknown Event"


@pytest.mark.parametrize("text_type", list(gda.TextMessage.TextType))
def test_every_public_text_type_has_a_title(text_type):
  """Including the unspecified one, which the wire format sends as nothing."""
  event = _parse(
      gda.SystemMessage(
          text=gda.TextMessage(parts=["Some text"], text_type=text_type)
      )
  )

  assert "Unknown" not in event.title
  assert event.content == "Some text"


def test_a_text_type_the_published_enum_does_not_name_reads_as_a_message():
  """The service sends one the installed library cannot name, on every run.

  Captured from a live BigQuery agent: the last message of the run carries a
  text type past the end of TextType. Titling it "Unknown Text Type (4)" ended
  every run on a row that reads as a defect in the agent, and the text under it
  is ordinary agent prose.
  """
  unnamed = max(t.value for t in gda.TextMessage.TextType) + 1
  trace = [{
      "timestamp": _TIMESTAMP,
      "system_message": {
          "text": {"parts": ["Some text"], "text_type": unnamed}
      },
  }]

  timeline = TimelineService().create_timeline_from_trace(
      trace=trace, ttfr_ms=0, total_duration_ms=100
  )

  assert "Unknown" not in timeline.events[0].title
  assert timeline.events[0].content == "Some text"


def test_a_looker_agent_query_is_not_an_unknown_event():
  """A Looker agent sends this where a BigQuery agent sends generated_sql."""
  event = _parse(
      gda.SystemMessage(
          data=gda.DataMessage(
              generated_looker_query=gda.LookerQuery(
                  model="thelook",
                  explore="orders",
                  fields=["orders.count"],
                  limit="100",
              )
          )
      )
  )

  assert event.title == "Generated Looker Query"
  assert "thelook" in event.content
  assert "orders.count" in event.content


def test_a_looker_query_groups_with_the_sql_it_replaces():
  """Otherwise a Looker run reads as one ungrouped event per step.

  Run through create_timeline_from_trace rather than read off PHASE_CONFIG. A
  title listed in the config is not the same thing as a grouped event, and the
  earlier version of this test only checked the list.
  """
  looker_query = gda.SystemMessage(
      data=gda.DataMessage(
          generated_looker_query=gda.LookerQuery(
              model="thelook",
              explore="orders",
              fields=["orders.count"],
              limit="100",
          )
      )
  )
  query_result = gda.SystemMessage(
      data=gda.DataMessage(result=gda.DataResult(name="orders"))
  )

  (query_event,) = _trace(looker_query)
  (result_event,) = _trace(query_result)
  # The events are sorted by timestamp, so the result needs a later one than
  # the query it answers.
  result_event["timestamp"] = _LATER_TIMESTAMP

  timeline = TimelineService().create_timeline_from_trace(
      trace=[query_event, result_event], ttfr_ms=0, total_duration_ms=100
  )

  assert [e.title for e in timeline.events] == [
      "Generated Looker Query",
      "Query Result",
  ]
  # The query opens the data phase and the result closes it, the same pair
  # generated_sql makes.
  assert timeline.events[0].group_title == "Agent Reasoning - Data Query"
  assert timeline.events[1].group_title == "Data Query"


@pytest.mark.parametrize("field", _fields(gda.AnalysisEvent))
def test_every_analysis_event_field_says_what_it_is(field):
  """One analysis produces ten of these, and they are not the same thing.

  Only the code was ever read. Everything else rendered as a dump of the whole
  message under the one title, so the plan, the output and the error were ten
  identical rows reading "Data Analysis".
  """
  event = _parse(
      gda.SystemMessage(
          analysis=gda.AnalysisMessage(
              progress_event=gda.AnalysisEvent(**{field: "the value"})
          )
      )
  )

  assert event.title != "Data Analysis"
  assert event.content == "the value"


def test_analysis_code_is_rendered_as_code():
  """The panel highlights it, and unhighlighted Python is a wall of text."""
  event = _parse(
      gda.SystemMessage(
          analysis=gda.AnalysisMessage(
              progress_event=gda.AnalysisEvent(code="import pandas as pd")
          )
      )
  )

  assert event.content_type == "python"
  assert event.content == "import pandas as pd"


def test_an_analysis_chart_is_rendered_as_a_chart():
  """It arrives as a JSON string, and the panel can draw it."""
  event = _parse(
      gda.SystemMessage(
          analysis=gda.AnalysisMessage(
              progress_event=gda.AnalysisEvent(
                  result_vega_chart_json='{"mark": "bar"}'
              )
          )
      )
  )

  assert event.content_type == "vegalite"
  assert event.content == '{"mark": "bar"}'


def test_an_analysis_message_with_no_event_still_renders():
  """The field is optional, and an empty one is not an unknown event."""
  event = _parse(
      gda.SystemMessage(
          analysis=gda.AnalysisMessage(
              query=gda.AnalysisQuery(question="why did it drop")
          )
      )
  )

  assert event.title == "Analysis Request"


def test_an_error_reads_as_its_message():
  """A stack trace with its newlines escaped into one line is unreadable."""
  event = _parse(
      gda.SystemMessage(error=gda.ErrorMessage(text="line one\nline two"))
  )

  assert event.content == "line one\nline two"
  assert event.content_type == "text"


def test_no_trace_event_can_carry_a_credential():
  """Nothing under Message reaches Credentials, so the viewer needs no pass.

  The OAuth secret is published on the agent's context, not sent on the
  messages the agent returns. The context is the path that leaks, and
  tests/clients/test_looker_credentials.py and
  tests/clients/test_gda_update_preserves_credentials.py cover it. This asserts
  the split is real, so that the viewer does not grow a redaction step it never
  fires.
  """
  seen = set()

  def reaches_credentials(message_type) -> bool:
    for field in message_type.pb(message_type()).DESCRIPTOR.fields:
      if not field.message_type:
        continue
      if field.message_type.name == "Credentials":
        return True
      if field.message_type.name in seen:
        continue
      seen.add(field.message_type.name)
      nested = getattr(gda, field.message_type.name, None)
      if nested and reaches_credentials(nested):
        return True
    return False

  assert not reaches_credentials(gda.Message)
