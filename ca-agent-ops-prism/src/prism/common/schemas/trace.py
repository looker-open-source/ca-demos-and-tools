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
from typing import Any

from google.cloud import geminidataanalytics
from google.protobuf import json_format
from prism.common.schemas.assertion import Assertion
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
  # We store it as dicts for JSON serialization compatibility with DBs/API
  # responses, but providing the `protobuf_response` property to rehydrate them
  # into strong types.
  response: list[dict[str, Any]]
  duration: DurationMetrics
  error_message: str | None = None

  @property
  def protobuf_response(self) -> list[geminidataanalytics.Message]:
    """Returns the response as a list of Protobuf Message objects."""
    # geminidataanalytics.Message is a proto-plus message.
    # self.response contains dicts, likely in JSON (camelCase) format from MessageToDict.
    # We must use ParseDict to reconstruct the proto correctly.
    messages = []
    for t in self.response:
      try:
        # Create a fresh internal protobuf message
        pb_instance = geminidataanalytics.Message()._pb
        # Parse the JSON dict into the protobuf
        json_format.ParseDict(t, pb_instance, ignore_unknown_fields=True)
        # Wrap it back into the high-level proto-plus object
        messages.append(geminidataanalytics.Message.wrap(pb_instance))
      except Exception:
        # Fallback: Maybe it's already snake_case?
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

  trace: PlaygroundTraceSchema
  suggestions: list[Assertion]

  # Processed summaries for UI
  result_summary: dict[str, Any]
  suggestions_ui: list[dict[str, Any]]
