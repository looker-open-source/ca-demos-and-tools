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

"""Pydantic schemas for the Test Suite entity."""

import datetime

from prism.common.schemas.example import Example
import pydantic


class SuiteCreate(pydantic.BaseModel):
  """Schema for creating a new Test Suite."""

  name: str = pydantic.Field(..., description="Unique name of the suite")
  description: str | None = None
  tags: dict[str, str] = pydantic.Field(
      default_factory=dict, description="Metadata tags"
  )


class SuiteUpdate(pydantic.BaseModel):
  """Schema for updating an existing Test Suite."""

  name: str | None = None
  description: str | None = None
  tags: dict[str, str] | None = None


class Suite(SuiteCreate):
  """Schema for a persisted Test Suite."""

  id: int
  created_at: datetime.datetime
  modified_at: datetime.datetime | None = None
  is_archived: bool = False

  model_config = pydantic.ConfigDict(from_attributes=True)


class SuiteWithStats(pydantic.BaseModel):
  """Suite data with associated statistics."""

  suite: Suite
  question_count: int
  run_count: int
  assertion_coverage: float = 0.0


class SuiteDetail(Suite):
  """Suite data including full examples list."""

  examples: list[Example] = []


class TestSuiteSnapshotSchema(pydantic.BaseModel):
  """Schema for a Test Suite snapshot."""

  id: int
  original_suite_id: int | None = None
  name: str
  description: str | None = None
  tags: dict[str, str] = pydantic.Field(default_factory=dict)
  created_at: datetime.datetime

  model_config = pydantic.ConfigDict(from_attributes=True)
