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

"""Pydantic schemas for the Example entity."""

import datetime

from prism.server.schemas.assertion import Assertion
import pydantic


class ExampleCreate(pydantic.BaseModel):
  """Schema for creating a new Example."""

  test_suite_id: int
  logical_id: str | None = None  # Optional, can be auto-generated
  question: str = pydantic.Field(..., description="The input question")
  asserts: list[Assertion] = pydantic.Field(
      default_factory=list, description="List of assert definitions"
  )


class ExampleUpdate(pydantic.BaseModel):
  """Schema for updating an existing Example."""

  question: str | None = None
  asserts: list[Assertion] | None = None


class Example(ExampleCreate):
  """Schema for a persisted Example."""

  id: int
  logical_id: str
  created_at: datetime.datetime
  modified_at: datetime.datetime | None = None
  is_archived: bool = False

  model_config = pydantic.ConfigDict(from_attributes=True)
