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

"""Pydantic schemas for Run Comparison."""

import enum
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import Trial
import pydantic


class ComparisonStatus(str, enum.Enum):
  """Status of a comparison case."""

  REGRESSION = "REGRESSION"
  IMPROVED = "IMPROVED"
  STABLE = "STABLE"
  NEW = "NEW"  # Only in challenger
  REMOVED = "REMOVED"  # Only in base
  ERROR = "ERROR"  # Error in challenger (maybe base was success)


class ComparisonCase(pydantic.BaseModel):
  """A single case comparison (Row in the UI)."""

  logical_id: str
  question: str

  # Trials (Optional because might be NEW or REMOVED)
  base_trial: Trial | None = None
  challenger_trial: Trial | None = None

  # Deltas
  score_delta: float | None = None
  duration_delta: int | None = None

  status: ComparisonStatus

  model_config = pydantic.ConfigDict(from_attributes=True)


class ComparisonDelta(pydantic.BaseModel):
  """Overall delta summary."""

  accuracy_delta: float = 0.0
  duration_delta_avg: float = 0.0
  regressions_count: int = 0
  improvements_count: int = 0
  same_count: int = 0
  errors_count: int = 0


class RunComparisonMetadata(pydantic.BaseModel):
  """Metadata for the comparison report."""

  base_run_id: int
  challenger_run_id: int
  total_cases: int


class RunComparison(pydantic.BaseModel):
  """Full comparison report object."""

  base_run: RunSchema
  challenger_run: RunSchema
  metadata: RunComparisonMetadata
  delta: ComparisonDelta
  cases: list[ComparisonCase]
