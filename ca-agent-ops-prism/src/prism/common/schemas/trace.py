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

"""Pydantic schemas for Trace and Duration metrics."""

import datetime
import functools
from typing import Any

from google.cloud import geminidataanalytics
from google.protobuf import json_format
from prism.common.schemas.execution import AssertionResult
import pydantic


class DurationMetrics(pydantic.BaseModel):
  """Metrics for operation duration."""

  time_to_first_response: int | None = None
  total_duration: int


class AskQuestionResponse(pydantic.BaseModel):
  """Response from an ask_question call."""

  # The response is a list of JSON-dumped Protobuf messages
  # (geminidataanalytics.Message).
  # We store them as dicts so they serialize to JSON for the DB and the API.
  # The protobuf_response property rehydrates them into strong types.
  response: list[dict[str, Any]]
  duration: DurationMetrics
  error_message: str | None = None

  # Cached, because assert_engine.evaluate_all reads this once per assertion
  # and each read re-parsed the whole trace.
  @functools.cached_property
  def protobuf_response(self) -> list[geminidataanalytics.Message]:
    """Returns the response as a list of Protobuf Message objects."""
    # geminidataanalytics.Message is a proto-plus message. These dicts come
    # from MessageToDict(preserving_proto_field_name=True) in
    # GeminiDataAnalyticsClient.ask_question, so their keys are snake_case.
    # ParseDict accepts either spelling, which the proto-plus constructor does
    # not, so it is what rebuilds a stored trace. ignore_unknown_fields costs
    # us any field the pinned client does not know: it is dropped here, and no
    # assertion ever sees it.
    messages = []
    for t in self.response:
      try:
        pb_instance = geminidataanalytics.Message()._pb
        json_format.ParseDict(t, pb_instance, ignore_unknown_fields=True)
        messages.append(geminidataanalytics.Message.wrap(pb_instance))
      except Exception:
        # Unknown fields are already ignored above, so what reaches here is a
        # value whose type does not match its field, from a trace recorded
        # against an older version of the proto. The constructor is the
        # stricter of the two, so it usually raises in turn.
        messages.append(geminidataanalytics.Message(t))
    return messages


class PlaygroundTraceSchema(pydantic.BaseModel):
  """Schema for a Playground Trace."""

  id: int
  created_at: datetime.datetime
  question: str
  agent_id: int
  trace_results: list[dict[str, Any]]
  assertion_results: list[AssertionResult]
  output_text: str | None = None
  error_message: str | None = None
  score: float | None = None
  duration_ms: int | None = None
  passed: bool

  model_config = pydantic.ConfigDict(from_attributes=True)


class SimulationResult(pydantic.BaseModel):
  """Result of a playground simulation."""

  # Processed summaries for UI
  result_summary: dict[str, Any]
  suggestions_ui: list[dict[str, Any]]
