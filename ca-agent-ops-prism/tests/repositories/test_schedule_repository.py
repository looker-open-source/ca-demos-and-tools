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

"""Unit tests for ScheduleRepository."""

import datetime

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.schedule_repository import ScheduleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy import orm

_UTC = datetime.timezone.utc


def _seed_agent_and_suite(db_session: orm.Session):
  """Seeds a test Agent and TestSuite with one active question."""
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  agent = agent_repo.create(
      name="Sched Agent",
      config=AgentConfig(
          project_id="proj-1", location="global", agent_resource_id="ag-1"
      ),
  )
  suite = suite_repo.create(name="Sched Suite")
  example_repo.create(suite.id, "How many active customers exist?")
  return agent, suite


def test_schedule_crud_and_filters(db_session: orm.Session):
  """Verifies schedule creation, eager loading, and list filters."""
  agent, suite = _seed_agent_and_suite(db_session)
  other_agent = AgentRepository(db_session).create(
      name="Other Agent",
      config=AgentConfig(
          project_id="proj-1", location="global", agent_resource_id="ag-2"
      ),
  )
  repo = ScheduleRepository(db_session)

  t1 = datetime.datetime(2026, 10, 30, 12, 0, tzinfo=_UTC)
  s1 = repo.create(
      name="Morning Check",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="DAILY",
      cron_expression="0 9 * * *",
      timezone="UTC",
      generate_suggestions=True,
      concurrency=4,
      is_enabled=True,
      next_run_at=t1,
  )
  s2 = repo.create(
      name="Paused Check",
      agent_id=other_agent.id,
      test_suite_id=suite.id,
      cadence="WEEKLY",
      cron_expression="0 9 * * 1",
      timezone="America/New_York",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=False,
      next_run_at=None,
  )

  fetched = repo.get_by_id(s1.id)
  assert fetched is not None
  assert fetched.agent_name == "Sched Agent"
  assert fetched.suite_name == "Sched Suite"
  assert fetched.concurrency == 4
  assert fetched.generate_suggestions

  assert [s.id for s in repo.list_all(agent_id=agent.id)] == [s1.id]
  assert [s.id for s in repo.list_all(is_enabled=True)] == [s1.id]
  assert [s.id for s in repo.list_all(is_enabled=False)] == [s2.id]

  s2.is_archived = True
  repo.save(s2)
  assert [s.id for s in repo.list_all(include_archived=False)] == [s1.id]
  assert {s.id for s in repo.list_all(include_archived=True)} == {s1.id, s2.id}


@pytest.mark.parametrize(
    "status,expected_active",
    [
        (RunStatus.PENDING, True),
        (RunStatus.RUNNING, True),
        (RunStatus.EXECUTING, True),
        (RunStatus.EVALUATING, True),
        (RunStatus.PAUSED, True),
        (RunStatus.COMPLETED, False),
        (RunStatus.FAILED, False),
        (RunStatus.CANCELLED, False),
    ],
)
def test_has_active_run_tracks_non_terminal_unarchived_runs(
    db_session: orm.Session, status: RunStatus, expected_active: bool
):
  """Checks active-run overlap detection across all RunStatus values."""
  agent, suite = _seed_agent_and_suite(db_session)
  snap = SnapshotService(
      db_session, SuiteRepository(db_session), ExampleRepository(db_session)
  ).create_snapshot(suite.id)
  sched_repo = ScheduleRepository(db_session)
  run_repo = RunRepository(db_session)

  sched = sched_repo.create(
      name="Overlap Check",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="HOURLY",
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=True,
      next_run_at=datetime.datetime(2026, 10, 30, 12, 0, tzinfo=_UTC),
  )
  run = run_repo.create(snap.id, agent.id, schedule_id=sched.id)
  run.status = status
  db_session.commit()

  assert sched_repo.has_active_run(sched.id) is expected_active


def test_claim_next_due_schedule_orders_by_due_time_and_skips_ineligible(
    db_session: orm.Session,
):
  """Claims the oldest due enabled schedule and skips future/disabled rows."""
  agent, suite = _seed_agent_and_suite(db_session)
  repo = ScheduleRepository(db_session)
  now = datetime.datetime(2026, 10, 30, 12, 0, tzinfo=_UTC)

  later_due = repo.create(
      name="Later Due",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="HOURLY",
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=True,
      next_run_at=now - datetime.timedelta(minutes=5),
  )
  earlier_due = repo.create(
      name="Earlier Due",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="HOURLY",
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=True,
      next_run_at=now - datetime.timedelta(minutes=30),
  )
  repo.create(
      name="Future Schedule",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="HOURLY",
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=True,
      next_run_at=now + datetime.timedelta(minutes=10),
  )
  repo.create(
      name="Disabled Schedule",
      agent_id=agent.id,
      test_suite_id=suite.id,
      cadence="HOURLY",
      cron_expression="0 * * * *",
      timezone="UTC",
      generate_suggestions=False,
      concurrency=2,
      is_enabled=False,
      next_run_at=now - datetime.timedelta(minutes=45),
  )

  claimed = repo.claim_next_due_schedule(now)
  assert claimed is not None
  assert claimed.id == earlier_due.id

  # Advance earlier_due so the next call picks later_due.
  claimed.next_run_at = now + datetime.timedelta(hours=1)
  db_session.commit()

  second = repo.claim_next_due_schedule(now)
  assert second is not None
  assert second.id == later_due.id
