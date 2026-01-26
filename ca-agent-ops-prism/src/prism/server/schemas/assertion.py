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

"""Pydantic schemas for the Assertion entity."""

import enum
from typing import Any, Literal, Union

import pydantic


class AssertionType(str, enum.Enum):
  """Enumeration of all supported assert types."""

  # Data
  DATA_CHECK_ROW = "data-check-row"
  DATA_CHECK_ROW_COUNT = "data-check-row-count"
  # Query
  QUERY_CONTAINS = "query-contains"
  # Text
  TEXT_CONTAINS = "text-contains"
  # Chart
  CHART_CHECK_TYPE = "chart-check-type"
  # Workflow
  LATENCY_MAX_MS = "latency-max-ms"
  # Looker
  LOOKER_QUERY_MATCH = "looker-query-match"


class AssertionSchema(pydantic.BaseModel):
  """Base schema for assertion logic (no ID)."""

  model_config = pydantic.ConfigDict(extra="forbid")

  weight: float = 1.0


class BaseAssertion(AssertionSchema):
  """Base schema for persisted assertions (with ID)."""

  id: int | None = None


# --- Specific Assertion Types (Schema Only) ---


class TextContainsSchema(AssertionSchema):
  """Checks if the result text contains a value."""

  type: Literal[AssertionType.TEXT_CONTAINS] = AssertionType.TEXT_CONTAINS
  value: str = pydantic.Field(min_length=1)


class QueryContainsSchema(AssertionSchema):
  """Checks if the generated query contains a value."""

  type: Literal[AssertionType.QUERY_CONTAINS] = AssertionType.QUERY_CONTAINS
  value: str = pydantic.Field(min_length=1)


class ChartCheckTypeSchema(AssertionSchema):
  """Checks if the chart type matches."""

  type: Literal[AssertionType.CHART_CHECK_TYPE] = AssertionType.CHART_CHECK_TYPE
  value: str = pydantic.Field(min_length=1)


class LatencyMaxMsSchema(AssertionSchema):
  """Checks if latency is below a threshold."""

  type: Literal[AssertionType.LATENCY_MAX_MS] = AssertionType.LATENCY_MAX_MS
  value: float


class DataCheckRowCountSchema(AssertionSchema):
  """Checks the number of rows in the result."""

  type: Literal[AssertionType.DATA_CHECK_ROW_COUNT] = (
      AssertionType.DATA_CHECK_ROW_COUNT
  )
  value: int


class DataCheckRowSchema(AssertionSchema):
  """Checks if a row with specific column values exists."""

  type: Literal[AssertionType.DATA_CHECK_ROW] = AssertionType.DATA_CHECK_ROW
  columns: dict[str, Any] = pydantic.Field(min_length=1)


class LookerFilterSchema(pydantic.BaseModel):
  """Single Looker filter."""

  field: str
  value: str | int


class LookerQuerySchema(pydantic.BaseModel):
  """Structured Looker query parameters."""

  model_config = pydantic.ConfigDict(extra="forbid")

  model: str | None = None
  explore: str | None = None
  fields: list[str] | None = None
  filters: list[LookerFilterSchema] | None = None
  sorts: list[str] | None = None
  limit: str | int | None = None

  @pydantic.model_validator(mode="after")
  def check_not_empty(self) -> "LookerQuerySchema":
    if not any([
        self.model,
        self.explore,
        self.fields,
        self.filters,
        self.sorts,
        self.limit,
    ]):
      raise ValueError("Looker query parameters cannot be all empty")
    return self


class LookerQueryMatchSchema(AssertionSchema):
  """Checks if a Looker query matches parameters (structured params)."""

  type: Literal[AssertionType.LOOKER_QUERY_MATCH] = (
      AssertionType.LOOKER_QUERY_MATCH
  )
  params: LookerQuerySchema


# --- Persisted Versions (Inherit from Schema + BaseAssertion) ---


class TextContains(TextContainsSchema, BaseAssertion):
  pass


class QueryContains(QueryContainsSchema, BaseAssertion):
  pass


class ChartCheckType(ChartCheckTypeSchema, BaseAssertion):
  pass


class LatencyMaxMs(LatencyMaxMsSchema, BaseAssertion):
  pass


class DataCheckRowCount(DataCheckRowCountSchema, BaseAssertion):
  pass


class DataCheckRow(DataCheckRowSchema, BaseAssertion):
  pass


class LookerQueryMatch(LookerQueryMatchSchema, BaseAssertion):
  pass


# Discriminated Unions

# Using schemas for Generation
AssertionRequest = Union[
    TextContainsSchema,
    QueryContainsSchema,
    ChartCheckTypeSchema,
    LatencyMaxMsSchema,
    DataCheckRowCountSchema,
    DataCheckRowSchema,
    LookerQueryMatchSchema,
]

# Using persisted models for Storage/API
Assertion = Union[
    TextContains,
    QueryContains,
    ChartCheckType,
    LatencyMaxMs,
    DataCheckRowCount,
    DataCheckRow,
    LookerQueryMatch,
]
