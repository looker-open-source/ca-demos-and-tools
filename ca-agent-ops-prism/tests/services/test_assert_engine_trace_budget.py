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

"""Regression tests for the trace budget in the AI judge prompt.

A single data event with a few thousand result rows is megabytes, and the
model rejects a prompt that size, so the judge fails on every assertion behind
it. trace_for_prompt exists to cut the trace before that happens.
"""

import json

from prism.server.services import assert_engine


def event_of_exactly(size):
  """A trace event whose pretty printed JSON is ``size`` characters."""
  event = {"system_message": {"text": {"parts": [""]}}}
  filler = size - len(json.dumps(event, indent=2))
  event["system_message"]["text"]["parts"] = ["x" * filler]
  return event


def big_data_event():
  """The kind of event the budget was written for: one large result set."""
  return {
      "system_message": {
          "data": {"result": {"data": [{"id": i} for i in range(4000)]}}
      }
  }


def test_an_event_of_exactly_the_budget_still_cuts_the_next_one():
  """The chunks are joined with newlines, and used counts those newlines.

  A trace whose leading events filled the budget exactly left used one past
  it, so the slice for the next event was chunk[:-1]: the whole oversized
  event minus its last character, which is the prompt the budget prevents.
  """
  budget = assert_engine.AI_JUDGE_TRACE_CHAR_BUDGET
  messages = [event_of_exactly(budget), big_data_event()]

  trace = assert_engine.trace_for_prompt(messages)

  assert "Trace truncated" in trace
  assert '"id"' not in trace
  assert len(trace) < budget + 200


def test_a_trace_under_the_budget_is_passed_through_whole():
  """The cut only happens when there is something to cut."""
  messages = [event_of_exactly(100), event_of_exactly(100)]

  trace = assert_engine.trace_for_prompt(messages)

  assert "Trace truncated" not in trace
  assert len(trace) == 201
