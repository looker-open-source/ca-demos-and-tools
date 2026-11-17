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

"""Schedules Client implementation for managing Scheduled Evaluations."""

import datetime
from typing import Any

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common import cron
from prism.common.schemas import execution as execution_schemas
from prism.common.schemas import schedule as schedule_schemas
from prism.server.services.schedule_service import ScheduleService


def _map_schedule(model: Any) -> schedule_schemas.ScheduleSchema:
  """Converts an EvalSchedule ORM instance to ScheduleSchema."""
  return schedule_schemas.ScheduleSchema.model_validate(model)


class SchedulesClient:
  """Client facade for Scheduled Evaluations."""

  @inject
  def list_schedules(
      self,
      agent_id: int | None = None,
      test_suite_id: int | None = None,
      is_enabled: bool | None = None,
      include_archived: bool = False,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> list[schedule_schemas.ScheduleSchema]:
    """Lists evaluation schedules matching optional filters."""
    models = service.list_schedules(
        agent_id=agent_id,
        test_suite_id=test_suite_id,
        is_enabled=is_enabled,
        include_archived=include_archived,
    )
    return [_map_schedule(m) for m in models]

  @inject
  def get_schedule(
      self,
      schedule_id: int,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema | None:
    """Gets a single evaluation schedule by ID."""
    model = service.get_schedule(schedule_id)
    return _map_schedule(model) if model else None

  @inject
  def create_schedule(
      self,
      payload: schedule_schemas.ScheduleCreate,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema:
    """Creates a new evaluation schedule."""
    model = service.create_schedule(payload)
    return _map_schedule(model)

  @inject
  def update_schedule(
      self,
      schedule_id: int,
      payload: schedule_schemas.ScheduleUpdate,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema:
    """Updates an existing evaluation schedule."""
    model = service.update_schedule(schedule_id, payload)
    return _map_schedule(model)

  @inject
  def pause_schedule(
      self,
      schedule_id: int,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema:
    """Pauses an active evaluation schedule."""
    model = service.pause_schedule(schedule_id)
    return _map_schedule(model)

  @inject
  def resume_schedule(
      self,
      schedule_id: int,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema:
    """Resumes a paused evaluation schedule."""
    model = service.resume_schedule(schedule_id)
    return _map_schedule(model)

  @inject
  def archive_schedule(
      self,
      schedule_id: int,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema:
    """Archives an evaluation schedule."""
    model = service.archive_schedule(schedule_id)
    return _map_schedule(model)

  @inject
  def unarchive_schedule(
      self,
      schedule_id: int,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleSchema:
    """Restores an archived evaluation schedule in a paused state."""
    model = service.unarchive_schedule(schedule_id)
    return _map_schedule(model)

  @inject
  def trigger_schedule_now(
      self,
      schedule_id: int,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> execution_schemas.RunSchema:
    """Triggers an immediate evaluation run for `schedule_id`."""
    run = service.trigger_schedule_now(schedule_id)
    return execution_schemas.RunSchema.model_validate(run)

  @inject
  def process_due_schedules(
      self,
      now: datetime.datetime | None = None,
      limit: int = 20,
      service: ScheduleService = Depends(dependencies.get_schedule_service),
  ) -> schedule_schemas.ScheduleTickResult:
    """Claims due schedules and queues evaluation runs."""
    return service.process_due_schedules(now=now, limit=limit)

  def preview_next_runs(
      self,
      cron_expression: str,
      timezone: str = "UTC",
      count: int = 3,
      after: datetime.datetime | None = None,
  ) -> list[datetime.datetime]:
    """Returns upcoming UTC execution timestamps for a cron expression."""
    return cron.preview_next_runs(
        cron_expression, tz_name=timezone, count=count, after=after
    )
