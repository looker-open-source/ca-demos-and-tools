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

"""Service layer for managing and dispatching Scheduled Evaluations."""

import datetime
import logging
import uuid

from prism.common import cron
from prism.common.schemas.schedule import ScheduleCreate
from prism.common.schemas.schedule import ScheduleTickResult
from prism.common.schemas.schedule import ScheduleUpdate
from prism.common.schemas.schedule import SKIPPED_ACTIVE_RUN_MESSAGE
from prism.server.models.run import Run
from prism.server.models.schedule import EvalSchedule
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.schedule_repository import ScheduleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import displayable_error
from prism.server.services.execution_service import ExecutionService
from sqlalchemy import orm

logger = logging.getLogger(__name__)

# How long a dispatch claim blocks other dispatches. It only has to outlast
# create_run, which is a snapshot plus one get_agent_context call, so it relies
# on that call's client deadline being well under this. A process that dies
# mid-dispatch leaves the claim behind, and due ticks inside this window are
# skipped like ticks that overlap an active run.
_DISPATCH_CLAIM_TTL = datetime.timedelta(minutes=10)


def _utc_now(now: datetime.datetime | None = None) -> datetime.datetime:
  if now is None:
    return datetime.datetime.now(datetime.timezone.utc)
  if now.tzinfo is None:
    return now.replace(tzinfo=datetime.timezone.utc)
  return now.astimezone(datetime.timezone.utc)


class ScheduleService:
  """Coordinates schedule lifecycle, overlap protection, and due ticks."""

  def __init__(
      self,
      session: orm.Session,
      schedule_repository: ScheduleRepository,
      execution_service: ExecutionService,
  ):
    self.session = session
    self.schedule_repository = schedule_repository
    self.execution_service = execution_service
    self.agent_repository = AgentRepository(session)
    self.suite_repository = SuiteRepository(session)

  def _validate_targets(self, agent_id: int, test_suite_id: int) -> None:
    """Verifies the target agent and suite exist, are unarchived, and non-empty."""
    agent = self.agent_repository.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found.")
    if agent.is_archived:
      raise ValueError(
          f"Agent '{agent.name}' is archived. Restore it before scheduling."
      )

    ds = agent.datasource_config or {}
    if isinstance(ds, dict) and (
        "instance_uri" in ds or "looker_instance_uri" in ds
    ):
      if not (agent.looker_client_id and agent.looker_client_secret):
        raise ValueError(
            "Looker datasource requires Looker Client ID and Secret. "
            "Edit the agent to provide them."
        )

    suite = self.suite_repository.get_by_id(test_suite_id)
    if not suite:
      raise ValueError(f"Test suite with id {test_suite_id} not found.")
    if suite.is_archived:
      raise ValueError(
          f"Test suite '{suite.name}' is archived. Restore it before"
          " scheduling."
      )

    active_examples = [e for e in suite.examples if not e.is_archived]
    if not active_examples:
      raise ValueError(
          f"Test suite '{suite.name}' has no active questions. Add a question"
          " first."
      )

  def _dispatch_blocked(
      self, schedule: EvalSchedule, current: datetime.datetime
  ) -> bool:
    """True if a run is active or another dispatch holds a live claim.

    Call with the schedule row locked, so the check and the claim that follows
    it are one step for every other dispatcher.

    Args:
      schedule: The locked schedule row.
      current: The UTC time the claim's age is measured against.

    Returns:
      Whether this dispatch has to be refused or skipped.
    """
    claim = schedule.dispatch_started_at
    if claim is not None and current - claim < _DISPATCH_CLAIM_TTL:
      return True
    return self.schedule_repository.has_active_run(schedule.id)

  def _release_failed_claim(self, schedule_id: int) -> EvalSchedule | None:
    """Rolls back a failed dispatch and clears its claim under a fresh lock.

    Args:
      schedule_id: The schedule whose dispatch failed.

    Returns:
      The re-locked schedule, or None if it was deleted meanwhile.
    """
    self.session.rollback()
    locked = self.session.get(EvalSchedule, schedule_id, with_for_update=True)
    if locked is not None:
      locked.dispatch_started_at = None
    return locked

  def create_schedule(
      self,
      payload: ScheduleCreate,
      now: datetime.datetime | None = None,
  ) -> EvalSchedule:
    """Creates a validated evaluation schedule and computes next_run_at."""
    current = _utc_now(now)
    self._validate_targets(payload.agent_id, payload.test_suite_id)

    next_run = None
    if payload.is_enabled:
      next_run = cron.next_run_time(
          payload.cron_expression, tz_name=payload.timezone, after=current
      )
    return self.schedule_repository.create(
        name=payload.name,
        agent_id=payload.agent_id,
        test_suite_id=payload.test_suite_id,
        cadence=payload.cadence.value,
        cron_expression=payload.cron_expression,
        timezone=payload.timezone,
        generate_suggestions=payload.generate_suggestions,
        concurrency=payload.concurrency,
        is_enabled=payload.is_enabled,
        next_run_at=next_run,
    )

  def get_schedule(self, schedule_id: int) -> EvalSchedule | None:
    """Returns a schedule by ID, or None if not found."""
    return self.schedule_repository.get_by_id(schedule_id)

  def list_schedules(
      self,
      agent_id: int | None = None,
      test_suite_id: int | None = None,
      is_enabled: bool | None = None,
      include_archived: bool = False,
  ) -> list[EvalSchedule]:
    """Lists schedules matching the supplied filters."""
    return list(
        self.schedule_repository.list_all(
            agent_id=agent_id,
            test_suite_id=test_suite_id,
            is_enabled=is_enabled,
            include_archived=include_archived,
        )
    )

  def update_schedule(
      self,
      schedule_id: int,
      payload: ScheduleUpdate,
      now: datetime.datetime | None = None,
  ) -> EvalSchedule:
    """Updates an existing schedule and recalculates next_run_at when needed."""
    schedule = self.schedule_repository.get_by_id(schedule_id)
    if not schedule:
      raise ValueError(f"Schedule with id {schedule_id} not found.")
    if schedule.is_archived:
      raise ValueError(
          f"Schedule '{schedule.name}' is archived. Restore it before editing."
      )

    new_agent_id = (
        payload.agent_id if payload.agent_id is not None else schedule.agent_id
    )
    new_suite_id = (
        payload.test_suite_id
        if payload.test_suite_id is not None
        else schedule.test_suite_id
    )
    # Only when the edit could start runs against something new. Checked on
    # every edit, a suite archived after the schedule was made left no way to
    # rename the schedule or switch it off through Edit.
    targets_changed = (new_agent_id, new_suite_id) != (
        schedule.agent_id,
        schedule.test_suite_id,
    )
    enabling = bool(payload.is_enabled) and not schedule.is_enabled
    if targets_changed or enabling:
      self._validate_targets(new_agent_id, new_suite_id)

    if payload.name is not None:
      schedule.name = payload.name
    schedule.agent_id = new_agent_id
    schedule.test_suite_id = new_suite_id
    if payload.cadence is not None:
      schedule.cadence = payload.cadence.value

    timing_changed = False
    if (
        payload.cron_expression is not None
        and payload.cron_expression != schedule.cron_expression
    ):
      schedule.cron_expression = payload.cron_expression
      timing_changed = True
    if payload.timezone is not None and payload.timezone != schedule.timezone:
      schedule.timezone = payload.timezone
      timing_changed = True
    if payload.generate_suggestions is not None:
      schedule.generate_suggestions = payload.generate_suggestions
    if payload.concurrency is not None:
      schedule.concurrency = payload.concurrency

    current = _utc_now(now)
    if payload.is_enabled is not None:
      was_enabled = schedule.is_enabled
      schedule.is_enabled = payload.is_enabled
      if not schedule.is_enabled:
        schedule.next_run_at = None
      elif not was_enabled or timing_changed or schedule.next_run_at is None:
        schedule.next_run_at = cron.next_run_time(
            schedule.cron_expression,
            tz_name=schedule.timezone,
            after=current,
        )
    elif schedule.is_enabled and (
        timing_changed or schedule.next_run_at is None
    ):
      schedule.next_run_at = cron.next_run_time(
          schedule.cron_expression,
          tz_name=schedule.timezone,
          after=current,
      )

    schedule.last_error_message = None
    return self.schedule_repository.save(schedule)

  def pause_schedule(self, schedule_id: int) -> EvalSchedule:
    """Pauses a schedule and clears next_run_at."""
    schedule = self.schedule_repository.get_by_id(schedule_id)
    if not schedule:
      raise ValueError(f"Schedule with id {schedule_id} not found.")
    if schedule.is_archived:
      raise ValueError("Cannot pause an archived schedule.")
    schedule.is_enabled = False
    schedule.next_run_at = None
    return self.schedule_repository.save(schedule)

  def resume_schedule(
      self, schedule_id: int, now: datetime.datetime | None = None
  ) -> EvalSchedule:
    """Resumes a paused schedule and computes its next future run time."""
    schedule = self.schedule_repository.get_by_id(schedule_id)
    if not schedule:
      raise ValueError(f"Schedule with id {schedule_id} not found.")
    if schedule.is_archived:
      raise ValueError("Restore this schedule before resuming it.")

    self._validate_targets(schedule.agent_id, schedule.test_suite_id)
    current = _utc_now(now)
    schedule.is_enabled = True
    schedule.next_run_at = cron.next_run_time(
        schedule.cron_expression, tz_name=schedule.timezone, after=current
    )
    schedule.last_error_message = None
    return self.schedule_repository.save(schedule)

  def archive_schedule(self, schedule_id: int) -> EvalSchedule:
    """Archives and disables a schedule so it stops firing."""
    schedule = self.schedule_repository.get_by_id(schedule_id)
    if not schedule:
      raise ValueError(f"Schedule with id {schedule_id} not found.")
    schedule.is_archived = True
    schedule.is_enabled = False
    schedule.next_run_at = None
    return self.schedule_repository.save(schedule)

  def unarchive_schedule(self, schedule_id: int) -> EvalSchedule:
    """Restores an archived schedule in a paused state until explicitly resumed."""
    schedule = self.schedule_repository.get_by_id(schedule_id)
    if not schedule:
      raise ValueError(f"Schedule with id {schedule_id} not found.")
    schedule.is_archived = False
    schedule.is_enabled = False
    schedule.next_run_at = None
    return self.schedule_repository.save(schedule)

  def trigger_schedule_now(
      self, schedule_id: int, now: datetime.datetime | None = None
  ) -> Run:
    """Immediately queues an evaluation run for `schedule_id`."""
    current = _utc_now(now)
    schedule = self.schedule_repository.get_by_id(
        schedule_id, with_for_update=True
    )
    if not schedule:
      raise ValueError(f"Schedule with id {schedule_id} not found.")
    if schedule.is_archived:
      raise ValueError("Restore this schedule before running it.")
    if self._dispatch_blocked(schedule, current):
      raise ValueError(
          f"Schedule '{schedule.name}' already has an active run in progress."
      )
    self._validate_targets(schedule.agent_id, schedule.test_suite_id)

    schedule.dispatch_started_at = current
    self.session.commit()
    try:
      run = self.execution_service.create_run(
          agent_id=schedule.agent_id,
          test_suite_id=schedule.test_suite_id,
          generate_suggestions=schedule.generate_suggestions,
          concurrency=schedule.concurrency,
          schedule_id=schedule_id,
      )
    except Exception:
      locked = self._release_failed_claim(schedule_id)
      # A tick skipped because of this dispatch has no run to point at now.
      if (
          locked is not None
          and locked.last_error_message == SKIPPED_ACTIVE_RUN_MESSAGE
      ):
        locked.last_error_message = None
      self.session.commit()
      raise

    schedule.last_run_id = run.id
    schedule.last_run_at = current
    schedule.last_error_message = None
    schedule.dispatch_started_at = None
    self.schedule_repository.save(schedule)
    return run

  def process_due_schedules(
      self,
      now: datetime.datetime | None = None,
      limit: int = 20,
  ) -> ScheduleTickResult:
    """Claims due schedules one by one with SKIP LOCKED and queues runs.

    Advances next_run_at and takes the dispatch claim in one commit before
    create_run, so neither a second worker nor a concurrent Run Now can start
    another run for the same schedule. A due tick whose previous run is still
    active is skipped, and the reason is left on the schedule for the UI.

    Args:
      now: Optional UTC reference timestamp; defaults to current UTC time.
      limit: Maximum number of due schedules to process in a single tick.

    Returns:
      Summary of triggered, skipped, and errored schedule IDs for this tick.
    """
    current = _utc_now(now)
    result = ScheduleTickResult(checked_at=current)

    for _ in range(max(0, limit)):
      schedule = self.schedule_repository.claim_next_due_schedule(current)
      if schedule is None:
        break

      schedule_id = schedule.id
      future_next = cron.next_run_time(
          schedule.cron_expression,
          tz_name=schedule.timezone,
          after=current,
      )

      if self._dispatch_blocked(schedule, current):
        logger.info(
            "Skipping due schedule %s (%s): prior run is still active;"
            " advancing next_run_at to %s",
            schedule_id,
            schedule.name,
            future_next.isoformat(),
        )
        schedule.next_run_at = future_next
        schedule.last_error_message = SKIPPED_ACTIVE_RUN_MESSAGE
        self.session.commit()
        result.skipped_overlap_schedule_ids.append(schedule_id)
        continue

      try:
        self._validate_targets(schedule.agent_id, schedule.test_suite_id)
        schedule.next_run_at = future_next
        schedule.dispatch_started_at = current
        self.session.commit()
        run = self.execution_service.create_run(
            agent_id=schedule.agent_id,
            test_suite_id=schedule.test_suite_id,
            generate_suggestions=schedule.generate_suggestions,
            concurrency=schedule.concurrency,
            schedule_id=schedule_id,
        )
        schedule.last_run_id = run.id
        schedule.last_run_at = current
        schedule.last_error_message = None
        schedule.dispatch_started_at = None
        self.session.commit()
        logger.info(
            "Triggered scheduled run %s for schedule %s (%s); next_run_at=%s",
            run.id,
            schedule_id,
            schedule.name,
            future_next.isoformat(),
        )
        result.triggered_run_ids.append(run.id)
      except Exception as exc:  # pylint: disable=broad-exception-caught
        ref = uuid.uuid4().hex[:6]
        logger.exception(
            "Failed to dispatch due schedule %s (ref %s): %s",
            schedule_id,
            ref,
            exc,
        )
        locked = self._release_failed_claim(schedule_id)
        if locked is not None:
          locked.next_run_at = future_next
          if isinstance(exc, ValueError):
            locked.last_error_message = str(exc)
          else:
            locked.last_error_message = f"{displayable_error(exc)} (ref {ref})"
          self.session.commit()
        result.failed_schedule_ids.append(schedule_id)

    return result
