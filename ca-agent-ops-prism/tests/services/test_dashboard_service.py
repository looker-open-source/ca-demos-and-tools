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

import datetime
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.assertion import AssertionType
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.dashboard_service import DashboardService
from sqlalchemy import orm


def test_get_dashboard_stats_accuracy_history(db_session: orm.Session):
  agent = Agent(
      name="Test Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  db_session.add(agent)
  db_session.commit()

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
  run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      started_at=now - datetime.timedelta(days=1),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=False,
  )
  db_session.add(run)
  db_session.commit()

  snap = AssertionSnapshot(
      example_snapshot_id=ex_snap.id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
  )
  db_session.add(snap)
  db_session.commit()

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
  # The chart plots a run's accuracy. It used to come back named score, which
  # is a per-trial number, so the two were being read as one.
  history_item = stats.accuracy_history[0]
  assert hasattr(history_item, "accuracy")
  assert history_item.accuracy == 0.8
  assert not hasattr(history_item, "score")

  # The home callback reads three fields off the stats. The other two are
  # built from the same run, so cover them here as well.
  assert len(stats.run_volume_history) == 1
  assert stats.run_volume_history[0].count == 1
  assert [r.id for r in stats.recent_runs] == [run.id]


def test_both_charts_put_one_run_on_the_same_day(db_session: orm.Session):
  """The accuracy series bucketed on started_at, the volume one on created_at.

  A run created at 23:50 and picked up by the worker after midnight drew its
  accuracy point on one day and its bar on the day before. The day carrying
  the point read a volume of 0 next to it.
  """
  agent = Agent(
      name="Split Day Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
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
  # Three days between creation and promotion, so the two fields fall on
  # different days in any timezone the server might be left at.
  run = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      created_at=now - datetime.timedelta(days=5),
      started_at=now - datetime.timedelta(days=2),
      completed_at=now - datetime.timedelta(days=2),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=False,
  )
  db_session.add(run)
  db_session.flush()

  snap = AssertionSnapshot(
      example_snapshot_id=ex_snap.id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
  )
  db_session.add(snap)
  db_session.flush()

  trial = Trial(
      run_id=run.id,
      example_snapshot_id=ex_snap.id,
      status=RunStatus.COMPLETED,
  )
  db_session.add(trial)
  db_session.flush()

  db_session.add(
      AssertionResult(
          trial_id=trial.id,
          assertion_snapshot_id=snap.id,
          passed=True,
          score=0.8,
      )
  )
  db_session.commit()
  db_session.expire_all()

  stats = DashboardService(db_session).get_dashboard_stats()

  run = db_session.get(Run, run.id)
  created_day = run.created_at.strftime("%Y-%m-%d")
  assert run.started_at.strftime("%Y-%m-%d") != created_day

  assert [(p.date, p.accuracy) for p in stats.accuracy_history] == [
      (created_day, 0.8)
  ]
  assert [(p.date, p.count) for p in stats.run_volume_history] == [
      (created_day, 1)
  ]


def test_the_volume_chart_counts_a_run_on_the_day_it_was_created(
    db_session: orm.Session,
):
  """started_at is NULL until the worker promotes the run.

  Filtered and bucketed on started_at, a queued run was counted on no day at
  all, and a run that waited in the queue landed on the day the worker reached
  it rather than the day someone asked for it. The comment above the query
  said volume counted every run.
  """
  agent = Agent(
      name="Volume Agent", project_id="p", location="l", agent_resource_id="r"
  )
  db_session.add(agent)
  db_session.flush()

  suite_snap = TestSuiteSnapshot(name="S1", original_suite_id=1)
  db_session.add(suite_snap)
  db_session.flush()

  now = datetime.datetime.now(datetime.timezone.utc)
  queued = Run(
      agent_id=agent.id,
      status=RunStatus.PENDING,
      created_at=now - datetime.timedelta(days=3),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=False,
  )
  # Three days between the two, so the day the run was created and the day it
  # started are different days in any timezone the server might be left at.
  delayed = Run(
      agent_id=agent.id,
      status=RunStatus.COMPLETED,
      created_at=now - datetime.timedelta(days=5),
      started_at=now - datetime.timedelta(days=2),
      completed_at=now - datetime.timedelta(days=2),
      test_suite_snapshot_id=suite_snap.id,
      is_archived=False,
  )
  db_session.add_all([queued, delayed])
  db_session.commit()
  db_session.expire_all()

  stats = DashboardService(db_session).get_dashboard_stats()

  queued = db_session.get(Run, queued.id)
  delayed = db_session.get(Run, delayed.id)
  counts = {point.date: point.count for point in stats.run_volume_history}

  # Exactly two bars, so the day the delayed run started carries none.
  assert counts == {
      queued.created_at.strftime("%Y-%m-%d"): 1,
      delayed.created_at.strftime("%Y-%m-%d"): 1,
  }
  assert delayed.started_at.strftime("%Y-%m-%d") not in counts
