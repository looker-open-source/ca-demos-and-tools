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

"""Pydantic schemas for Timeline visualization."""

import datetime
from typing import Literal

import pydantic


class TimelineEvent(pydantic.BaseModel):
  """A single event in the timeline."""

  title: str
  content: str
  content_type: Literal["text", "json", "code", "sql", "python", "vegalite"] = (
      "text"
  )
  icon: str = "bi:circle"
  duration_ms: int = 0
  cumulative_duration_ms: int = 0
  timestamp: datetime.datetime | None = None
  group_title: str | None = None

  # For internal storage of original data if needed, but not sent to UI usually
  # metadata: dict[str, Any] = pydantic.Field(default_factory=dict)


class TimelineGroup(pydantic.BaseModel):
  """A group of adjacent events sharing a common theme or tool."""

  title: str
  duration_ms: int = 0
  icon: str = "bi:circle"
  events: list[TimelineEvent] = pydantic.Field(default_factory=list)


class Timeline(pydantic.BaseModel):
  """Timeline DTO containing all events and metadata."""

  total_duration_ms: int
  events: list[TimelineEvent] = pydantic.Field(default_factory=list)
  groups: list[TimelineGroup] = pydantic.Field(default_factory=list)
