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

"""Pydantic schemas for Execution entities (Runs, Trials)."""

import datetime
import enum
import logging
from typing import Any
from prism.common.schemas.assertion import Assertion
from prism.common.schemas.assertion import AssertionSchema
import pydantic

logger = logging.getLogger(__name__)


def _repair_legacy_assertion(item: Any) -> Any:
  """Flattens an assertion and rewrites the legacy "contains" type.

  Rows written before "contains" was split into text-contains and
  query-contains still carry the old value, which names no member of either
  discriminated union. Reading one raised ValidationError instead of
  rendering the page.
  """
  flattened = AssertionSchema.flatten_params(item)
  if not isinstance(flattened, dict):
    return item
  if flattened.get("type") == "contains":
    flattened["type"] = "text-contains"
  return flattened


class RunStatus(str, enum.Enum):
  """Status of an Execution Run."""

  PENDING = "PENDING"
  RUNNING = "RUNNING"
  EXECUTING = "EXECUTING"
  EVALUATING = "EVALUATING"
  COMPLETED = "COMPLETED"
  FAILED = "FAILED"
  CANCELLED = "CANCELLED"
  PAUSED = "PAUSED"


class RunSchema(pydantic.BaseModel):
  """Schema for a Test Run."""

  id: int
  test_suite_snapshot_id: int
  agent_id: int
  # Denormalized names for UI performance
  agent_name: str | None = None
  suite_name: str | None = None
  original_suite_id: int | None = None
  # What the agent's config was when the run started, so a later edit does
  # not change what an old run reads as.
  agent_context_snapshot: dict[str, Any] | None = None
  generate_suggestions: bool | None = False
  is_archived: bool = False

  status: RunStatus
  created_at: datetime.datetime
  # Null until a worker picks the run up.
  started_at: datetime.datetime | None = None
  completed_at: datetime.datetime | None = None
  concurrency: int = 2

  # Stats
  accuracy: float | None = None
  duration_ms: int | None = None
  tool_timings: dict[str, int] | None = None

  model_config = pydantic.ConfigDict(from_attributes=True)

  @pydantic.field_validator("concurrency", mode="before")
  @classmethod
  def validate_concurrency(cls, v: Any) -> int:
    """Handles None or missing concurrency for legacy runs."""
    if v is None:
      return 2
    return int(v)


class RunHistoryPoint(pydantic.BaseModel):
  """A point in run history."""

  created_at: datetime.datetime
  # Nullable, because a queued or cancelled run has scored nothing. Typed
  # float, the repository had to send 0.0 instead, and the agent list sparkline
  # plotted a run that never executed at 0% and turned the trend red. The
  # "Last eval" text on the same row was already showing "--" for it.
  accuracy: float | None
  run_id: int

  model_config = pydantic.ConfigDict(from_attributes=True)


class RunStatsSchema(pydantic.BaseModel):
  """Run with calculated stats."""

  run: RunSchema
  accuracy: float | None = None


class AssertionResult(pydantic.BaseModel):
  """Result of a single assertion evaluation."""

  assertion: Assertion
  passed: bool
  score: float
  reasoning: str | None = None
  error_message: str | None = None

  model_config = pydantic.ConfigDict(from_attributes=True)

  @pydantic.field_validator("assertion", mode="before")
  @classmethod
  def fix_legacy_assertion_type(cls, v: Any) -> Any:
    """Applies the same legacy repair Trial does for its suggestions."""
    return _repair_legacy_assertion(v) if v else v


class Trial(pydantic.BaseModel):
  """Schema for a single Trial (execution of an example)."""

  id: int
  run_id: int
  example_snapshot_id: int
  status: RunStatus
  agent_name: str | None = None
  question: str | None = None

  # Execution Result
  output_text: str | None = None
  duration_ms: int | None = None
  ttfr_ms: int | None = None
  error_message: str | None = None
  error_traceback: str | None = None
  failed_stage: str | None = None
  trace_results: list[dict[str, Any]] | None = None
  tool_timings: dict[str, int] | None = None

  # Scoring
  score: float | None = None
  assertion_results: list[AssertionResult] = pydantic.Field(
      default_factory=list
  )
  suggested_asserts: list[Assertion] | None = None

  created_at: datetime.datetime
  started_at: datetime.datetime | None = None
  completed_at: datetime.datetime | None = None

  model_config = pydantic.ConfigDict(from_attributes=True)

  @pydantic.field_validator("suggested_asserts", mode="before")
  @classmethod
  def fix_legacy_assertion_types(cls, v: Any) -> Any:
    """Fixes legacy assertion types and flattens SQLAlchemy models."""
    if not v:
      return v
    if isinstance(v, list):
      fixed_list = []
      for item in v:
        fixed = _repair_legacy_assertion(item)
        if not isinstance(fixed, dict):
          logger.warning("Failed to flatten suggestion item: %s", item)
        fixed_list.append(fixed)
      return fixed_list
    return v


class EphemeralTestResult(pydantic.BaseModel):
  """Result of an ephemeral test run."""

  passed: bool
  score: float | None = None
  duration_ms: int
  assertion_results: list[AssertionResult]
  response_text: str
  generated_sql: str
  trace: list[dict[str, Any]]
  error_message: str | None = None
