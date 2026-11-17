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

"""Repository for managing Scheduled Evaluations."""

import datetime
import logging
from typing import Sequence

from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.models.schedule import EvalSchedule
from prism.server.repositories.run_repository import MAX_CONCURRENCY
import sqlalchemy
from sqlalchemy import orm

logger = logging.getLogger(__name__)

_ACTIVE_RUN_STATUSES = (
    RunStatus.PENDING,
    RunStatus.RUNNING,
    RunStatus.EXECUTING,
    RunStatus.EVALUATING,
    RunStatus.PAUSED,
)


class ScheduleRepository:
  """Persistence queries and row-locked due claiming for EvalSchedule."""

  def __init__(self, session: orm.Session):
    self.session = session

  def eager_options(self):
    """Eager loads related Agent, TestSuite, and latest Run rows."""
    return [
        orm.joinedload(EvalSchedule.agent),
        orm.joinedload(EvalSchedule.test_suite),
        orm.joinedload(EvalSchedule.last_run),
    ]

  def create(
      self,
      name: str,
      agent_id: int,
      test_suite_id: int,
      cadence: str,
      cron_expression: str,
      timezone: str = "UTC",
      generate_suggestions: bool = False,
      concurrency: int = 2,
      is_enabled: bool = True,
      next_run_at: datetime.datetime | None = None,
  ) -> EvalSchedule:
    """Creates a new EvalSchedule row."""
    requested = 2 if concurrency is None else int(concurrency)
    clamped = max(1, min(requested, MAX_CONCURRENCY))
    schedule = EvalSchedule(
        name=name,
        agent_id=agent_id,
        test_suite_id=test_suite_id,
        cadence=cadence,
        cron_expression=cron_expression,
        timezone=timezone,
        generate_suggestions=generate_suggestions,
        concurrency=clamped,
        is_enabled=is_enabled,
        next_run_at=next_run_at,
    )
    self.session.add(schedule)
    self.session.commit()
    loaded = self.get_by_id(schedule.id)
    assert loaded is not None
    return loaded

  def get_by_id(
      self, schedule_id: int, with_for_update: bool = False
  ) -> EvalSchedule | None:
    """Fetches a schedule by ID with eager relationships loaded."""
    stmt = (
        sqlalchemy.select(EvalSchedule)
        .options(*self.eager_options())
        .where(EvalSchedule.id == schedule_id)
    )
    if with_for_update:
      stmt = stmt.with_for_update(of=EvalSchedule)
    return self.session.scalars(stmt).unique().first()

  def list_all(
      self,
      agent_id: int | None = None,
      test_suite_id: int | None = None,
      is_enabled: bool | None = None,
      include_archived: bool = False,
  ) -> Sequence[EvalSchedule]:
    """Lists schedules ordered by enabled status and next run time."""
    stmt = sqlalchemy.select(EvalSchedule).options(*self.eager_options())

    if not include_archived:
      stmt = stmt.where(EvalSchedule.is_archived.is_not(True))
    if agent_id is not None:
      stmt = stmt.where(EvalSchedule.agent_id == agent_id)
    if test_suite_id is not None:
      stmt = stmt.where(EvalSchedule.test_suite_id == test_suite_id)
    if is_enabled is not None:
      stmt = stmt.where(EvalSchedule.is_enabled.is_(is_enabled))

    stmt = stmt.order_by(
        EvalSchedule.is_archived.asc(),
        EvalSchedule.is_enabled.desc(),
        EvalSchedule.next_run_at.asc().nulls_last(),
        EvalSchedule.created_at.desc(),
    )
    return self.session.scalars(stmt).unique().all()

  def save(self, schedule: EvalSchedule) -> EvalSchedule:
    """Commits modifications to a schedule and reloads eager relations."""
    if schedule.concurrency is not None:
      schedule.concurrency = max(
          1, min(int(schedule.concurrency), MAX_CONCURRENCY)
      )
    self.session.commit()
    loaded = self.get_by_id(schedule.id)
    assert loaded is not None
    return loaded

  def has_active_run(self, schedule_id: int) -> bool:
    """Returns True if any non-archived run for this schedule is still active."""
    stmt = (
        sqlalchemy.select(Run.id)
        .where(Run.schedule_id == schedule_id)
        .where(Run.is_archived.is_not(True))
        .where(Run.status.in_(_ACTIVE_RUN_STATUSES))
        .limit(1)
    )
    return self.session.scalars(stmt).first() is not None

  def claim_next_due_schedule(
      self, now: datetime.datetime
  ) -> EvalSchedule | None:
    """Locks and returns the oldest due active schedule using SKIP LOCKED."""
    stmt = (
        sqlalchemy.select(EvalSchedule)
        .where(EvalSchedule.is_enabled.is_(True))
        .where(EvalSchedule.is_archived.is_not(True))
        .where(EvalSchedule.next_run_at.is_not(None))
        .where(EvalSchedule.next_run_at <= now)
        .order_by(EvalSchedule.next_run_at.asc(), EvalSchedule.id.asc())
        .limit(1)
        .with_for_update(of=EvalSchedule, skip_locked=True)
    )
    return self.session.scalars(stmt).first()
