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

"""Accuracy regression tests for RunRepository.

Three places in this repository report accuracy: the latest-run stats on the
agent list, the sparkline history, and the daily chart on the agent dashboard.
Each used to compute it with its own SQL aggregate over AssertionResult rows,
and the three disagreed with each other and with the run page. All three now
defer to ``Run.accuracy``.

``tests/services/test_run_accuracy.py`` pins the rule itself on detached
objects. These go through the repository against a real database, because the
aggregates only diverged once the rows hit a join.
"""

import datetime

from prism.common.schemas import assertion as assertion_schemas
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunHistoryPoint
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.snapshot_service import SnapshotService
import pytest
from sqlalchemy.orm import Session

_SUITE_NAME = "Suite"


def _half_crashed_run(session: Session) -> tuple[Agent, Run]:
  """One agent with one run: a trial scoring 1.0 and a trial that crashed.

  The crashed trial gets no assertion results. The agent never answered, so
  nothing was evaluated, and that absence is what the old aggregates lost.
  """
  agent_repo = AgentRepository(session)
  suite_repo = SuiteRepository(session)
  example_repo = ExampleRepository(session)
  snapshot_service = SnapshotService(session, suite_repo, example_repo)
  run_repo = RunRepository(session)
  trial_repo = TrialRepository(session)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name=_SUITE_NAME)
  for question in ("Q1", "Q2"):
    example = example_repo.create(suite.id, question)
    example_repo.add_assertion(
        example.id, assertion_schemas.TextContainsSchema(value="ok")
    )
  snapshot = snapshot_service.create_snapshot(suite.id)

  run = run_repo.create(snapshot.id, agent.id)
  run.status = RunStatus.COMPLETED

  passed = trial_repo.create(run.id, snapshot.examples[0].id)
  passed.status = RunStatus.COMPLETED
  session.add(
      AssertionResult(
          trial_id=passed.id,
          assertion_snapshot_id=snapshot.examples[0].asserts[0].id,
          passed=True,
          score=1.0,
      )
  )

  crashed = trial_repo.create(run.id, snapshot.examples[1].id)
  crashed.status = RunStatus.FAILED
  crashed.error_message = "boom"

  session.commit()
  return agent, run


def test_latest_run_stats_score_a_crashed_trial_as_zero(db_session: Session):
  """All three paths returned 1.0 on this run before the fix.

  Each aggregated AssertionResult rows in SQL. A crashed trial has none, so an
  inner join dropped it from the denominator and an outer join handed it a NULL
  that avg skips. Either way a run where half the trials crashed reported the
  accuracy of the half that worked.
  """
  agent, _ = _half_crashed_run(db_session)

  stats = RunRepository(db_session).get_latest_runs_with_stats([agent.id])

  assert stats[agent.id]["accuracy"] == pytest.approx(0.5)


def test_history_sparkline_scores_a_crashed_trial_as_zero(db_session: Session):
  agent, _ = _half_crashed_run(db_session)

  history = RunRepository(db_session).get_run_history_for_agents([agent.id])

  assert [point["accuracy"] for point in history[agent.id]] == [
      pytest.approx(0.5)
  ]


def test_daily_accuracy_chart_scores_a_crashed_trial_as_zero(
    db_session: Session,
):
  agent, _ = _half_crashed_run(db_session)

  daily = RunRepository(db_session).get_agent_dashboard_stats(agent.id)[
      "daily_accuracy"
  ]

  assert len(daily) == 1
  assert daily[0][_SUITE_NAME] == pytest.approx(0.5)


def test_the_three_accuracy_paths_agree_with_the_run(db_session: Session):
  """They disagreed, which is how the bug survived: each page looked sane."""
  agent, run = _half_crashed_run(db_session)
  repo = RunRepository(db_session)

  latest = repo.get_latest_runs_with_stats([agent.id])[agent.id]["accuracy"]
  history = repo.get_run_history_for_agents([agent.id])[agent.id][0]["accuracy"]
  daily = repo.get_agent_dashboard_stats(agent.id)["daily_accuracy"][0][
      _SUITE_NAME
  ]

  assert run.accuracy == pytest.approx(0.5)
  assert latest == pytest.approx(run.accuracy)
  assert history == pytest.approx(run.accuracy)
  assert daily == pytest.approx(run.accuracy)


def test_a_run_that_has_scored_nothing_keeps_a_null_history_point(
    db_session: Session,
):
  """A queued run is not a run that scored zero.

  The history point was typed float, so the repository coerced the None to
  0.0. The sparkline then drew the queued run at 0% and turned the whole trend
  red, while the "Last eval" text on the same row read "--" for it.
  """
  agent, scored_run = _half_crashed_run(db_session)
  queued_run = RunRepository(db_session).create(
      scored_run.test_suite_snapshot_id, agent.id
  )
  assert queued_run.accuracy is None

  history = RunRepository(db_session).get_run_history_for_agents([agent.id])

  by_run = {p["run_id"]: p["accuracy"] for p in history[agent.id]}
  assert by_run[scored_run.id] == pytest.approx(0.5)
  assert by_run[queued_run.id] is None
  # The client validates every point through this schema before the table
  # sees it, and a float-only field is what forced the coercion.
  assert all(
      RunHistoryPoint.model_validate(p).accuracy == p["accuracy"]
      for p in history[agent.id]
  )


def test_avg_duration_averages_over_trials_not_over_runs(db_session: Session):
  """The one aggregate in that query that is not distinct on Run.id.

  It answers how long a trial takes, so a run with more trials weighs more.
  Three trials of 1s and one of 5s average to 2s per trial. Per run they would
  average to 3s.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  repo = RunRepository(db_session)

  agent = agent_repo.create(
      name="Bot",
      config=AgentConfig(project_id="p", location="l", agent_resource_id="r"),
  )
  suite = suite_repo.create(name=_SUITE_NAME)

  short_run = repo.create(
      snapshot_service.create_snapshot(suite.id).id, agent.id
  )
  long_run = repo.create(
      snapshot_service.create_snapshot(suite.id).id, agent.id
  )
  db_session.flush()

  for run, trial_count, seconds in ((short_run, 3, 1), (long_run, 1, 5)):
    for i in range(trial_count):
      example = ExampleSnapshot(
          snapshot_suite_id=run.test_suite_snapshot_id,
          question=f"Q{i}",
          original_example_id=i + 1,
          logical_id=f"L{run.id}-{i}",
      )
      db_session.add(example)
      db_session.flush()
      started = datetime.datetime.now(datetime.timezone.utc)
      db_session.add(
          Trial(
              run_id=run.id,
              example_snapshot_id=example.id,
              status=RunStatus.COMPLETED,
              started_at=started,
              completed_at=started + datetime.timedelta(seconds=seconds),
          )
      )
  db_session.commit()

  stats = repo.get_agent_dashboard_stats(agent.id)

  assert stats["avg_duration_ms"] == 2000
