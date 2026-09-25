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
import re
from typing import Annotated, Any, Literal, Union

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
  DURATION_MAX_MS = "duration-max-ms"
  LATENCY_MAX_MS = "latency-max-ms"  # Deprecated: Use duration-max-ms
  # Looker
  LOOKER_QUERY_MATCH = "looker-query-match"
  # AI
  AI_JUDGE = "ai-judge"


class MatchMode(str, enum.Enum):
  """How a contains assertion compares its value against the trace."""

  CONTAINS = "contains"
  REGEX = "regex"


class AssertionSchema(pydantic.BaseModel):
  """Base schema for assertion logic (no ID)."""

  model_config = pydantic.ConfigDict(extra="forbid", from_attributes=True)

  weight: float = 1.0

  @pydantic.model_validator(mode="before")
  @classmethod
  def flatten_params(cls, data: Any) -> Any:
    """Flattens the 'params' field from SQLAlchemy objects if present."""
    if hasattr(data, "params") and isinstance(data.params, dict):
      data_dict = {**data.params, "type": data.type, "weight": data.weight}
      # A column wins over the params copy of the same name. add_assertion
      # dumps the whole schema into params, so a snapshot's params carry the
      # live row's original_assertion_id, which is always None. Spreading
      # params last overwrote the real one and every snapshot came back
      # unlinked. Only override from a column that exists: the live Assertion
      # has no original_assertion_id or reasoning, and there params is the
      # only copy.
      for name in ("id", "original_assertion_id", "reasoning"):
        if hasattr(data, name):
          data_dict[name] = getattr(data, name)
      return data_dict
    return data


class BaseAssertion(AssertionSchema):
  """Base schema for persisted assertions (with ID)."""

  id: int | None = None
  original_assertion_id: int | None = None
  reasoning: str | None = None


class ContainsSchema(AssertionSchema):
  """Shared shape of the two substring assertions."""

  value: str = pydantic.Field(min_length=1)
  mode: MatchMode = MatchMode.CONTAINS

  @pydantic.model_validator(mode="after")
  def check_pattern_compiles(self) -> "ContainsSchema":
    """Rejects a broken pattern here, so the run does not carry it."""
    if self.mode == MatchMode.REGEX:
      try:
        re.compile(self.value)
      except re.error as e:
        raise ValueError(f"Invalid regular expression: {e}") from e
    return self


class TextContainsSchema(ContainsSchema):
  """Checks if the result text contains a value."""

  type: Literal[AssertionType.TEXT_CONTAINS] = AssertionType.TEXT_CONTAINS


class QueryContainsSchema(ContainsSchema):
  """Checks if the generated query contains a value."""

  type: Literal[AssertionType.QUERY_CONTAINS] = AssertionType.QUERY_CONTAINS


class ChartCheckTypeSchema(AssertionSchema):
  """Checks if the chart type matches."""

  type: Literal[AssertionType.CHART_CHECK_TYPE] = AssertionType.CHART_CHECK_TYPE
  value: str = pydantic.Field(min_length=1)


class DurationMaxMsSchema(AssertionSchema):
  """Checks if duration is below a threshold."""

  type: Literal[AssertionType.DURATION_MAX_MS] = AssertionType.DURATION_MAX_MS
  value: float


class LatencyMaxMsSchema(AssertionSchema):
  """Checks if latency is below a threshold (Deprecated)."""

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


class AIJudgeSchema(AssertionSchema):
  """Evaluates the response using an LLM based on criteria."""

  type: Literal[AssertionType.AI_JUDGE] = AssertionType.AI_JUDGE
  value: str = pydantic.Field(min_length=1)


class TextContains(TextContainsSchema, BaseAssertion):
  pass


class QueryContains(QueryContainsSchema, BaseAssertion):
  pass


class ChartCheckType(ChartCheckTypeSchema, BaseAssertion):
  pass


class DurationMaxMs(DurationMaxMsSchema, BaseAssertion):
  pass


class LatencyMaxMs(LatencyMaxMsSchema, BaseAssertion):
  pass


class DataCheckRowCount(DataCheckRowCountSchema, BaseAssertion):
  pass


class DataCheckRow(DataCheckRowSchema, BaseAssertion):
  pass


class LookerQueryMatch(LookerQueryMatchSchema, BaseAssertion):
  pass


class AIJudge(AIJudgeSchema, BaseAssertion):
  pass


# Schemas, for generating new assertions.
AssertionRequest = Annotated[
    Union[
        TextContainsSchema,
        QueryContainsSchema,
        ChartCheckTypeSchema,
        DurationMaxMsSchema,
        LatencyMaxMsSchema,
        DataCheckRowCountSchema,
        DataCheckRowSchema,
        LookerQueryMatchSchema,
        AIJudgeSchema,
    ],
    pydantic.Discriminator("type"),
]

# Persisted models, for storage and the API.
Assertion = Annotated[
    Union[
        TextContains,
        QueryContains,
        ChartCheckType,
        DurationMaxMs,
        LatencyMaxMs,
        DataCheckRowCount,
        DataCheckRow,
        LookerQueryMatch,
        AIJudge,
    ],
    pydantic.Discriminator("type"),
]
