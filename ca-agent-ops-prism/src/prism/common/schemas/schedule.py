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

"""Pydantic schemas for Scheduled Evaluations."""

import datetime
import enum

from prism.common import cron
from prism.common.schemas.execution import RunStatus
import pydantic

# Matches RunRepository.MAX_CONCURRENCY without importing prism.server.
MAX_SCHEDULE_CONCURRENCY = 16

# Left in last_error_message when a due tick is skipped, so the UI can tell a
# skip apart from a failed dispatch. A tick is skipped while a run is active or
# another dispatch still holds the schedule's claim.
SKIPPED_ACTIVE_RUN_MESSAGE = (
    "Skipped: another run or dispatch was still active."
)


class ScheduleCadence(str, enum.Enum):
  """Supported UI cadence presets and custom cron mode."""

  HOURLY = "HOURLY"
  DAILY = "DAILY"
  WEEKLY = "WEEKLY"
  CUSTOM = "CUSTOM"


class ScheduleCreate(pydantic.BaseModel):
  """Payload for creating a new evaluation schedule."""

  name: str = pydantic.Field(min_length=1, max_length=200)
  agent_id: int
  test_suite_id: int
  cadence: ScheduleCadence = ScheduleCadence.DAILY
  cron_expression: str = "0 9 * * *"
  timezone: str = "UTC"
  generate_suggestions: bool = False
  concurrency: int = pydantic.Field(
      default=2, ge=1, le=MAX_SCHEDULE_CONCURRENCY
  )
  is_enabled: bool = True

  @pydantic.field_validator("name")
  @classmethod
  def validate_name(cls, v: str) -> str:
    cleaned = v.strip()
    if not cleaned:
      raise ValueError("Schedule name cannot be blank.")
    return cleaned

  @pydantic.field_validator("cron_expression")
  @classmethod
  def validate_cron(cls, v: str) -> str:
    return cron.validate_cron_expression(v)

  @pydantic.field_validator("timezone")
  @classmethod
  def validate_tz(cls, v: str) -> str:
    cleaned = v.strip()
    cron.validate_timezone(cleaned)
    return cleaned


class ScheduleUpdate(pydantic.BaseModel):
  """Payload for updating an existing evaluation schedule."""

  name: str | None = pydantic.Field(default=None, min_length=1, max_length=200)
  agent_id: int | None = None
  test_suite_id: int | None = None
  cadence: ScheduleCadence | None = None
  cron_expression: str | None = None
  timezone: str | None = None
  generate_suggestions: bool | None = None
  concurrency: int | None = pydantic.Field(
      default=None, ge=1, le=MAX_SCHEDULE_CONCURRENCY
  )
  is_enabled: bool | None = None

  @pydantic.field_validator("name")
  @classmethod
  def validate_name(cls, v: str | None) -> str | None:
    if v is None:
      return None
    cleaned = v.strip()
    if not cleaned:
      raise ValueError("Schedule name cannot be blank.")
    return cleaned

  @pydantic.field_validator("cron_expression")
  @classmethod
  def validate_cron(cls, v: str | None) -> str | None:
    if v is None:
      return None
    return cron.validate_cron_expression(v)

  @pydantic.field_validator("timezone")
  @classmethod
  def validate_tz(cls, v: str | None) -> str | None:
    if v is None:
      return None
    cleaned = v.strip()
    cron.validate_timezone(cleaned)
    return cleaned


class ScheduleSchema(pydantic.BaseModel):
  """Read schema for an evaluation schedule."""

  id: int
  name: str
  agent_id: int
  test_suite_id: int
  agent_name: str | None = None
  suite_name: str | None = None
  cadence: ScheduleCadence
  cron_expression: str
  timezone: str
  generate_suggestions: bool = False
  concurrency: int = 2
  is_enabled: bool = True
  is_archived: bool = False

  next_run_at: datetime.datetime | None = None
  last_run_at: datetime.datetime | None = None
  last_run_id: int | None = None
  last_run_status: RunStatus | None = None
  last_error_message: str | None = None

  created_at: datetime.datetime
  modified_at: datetime.datetime

  model_config = pydantic.ConfigDict(from_attributes=True)


class ScheduleTickResult(pydantic.BaseModel):
  """Summary of a scheduler due-check pass."""

  checked_at: datetime.datetime
  triggered_run_ids: list[int] = pydantic.Field(default_factory=list)
  skipped_overlap_schedule_ids: list[int] = pydantic.Field(default_factory=list)
  failed_schedule_ids: list[int] = pydantic.Field(default_factory=list)
