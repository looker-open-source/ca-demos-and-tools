import datetime
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot, TestSuiteSnapshot
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.dashboard_service import DashboardService
import pytest
from sqlalchemy import orm


def test_archived_runs_excluded_from_dashboard(db_session: orm.Session):
  # 1. Setup: Create an active run and an archived run
  agent = Agent(
      name="Test Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(name="S1", original_suite_id=1)
  db_session.add(suite_snap)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)

  active_run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      started_at=now - datetime.timedelta(hours=1),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=False,
  )
  archived_run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      started_at=now - datetime.timedelta(hours=2),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=True,
  )
  db_session.add_all([active_run, archived_run])
  db_session.commit()

  service = DashboardService(db_session)
  stats = service.get_dashboard_stats()

  # 2. Verification: Archived run should not be in stats
  assert stats.total_runs_7d == 1
  assert len(stats.recent_runs) == 1
  assert stats.recent_runs[0].id == active_run.id

  # Run volume history should only count the active run
  assert len(stats.run_volume_history) == 1
  assert stats.run_volume_history[0].count == 1


def test_archived_runs_excluded_from_agent_stats(db_session: orm.Session):
  # 1. Setup
  agent = Agent(
      name="Test Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(name="S1", original_suite_id=1)
  db_session.add(suite_snap)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)

  active_run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      created_at=now - datetime.timedelta(hours=1),
      started_at=now - datetime.timedelta(hours=1),
      completed_at=now - datetime.timedelta(minutes=50),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=False,
  )
  archived_run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      created_at=now - datetime.timedelta(hours=2),
      started_at=now - datetime.timedelta(hours=2),
      completed_at=now - datetime.timedelta(hours=1, minutes=50),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=True,
  )
  db_session.add_all([active_run, archived_run])
  db_session.commit()

  repo = RunRepository(db_session)
  stats = repo.get_agent_dashboard_stats(agent.id)

  # 2. Verification
  assert len(stats["recent_evals"]) == 1
  assert stats["recent_evals"][0]["id"] == active_run.id


def test_archived_runs_excluded_from_trial_picking(db_session: orm.Session):
  # 1. Setup: pending trial in archived run
  agent = Agent(
      name="Test Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(name="S1", original_suite_id=1)
  db_session.add(suite_snap)
  db_session.flush()

  ex_snap = ExampleSnapshot(
      snapshot_suite_id=suite_snap.id,
      question="Q",
      original_example_id=1,
      logical_id="L1",
  )
  db_session.add(ex_snap)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)

  archived_run = Run(
      agent_id=agent.id,
      status=RunStatus.PENDING,
      created_at=now,
      test_suite_snapshot_id=suite_snap.id,
      is_archived=True,
  )
  db_session.add(archived_run)
  db_session.flush()

  trial = Trial(
      run_id=archived_run.id,
      example_snapshot_id=ex_snap.id,
      status=RunStatus.PENDING,
  )
  db_session.add(trial)
  db_session.commit()

  repo = TrialRepository(db_session)
  next_trial = repo.pick_next_pending_trial()

  # 2. Verification: should not pick trial from archived run
  assert next_trial is None
