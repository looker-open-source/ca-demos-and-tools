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

"""The agent dashboard's recent-runs list, and what it costs to build it.

get_agent_dashboard_stats read the five most recent runs with a joinedload on
Run.trials. Two things were wrong with that.

The LIMIT applied to the joined rows, not to the runs. A run with twenty trials
is twenty rows, so a query asking for five got one run back and the panel said
the agent had run once.

And the loader stopped at the trials. r.accuracy walks every trial's assertion
results and their snapshots, so each trial cost two more queries. The list grew
its query count with the size of the runs on it.

Both are the same one-line fix, eager_options(), so both are pinned here.
"""

import datetime

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.repositories.run_repository import RunRepository
import pytest
from sqlalchemy import orm

NOW = datetime.datetime.now(datetime.timezone.utc)


def _agent_with_runs(
    session: orm.Session, run_count: int, trials_per_run: int
) -> Agent:
  """One agent, its runs, and one scored assertion on every trial."""
  agent = Agent(
      name="Dashboard Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  session.add(agent)
  session.flush()

  for run_index in range(run_count):
    suite_snapshot = TestSuiteSnapshot(name=f"Suite {run_index}")
    session.add(suite_snapshot)
    session.flush()

    run = Run(
        agent_id=agent.id,
        test_suite_snapshot_id=suite_snapshot.id,
        status=RunStatus.COMPLETED,
        created_at=NOW - datetime.timedelta(minutes=run_index),
        started_at=NOW - datetime.timedelta(minutes=run_index),
        completed_at=NOW,
        is_archived=False,
    )
    session.add(run)
    session.flush()

    for trial_index in range(trials_per_run):
      example_snapshot = ExampleSnapshot(
          snapshot_suite_id=suite_snapshot.id,
          logical_id=f"L{run_index}-{trial_index}",
          question="Q",
      )
      session.add(example_snapshot)
      session.flush()
      trial = Trial(
          run_id=run.id,
          example_snapshot_id=example_snapshot.id,
          status=RunStatus.COMPLETED,
          created_at=run.created_at,
          started_at=run.created_at,
          completed_at=NOW,
      )
      trial.assertion_results.append(
          AssertionResult(
              score=1.0,
              passed=True,
              assertion_snapshot=AssertionSnapshot(
                  type=AssertionType.TEXT_CONTAINS,
                  weight=1.0,
                  params={"value": "x"},
                  example_snapshot_id=example_snapshot.id,
              ),
          )
      )
      session.add(trial)

  session.commit()
  return agent


def test_the_recent_list_holds_five_runs_however_many_trials_they_have(
    db_session: orm.Session,
):
  """The LIMIT has to count runs. Under a joinedload it counted rows."""
  agent = _agent_with_runs(db_session, run_count=6, trials_per_run=7)

  stats = RunRepository(db_session).get_agent_dashboard_stats(agent.id)

  assert len(stats["recent_evals"]) == 5
  assert all(e["score"] == 1.0 for e in stats["recent_evals"])


def test_the_query_count_does_not_grow_with_the_trials_on_a_run(
    db_session: orm.Session, statement_counter
):
  """Same five runs, more trials each, same number of round trips."""
  small = _agent_with_runs(db_session, run_count=5, trials_per_run=1)
  large = _agent_with_runs(db_session, run_count=5, trials_per_run=8)
  repository = RunRepository(db_session)

  # Expired first, so neither call is served out of the identity map that the
  # other one filled.
  db_session.expire_all()
  with statement_counter() as small_counter:
    repository.get_agent_dashboard_stats(small.id)

  db_session.expire_all()
  with statement_counter() as large_counter:
    repository.get_agent_dashboard_stats(large.id)

  assert large_counter.count == small_counter.count


def _agent_with_trial_scores(
    session: orm.Session, scores: list[float | None]
) -> Agent:
  """One agent, one run, and a trial for every entry in ``scores``.

  A float is a trial carrying one assertion of weight 1 that scored it, so the
  trial's score is that float. None is a COMPLETED trial whose only assertion
  has weight 0, which leaves the trial with no score at all. Run.accuracy
  drops those from both sides of the average, so a seed holding one is what
  tells the two plausible denominators apart.
  """
  agent = Agent(
      name="Dashboard Agent",
      project_id="p",
      location="l",
      agent_resource_id="r",
  )
  session.add(agent)
  session.flush()

  suite_snapshot = TestSuiteSnapshot(name="Suite")
  session.add(suite_snapshot)
  session.flush()

  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snapshot.id,
      status=RunStatus.COMPLETED,
      created_at=NOW,
      started_at=NOW,
      completed_at=NOW,
      is_archived=False,
  )
  session.add(run)
  session.flush()

  for index, score in enumerate(scores):
    example_snapshot = ExampleSnapshot(
        snapshot_suite_id=suite_snapshot.id,
        logical_id=f"L{index}",
        question="Q",
    )
    session.add(example_snapshot)
    session.flush()
    trial = Trial(
        run_id=run.id,
        example_snapshot_id=example_snapshot.id,
        status=RunStatus.COMPLETED,
        created_at=NOW,
        started_at=NOW,
        completed_at=NOW,
    )
    trial.assertion_results.append(
        AssertionResult(
            score=0.0 if score is None else score,
            passed=score == 1.0,
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS,
                weight=0.0 if score is None else 1.0,
                params={"value": "x"},
                example_snapshot_id=example_snapshot.id,
            ),
        )
    )
    session.add(trial)

  session.commit()
  return agent


@pytest.mark.parametrize(
    "scores",
    [
        [0.25, None],
        [1.0, 0.5, 0.0, 0.75, None, 1.0, 0.25, 0.5],
    ],
)
def test_the_score_on_the_list_is_the_accuracy_the_trials_imply(
    db_session: orm.Session, scores: list[float | None]
):
  """Eager loading must not change the number, only what it costs.

  The expected score is worked out here from the seed. Reading it back off
  ``run.accuracy`` compares the list against the same ORM object the list was
  built from, which holds whatever that property is made to return.
  """
  agent = _agent_with_trial_scores(db_session, scores)
  scored = [s for s in scores if s is not None]
  expected = sum(scored) / len(scored)

  stats = RunRepository(db_session).get_agent_dashboard_stats(agent.id)

  assert stats["recent_evals"][0]["score"] == pytest.approx(expected)
