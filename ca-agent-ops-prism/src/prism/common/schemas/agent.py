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

"""Pydantic schemas for the Agent entity."""

import datetime
import enum
from typing import Union

import pydantic


class BigQueryConfig(pydantic.BaseModel):
  """Configuration for BigQuery datasource."""

  tables: list[str]


class LookerConfig(pydantic.BaseModel):
  """Configuration for Looker datasource."""

  instance_uri: str
  explores: list[str]


class AgentConfig(pydantic.BaseModel):
  """Configuration for an Agent."""

  project_id: str | None = None
  location: str | None = None
  agent_resource_id: str | None = None
  datasource: Union[BigQueryConfig, LookerConfig, None] = None
  system_instruction: str | None = None
  looker_client_id: str | None = None
  looker_client_secret: str | None = None


class AgentBase(pydantic.BaseModel):
  """Base schema for Agent data."""

  name: str = pydantic.Field(..., description="Display name of the agent")
  config: AgentConfig | None = pydantic.Field(
      default_factory=AgentConfig, description="Configuration details"
  )


class AgentCreate(AgentBase):
  """Schema for creating a new Agent."""


class AgentUpdate(pydantic.BaseModel):
  """Schema for updating an existing Agent."""

  name: str | None = None
  config: AgentConfig | None = None


class Agent(AgentBase):
  """Schema for a persisted Agent."""

  id: int
  created_at: datetime.datetime
  modified_at: datetime.datetime | None = None
  is_archived: bool = False

  model_config = pydantic.ConfigDict(from_attributes=True)


class UniqueDatasources(pydantic.BaseModel):
  """Unique datasource names grouped by type."""

  bq: list[str]
  looker: list[str]
