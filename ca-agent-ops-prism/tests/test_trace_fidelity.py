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

"""Checks that the E2E suite's synthetic agent traces parse as agent messages.

``tests/e2e/cassettes/`` is empty. Nothing has been recorded from the real API
yet, so every E2E spec needing an agent response builds one by hand in
``tests/e2e/traces.py``. The whole browser suite therefore rests on those dicts
being shaped the way Gemini Data Analytics answers, and nothing was checking
that.

``TraceSchema.protobuf_response`` can't check it either. It parses with
``ignore_unknown_fields=True`` and falls back to a bare constructor inside a
broad ``except``, so a misspelled field is dropped in silence and the app
renders less than it should. These tests parse strictly, which turns a typo
into an error instead of a missing panel.

This won't detect the API changing under us, only the library moving and our
own drift.
"""

from __future__ import annotations

from google.cloud import geminidataanalytics
from google.protobuf import json_format
import pytest
from tests.e2e import traces


def _parse(message: dict) -> geminidataanalytics.Message:
  """Parses one trace message strictly, as the real transport would."""
  instance = geminidataanalytics.Message()._pb  # pylint: disable=protected-access
  json_format.ParseDict(message, instance, ignore_unknown_fields=False)
  return geminidataanalytics.Message.wrap(instance)


@pytest.fixture(name="trace")
def _trace() -> list[dict]:
  return traces.success()


def test_every_message_parses_into_a_real_proto(trace):
  """A field name the proto does not know is a typo, not a feature."""
  for index, message in enumerate(trace):
    try:
      _parse(message)
    except json_format.ParseError as error:
      pytest.fail(f"traces.success()[{index}] is not a Message: {error}")


def test_every_message_carries_a_timestamp(trace):
  """TimelineService drops untimed messages, rendering "No trace data"."""
  for index, message in enumerate(trace):
    assert message.get("timestamp"), f"message {index} has no timestamp"


def test_the_answer_survives_the_round_trip(trace):
  """The text the UI displays, and the text assertions run against."""
  finals = [
      part
      for message in trace
      for part in _final_response_parts(_parse(message))
  ]
  assert finals == [traces.ANSWER]


def test_progress_is_distinguishable_from_the_answer(trace):
  """assert_engine must be able to tell the two apart.

  If the text_type enum stops round tripping, text-contains quietly starts
  matching progress text again, which is the regression this guards.
  """
  types = [_text_type(_parse(message)) for message in trace]
  assert "PROGRESS" in types
  assert "FINAL_RESPONSE" in types


def test_generated_sql_survives_the_round_trip(trace):
  sql = [
      _parse(message).system_message.data.generated_sql
      for message in trace
      if _parse(message).system_message.data.generated_sql
  ]
  assert sql == [traces.GENERATED_SQL]


def test_omitting_the_progress_message_omits_it():
  without = traces.success(progress=None)
  assert "PROGRESS" not in [_text_type(_parse(m)) for m in without]


def _text_type(message: geminidataanalytics.Message) -> str:
  """The name of the text_type enum on a message, or "" if it has no text."""
  text = message.system_message.text
  if not text.parts:
    return ""
  return geminidataanalytics.TextMessage.TextType(text.text_type).name


def _final_response_parts(message: geminidataanalytics.Message) -> list[str]:
  if _text_type(message) != "FINAL_RESPONSE":
    return []
  return list(message.system_message.text.parts)
