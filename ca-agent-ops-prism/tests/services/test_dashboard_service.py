import datetime
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.services.dashboard_service import DashboardService
import pytest
from sqlalchemy import orm


def test_get_dashboard_stats_accuracy_history(db_session: orm.Session):
  # Setup
  agent = Agent(
      name="Test Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  db_session.add(agent)
  db_session.commit()

  from prism.server.models.snapshot import TestSuiteSnapshot, ExampleSnapshot

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
  # Create a completed run with some accuracy
  run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      started_at=now - datetime.timedelta(days=1),
      test_suite_snapshot_id=suite_snap.id,
  )
  db_session.add(run)
  db_session.commit()

  from prism.server.models.assertion import AssertionResult, AssertionSnapshot, AssertionType

  snap = AssertionSnapshot(
      example_snapshot_id=ex_snap.id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
  )
  db_session.add(snap)
  db_session.commit()

  # Add a trial
  trial = Trial(
      run_id=run.id,
      example_snapshot_id=ex_snap.id,
      status=RunStatus.COMPLETED,
  )
  db_session.add(trial)
  db_session.commit()

  res = AssertionResult(
      trial_id=trial.id,
      assertion_snapshot_id=snap.id,
      passed=True,
      score=0.8,
  )
  db_session.add(res)
  db_session.commit()

  service = DashboardService(db_session)
  stats = service.get_dashboard_stats()

  assert len(stats.accuracy_history) >= 1
  # Check that the field is 'accuracy' and not 'score'
  history_item = stats.accuracy_history[0]
  assert hasattr(history_item, "accuracy")
  assert history_item.accuracy == 0.8
  assert not hasattr(history_item, "score")
