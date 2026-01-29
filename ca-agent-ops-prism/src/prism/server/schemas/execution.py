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
from typing import Any

from prism.server.schemas.assertion import Assertion
import pydantic


class RunStatus(str, enum.Enum):
  """Status of an Execution Run."""

  PENDING = "PENDING"
  RUNNING = "RUNNING"
  EXECUTING = "EXECUTING"
  EVALUATING = "EVALUATING"
  COMPLETED = "COMPLETED"
  FAILED = "FAILED"
  CANCELLED = "CANCELLED"


class RunSchema(pydantic.BaseModel):
  """Schema for a Test Run."""

  id: int
  test_suite_snapshot_id: int
  agent_id: int
  # Snapshot of the agent's context at the time of the run
  agent_context_snapshot: dict[str, Any] | None = None

  status: RunStatus
  created_at: datetime.datetime
  completed_at: datetime.datetime | None = None

  # Stats
  total_examples: int = 0
  failed_examples: int = 0
  accuracy: float | None = None

  model_config = pydantic.ConfigDict(from_attributes=True)


class AssertionResult(pydantic.BaseModel):
  """Result of a single assertion evaluation."""

  assertion: Assertion
  passed: bool
  score: float
  reason: str | None = None
  error_message: str | None = None

  model_config = pydantic.ConfigDict(from_attributes=True)


class Trial(pydantic.BaseModel):
  """Schema for a single Trial (execution of an example)."""

  id: int
  run_id: int
  example_snapshot_id: int
  status: RunStatus

  # Execution Result
  output_text: str | None = None
  error_message: str | None = None
  error_traceback: str | None = None
  failed_stage: str | None = None
  trace_results: list[dict[str, Any]] | None = None

  # Scoring
  score: float | None = None
  assertion_results: list[AssertionResult] = pydantic.Field(
      default_factory=list
  )
  suggested_asserts: list[Assertion] | None = None

  @pydantic.field_validator("suggested_asserts", mode="before")
  @classmethod
  def fix_legacy_assertion_types(cls, v: Any) -> Any:
    """Fixes legacy assertion types in suggested assertions."""
    if not v:
      return v
    if isinstance(v, list):
      fixed_list = []
      for item in v:
        if isinstance(item, dict):
          # Fix "contains" -> "text-contains"
          if item.get("type") == "contains":
            item = item.copy()  # Don't mutate original if possible
            item["type"] = "text-contains"
        fixed_list.append(item)
      return fixed_list
    return v

  created_at: datetime.datetime
  completed_at: datetime.datetime | None = None

  model_config = pydantic.ConfigDict(from_attributes=True)


class AdHocRunRequest(pydantic.BaseModel):
  """Request schema for running an ad-hoc test."""

  agent_id: int
  question: str
  asserts: list[Assertion] | None = None


class EphemeralTestResult(pydantic.BaseModel):
  """Result of an ephemeral test run."""

  passed: bool
  score: float | None = None
  latency_ms: int
  assertion_results: list[AssertionResult]
  response_text: str
  generated_sql: str
  trace: list[dict[str, Any]]
  error_message: str | None = None
