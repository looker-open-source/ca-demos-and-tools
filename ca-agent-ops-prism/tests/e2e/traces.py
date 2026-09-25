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

"""Agent responses used by the E2E cassettes.

These are hand-built, not promoted from
``tests/integration/data/success_response.json``. That fixture puts
``generated_sql``, ``query`` and ``result`` inside a single ``DataMessage``,
but those three fields share a protobuf ``oneof``, so it cannot be parsed back
into a ``geminidataanalytics.Message`` at all. The integration test that uses
it substitutes a mock proto and never exercises the real path.

A cassette does get parsed back, so it has to be shaped the way the service
answers: one message per event.

``./scripts/run_e2e.sh --record`` overwrites anything built here with recorded
traces.
"""

from __future__ import annotations

import datetime
from typing import Any

QUESTION = "How many orders were there?"
SYSTEM_INSTRUCTION = "Answer questions about the demo orders table."
ANSWER = "There were 128 orders."
PROGRESS = "Scanning the orders table."
GENERATED_SQL = "SELECT COUNT(*) AS order_count FROM `e2e-project.demo.orders`"

# Spacing between the synthetic per-message timestamps.
_STEP = datetime.timedelta(milliseconds=300)


def _timestamps(count: int) -> list[str]:
  """RFC3339 timestamps for ``count`` messages, ending about now.

  ``geminidataanalytics.Message`` carries a ``timestamp``, and
  ``TimelineService.create_timeline_from_trace`` silently drops every message
  that lacks one, so a trace without them renders as "No trace data
  available." A trace built here has to carry them or it isn't the shape the
  app reads.

  Generated at call time, not frozen, because the timeline measures each event
  against ``trial.started_at``. Frozen timestamps would render durations in the
  millions of milliseconds. Real recorded cassettes have the same problem and
  nothing here can fix it.
  """
  now = datetime.datetime.now(datetime.timezone.utc)
  first = now - _STEP * count
  return [
      (first + _STEP * i).isoformat().replace("+00:00", "Z")
      for i in range(count)
  ]


def success(
    *,
    answer: str = ANSWER,
    progress: str | None = PROGRESS,
    generated_sql: str = GENERATED_SQL,
    rows: list[dict[str, str]] | None = None,
    chart_type: str | None = "bar",
) -> list[dict[str, Any]]:
  """A complete, successful agent trace.

  Args:
    answer: The final response text the UI displays.
    progress: A progress message, or None to omit it. Progress text is streamed
      to the user while the agent works but is not part of the answer, so
      assertions must not match against it.
    generated_sql: The SQL the agent reports having run.
    rows: The result rows. Defaults to a single row.
    chart_type: The Vega mark type, or None for no chart message.

  Returns:
    A list of messages in ``MessageToDict(preserving_proto_field_name=True)``
    form, the same shape ``trial.trace_results`` stores.
  """
  messages: list[dict[str, Any]] = []
  if progress:
    messages.append({
        "system_message": {
            "text": {"text_type": "PROGRESS", "parts": [progress]}
        }
    })
  messages.append(
      {"system_message": {"data": {"generated_sql": generated_sql}}}
  )
  messages.append({
      "system_message": {
          "data": {"result": {"data": rows or [{"order_count": "128"}]}}
      }
  })
  if chart_type:
    messages.append({
        "system_message": {
            "chart": {"result": {"vega_config": {"mark": {"type": chart_type}}}}
        }
    })
  messages.append({
      "system_message": {
          "text": {"text_type": "FINAL_RESPONSE", "parts": [answer]}
      }
  })
  for message, timestamp in zip(messages, _timestamps(len(messages))):
    message["timestamp"] = timestamp
  return messages
