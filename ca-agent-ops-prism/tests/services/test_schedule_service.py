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

"""Unit tests for ScheduleService."""

import datetime
from unittest import mock

from google.api_core import exceptions as api_exceptions
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.execution import RunStatus
from prism.common.schemas.schedule import ScheduleCadence
from prism.common.schemas.schedule import ScheduleCreate
from prism.common.schemas.schedule import ScheduleUpdate
from prism.common.schemas.schedule import SKIPPED_ACTIVE_RUN_MESSAGE
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.schedule_repository import ScheduleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.schedule_service import ScheduleService
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy import orm

_UTC = datetime.timezone.utc


def _build_services(db_session: orm.Session):
  """Constructs ScheduleService and mocked GeminiDataAnalyticsClient."""
  gda_client = mock.MagicMock(spec=GeminiDataAnalyticsClient)
  gda_client.get_datasource_kind.return_value = "bq"
  gda_client.get_agent_context.return_value = {
      "system_instruction": "Answer concise SQL questions."
  }
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snap_service = SnapshotService(db_session, suite_repo, example_repo)
  exec_service = ExecutionService(db_session, snap_service, gda_client)
  sched_repo = ScheduleRepository(db_session)
  sched_service = ScheduleService(db_session, sched_repo, exec_service)
  return sched_service, gda_client


def _seed_ready_targets(db_session: orm.Session):
  """Seeds a BigQuery Agent and TestSuite with one active question."""
  agent = AgentRepository(db_session).create(
      name="Sales Agent",
      config=AgentConfig(
          project_id="proj-1",
          location="global",
          agent_resource_id="sales-1",
          datasource=BigQueryConfig(tables=["proj-1.sales.orders"]),
      ),
  )
  suite = SuiteRepository(db_session).create(name="Nightly Sales")
  ExampleRepository(db_session).create(suite.id, "Total orders yesterday?")
  return agent, suite


def test_create_update_pause_resume_archive_and_restore_lifecycle(
    db_session: orm.Session,
):
  """Exercises full schedule CRUD, pause, resume, archive, and restore flow."""
  sched_service, _ = _build_services(db_session)
  agent, suite = _seed_ready_targets(db_session)
  now = datetime.datetime(2026, 10, 30, 8, 15, tzinfo=_UTC)

  created = sched_service.create_schedule(
      ScheduleCreate(
          name="Daily 09:00 Check",
          agent_id=agent.id,
          test_suite_id=suite.id,
          cadence=ScheduleCadence.DAILY,
          cron_expression="0 9 * * *",
          timezone="UTC",
          concurrency=3,
          generate_suggestions=True,
          is_enabled=True,
      ),
      now=now,
  )
  assert created.next_run_at == datetime.datetime(
      2026, 10, 30, 9, 0, tzinfo=_UTC
  )
  assert created.concurrency == 3

  paused = sched_service.pause_schedule(created.id)
  assert not paused.is_enabled
  assert paused.next_run_at is None

  resumed = sched_service.resume_schedule(
      created.id, now=datetime.datetime(2026, 10, 30, 10, 0, tzinfo=_UTC)
  )
  assert resumed.is_enabled
  assert resumed.next_run_at == datetime.datetime(
      2026, 10, 31, 9, 0, tzinfo=_UTC
  )

  updated = sched_service.update_schedule(
      created.id,
      ScheduleUpdate(
          name="Hourly Check",
          cadence=ScheduleCadence.HOURLY,
          cron_expression="30 * * * *",
          concurrency=4,
      ),
      now=datetime.datetime(2026, 10, 30, 10, 5, tzinfo=_UTC),
  )
  assert updated.name == "Hourly Check"
  assert updated.concurrency == 4
  assert updated.next_run_at == datetime.datetime(
      2026, 10, 30, 10, 30, tzinfo=_UTC
  )

  archived = sched_service.archive_schedule(created.id)
  assert archived.is_archived
  assert not archived.is_enabled
  assert archived.next_run_at is None

  with pytest.raises(ValueError, match="Restore it before editing"):
    sched_service.update_schedule(created.id, ScheduleUpdate(name="Nope"))

  restored = sched_service.unarchive_schedule(created.id)
  assert not restored.is_archived
  assert not restored.is_enabled
  assert restored.next_run_at is None


def test_schedule_validation_refuses_archived_empty_or_uncredentialed_targets(
    db_session: orm.Session,
):
  """Refuses schedules targeting empty suites, uncredentialed, or archived rows."""
  sched_service, _ = _build_services(db_session)
  agent, suite = _seed_ready_targets(db_session)

  empty_suite = SuiteRepository(db_session).create(name="Empty Suite")
  with pytest.raises(ValueError, match="no active questions"):
    sched_service.create_schedule(
        ScheduleCreate(
            name="Bad Suite",
            agent_id=agent.id,
            test_suite_id=empty_suite.id,
            cron_expression="0 9 * * *",
        )
    )

  looker_agent = AgentRepository(db_session).create(
      name="Looker Without Creds",
      config=AgentConfig(
          project_id="proj-1",
          location="global",
          agent_resource_id="lk-1",
          datasource=LookerConfig(
              instance_uri="https://looker.example.com",
              explores=["sales/orders"],
          ),
      ),
  )
  with pytest.raises(ValueError, match="Looker Client ID and Secret"):
    sched_service.create_schedule(
        ScheduleCreate(
            name="Looker Schedule",
            agent_id=looker_agent.id,
            test_suite_id=suite.id,
            cron_expression="0 9 * * *",
        )
    )

  AgentRepository(db_session).archive(agent.id)
  with pytest.raises(ValueError, match="is archived"):
    sched_service.create_schedule(
        ScheduleCreate(
            name="Archived Agent Schedule",
            agent_id=agent.id,
            test_suite_id=suite.id,
            cron_expression="0 9 * * *",
        )
    )


def test_trigger_now_and_process_due_schedules_handle_overlap_and_errors(
    db_session: orm.Session,
):
  """Verifies manual trigger, overlap protection, and per-schedule errors."""
  sched_service, _ = _build_services(db_session)
  agent, suite = _seed_ready_targets(db_session)
  t0 = datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC)

  sched = sched_service.create_schedule(
      ScheduleCreate(
          name="Hourly Ops",
          agent_id=agent.id,
          test_suite_id=suite.id,
          cadence=ScheduleCadence.HOURLY,
          cron_expression="0 * * * *",
          timezone="UTC",
      ),
      now=t0,
  )

  # Triggering immediately creates a PENDING run tied to the schedule.
  manual_run = sched_service.trigger_schedule_now(sched.id, now=t0)
  assert manual_run.schedule_id == sched.id
  assert sched_service.get_schedule(sched.id).last_run_id == manual_run.id

  # A second manual trigger while manual_run is still PENDING is refused.
  with pytest.raises(ValueError, match="already has an active run"):
    sched_service.trigger_schedule_now(sched.id, now=t0)

  # When the 09:00 tick arrives while manual_run is still PENDING, the tick
  # skips overlap and advances next_run_at to 10:00.
  t1 = datetime.datetime(2026, 10, 30, 9, 5, tzinfo=_UTC)
  overlap_tick = sched_service.process_due_schedules(now=t1)
  assert not overlap_tick.triggered_run_ids
  assert overlap_tick.skipped_overlap_schedule_ids == [sched.id]
  skipped = sched_service.get_schedule(sched.id)
  assert skipped.next_run_at == datetime.datetime(
      2026, 10, 30, 10, 0, tzinfo=_UTC
  )
  assert skipped.last_error_message == SKIPPED_ACTIVE_RUN_MESSAGE

  # Finish the active run, then advance to 10:05 and simulate an API failure on
  # a second schedule while the first schedule succeeds.
  manual_run.status = RunStatus.COMPLETED
  db_session.commit()

  failing_sched = sched_service.create_schedule(
      ScheduleCreate(
          name="Failing Ops",
          agent_id=agent.id,
          test_suite_id=suite.id,
          cadence=ScheduleCadence.HOURLY,
          cron_expression="0 * * * *",
          timezone="UTC",
      ),
      now=datetime.datetime(2026, 10, 30, 9, 30, tzinfo=_UTC),
  )

  real_create_snapshot = (
      sched_service.execution_service.snapshot_service.create_snapshot
  )
  call_count = {"n": 0}

  def flaky_snapshot(suite_id: int):
    call_count["n"] += 1
    if call_count["n"] == 2:
      raise api_exceptions.PermissionDenied("Caller lacks dataAgents.get")
    return real_create_snapshot(suite_id)

  with mock.patch.object(
      sched_service.execution_service.snapshot_service,
      "create_snapshot",
      side_effect=flaky_snapshot,
  ):
    t2 = datetime.datetime(2026, 10, 30, 10, 5, tzinfo=_UTC)
    mixed_tick = sched_service.process_due_schedules(now=t2)
  assert len(mixed_tick.triggered_run_ids) == 1
  assert mixed_tick.failed_schedule_ids == [failing_sched.id]
  # The next successful dispatch clears the skip message.
  assert sched_service.get_schedule(sched.id).last_error_message is None

  refreshed_fail = sched_service.get_schedule(failing_sched.id)
  assert refreshed_fail.next_run_at == datetime.datetime(
      2026, 10, 30, 11, 0, tzinfo=_UTC
  )
  assert refreshed_fail.last_run_at is None
  assert refreshed_fail.last_run_id is None
  assert refreshed_fail.last_error_message is not None
  assert "(ref " in refreshed_fail.last_error_message

  # Simulate run_repository.create failing AFTER SnapshotService.create_snapshot
  # has already committed: last_run_at and last_run_id must stay on the previous
  # successful run rather than stamping the failed tick.
  prev_last_run_at = sched_service.get_schedule(sched.id).last_run_at
  prev_last_run_id = sched_service.get_schedule(sched.id).last_run_id
  assert prev_last_run_at is not None
  assert prev_last_run_id is not None

  for active_run in sched_service.execution_service.run_repository.list_all(
      schedule_id=sched.id
  ):
    active_run.status = RunStatus.COMPLETED
  db_session.commit()

  with mock.patch.object(
      sched_service.execution_service.run_repository,
      "create",
      side_effect=RuntimeError("DB insert failed after snapshot commit"),
  ):
    t3 = datetime.datetime(2026, 10, 30, 11, 5, tzinfo=_UTC)
    halfway_fail_tick = sched_service.process_due_schedules(now=t3)
  assert sched.id in halfway_fail_tick.failed_schedule_ids
  after_halfway_fail = sched_service.get_schedule(sched.id)
  assert after_halfway_fail.last_run_at == prev_last_run_at
  assert after_halfway_fail.last_run_id == prev_last_run_id
  assert after_halfway_fail.next_run_at == datetime.datetime(
      2026, 10, 30, 12, 0, tzinfo=_UTC
  )
  assert after_halfway_fail.last_error_message is not None
  assert after_halfway_fail.dispatch_started_at is None


def test_update_only_validates_targets_when_they_change_or_on_enable(
    db_session: orm.Session,
):
  """A suite archived after scheduling still lets Edit rename or disable."""
  sched_service, _ = _build_services(db_session)
  agent, suite = _seed_ready_targets(db_session)
  now = datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC)
  sched = sched_service.create_schedule(
      ScheduleCreate(
          name="Nightly",
          agent_id=agent.id,
          test_suite_id=suite.id,
          cron_expression="0 9 * * *",
      ),
      now=now,
  )
  suite.is_archived = True
  db_session.commit()

  renamed = sched_service.update_schedule(
      sched.id, ScheduleUpdate(name="Nightly Renamed"), now=now
  )
  assert renamed.name == "Nightly Renamed"
  disabled = sched_service.update_schedule(
      sched.id, ScheduleUpdate(is_enabled=False), now=now
  )
  assert not disabled.is_enabled

  with pytest.raises(ValueError, match="is archived"):
    sched_service.update_schedule(
        sched.id, ScheduleUpdate(is_enabled=True), now=now
    )

  other_suite = SuiteRepository(db_session).create(name="Empty Suite")
  with pytest.raises(ValueError, match="no active questions"):
    sched_service.update_schedule(
        sched.id, ScheduleUpdate(test_suite_id=other_suite.id), now=now
    )


def test_dispatch_claim_blocks_until_released_or_stale(
    db_session: orm.Session,
):
  """A live claim refuses Run Now and skips the tick; a stale one does not."""
  sched_service, _ = _build_services(db_session)
  agent, suite = _seed_ready_targets(db_session)
  t0 = datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC)
  sched = sched_service.create_schedule(
      ScheduleCreate(
          name="Claimed",
          agent_id=agent.id,
          test_suite_id=suite.id,
          cron_expression="0 * * * *",
      ),
      now=t0,
  )

  # Another dispatcher is mid create_run at 09:00: no Run row exists yet.
  claimed_at = datetime.datetime(2026, 10, 30, 9, 0, tzinfo=_UTC)
  sched.dispatch_started_at = claimed_at
  db_session.commit()
  with pytest.raises(ValueError, match="already has an active run"):
    sched_service.trigger_schedule_now(sched.id, now=claimed_at)
  tick = sched_service.process_due_schedules(
      now=claimed_at + datetime.timedelta(minutes=1)
  )
  assert tick.skipped_overlap_schedule_ids == [sched.id]

  # A claim left by a dispatcher that died stops blocking after the TTL.
  stale_now = claimed_at + datetime.timedelta(minutes=11)
  run = sched_service.trigger_schedule_now(sched.id, now=stale_now)
  assert run.schedule_id == sched.id
  refreshed = sched_service.get_schedule(sched.id)
  assert refreshed.dispatch_started_at is None
  assert refreshed.last_run_id == run.id


def test_failed_run_now_releases_its_claim(db_session: orm.Session):
  """create_run failing after the claim commit leaves the schedule usable."""
  sched_service, _ = _build_services(db_session)
  agent, suite = _seed_ready_targets(db_session)
  t0 = datetime.datetime(2026, 10, 30, 8, 0, tzinfo=_UTC)
  sched = sched_service.create_schedule(
      ScheduleCreate(
          name="Flaky",
          agent_id=agent.id,
          test_suite_id=suite.id,
          cron_expression="0 * * * *",
      ),
      now=t0,
  )

  # A worker tick skipped during this dispatch left its message behind.
  sched.last_error_message = SKIPPED_ACTIVE_RUN_MESSAGE
  db_session.commit()
  with mock.patch.object(
      sched_service.execution_service,
      "create_run",
      side_effect=RuntimeError("snapshot insert failed"),
  ):
    with pytest.raises(RuntimeError, match="snapshot insert failed"):
      sched_service.trigger_schedule_now(sched.id, now=t0)
  released = sched_service.get_schedule(sched.id)
  assert released.dispatch_started_at is None
  assert released.last_error_message is None

  run = sched_service.trigger_schedule_now(sched.id, now=t0)
  assert run.schedule_id == sched.id
