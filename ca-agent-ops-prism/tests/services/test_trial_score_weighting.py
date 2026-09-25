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

"""Unit tests for ``Trial.score``.

The score is a weighted mean over the assertion results with a weight above
zero, and it is written twice: a Python property that reads
``self.assertion_results``, and a SQL correlated subquery that runs whenever a
query filters or orders by ``Trial.score``. Both end up on screen. If they
disagree, the trial page shows one number while the list it was sorted from
used another, and nothing on screen says which one is wrong.

The in-memory tests build detached ORM objects, the same way
``test_run_accuracy.py`` does. The last two need a real session: a correlated
subquery only runs in the database.
"""

from __future__ import annotations

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
import pytest
import sqlalchemy
from sqlalchemy import orm


def _result(score: float, weight: float) -> AssertionResult:
  """One assertion result carrying the snapshot it was weighted by."""
  return AssertionResult(
      assertion_snapshot=AssertionSnapshot(
          type=AssertionType.TEXT_CONTAINS, weight=weight, params={}
      ),
      passed=score >= 1.0,
      score=score,
  )


def _trial(*scored_weights: tuple[float, float]) -> Trial:
  """A detached trial with one result per (score, weight) pair."""
  trial = Trial(status=RunStatus.COMPLETED)
  for score, weight in scored_weights:
    trial.assertion_results.append(_result(score, weight))
  return trial


def _persisted_trial(
    session: orm.Session, *scored_weights: tuple[float, float]
) -> Trial:
  """The same trial, written out with the FK rows it needs."""
  agent = Agent(
      name="Test Agent", project_id="p", location="l", agent_resource_id="r"
  )
  suite_snapshot = TestSuiteSnapshot(name="Test Suite")
  session.add_all([agent, suite_snapshot])
  session.flush()

  example_snapshot = ExampleSnapshot(
      snapshot_suite_id=suite_snapshot.id, logical_id="L1", question="Q1"
  )
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=suite_snapshot.id,
      status=RunStatus.COMPLETED,
  )
  session.add_all([example_snapshot, run])
  session.flush()

  trial = Trial(
      run_id=run.id,
      example_snapshot_id=example_snapshot.id,
      status=RunStatus.COMPLETED,
  )
  for score, weight in scored_weights:
    result = _result(score, weight)
    result.assertion_snapshot.example_snapshot_id = example_snapshot.id
    trial.assertion_results.append(result)
  session.add(trial)
  session.commit()
  return trial


def _score_via_sql(session: orm.Session, trial: Trial) -> float | None:
  """Reads the score back through the subquery instead of the property."""
  return session.execute(
      sqlalchemy.select(Trial.score).where(Trial.id == trial.id)
  ).scalar_one()


def test_a_heavier_assertion_pulls_the_mean_towards_itself():
  # Weight 3 passing and weight 1 failing. The plain mean over the same two
  # rows is 0.5, so this is the case the old unweighted code got wrong.
  assert _trial((1.0, 3.0), (0.0, 1.0)).score == pytest.approx(0.75)


def test_zero_weight_results_do_not_move_the_score():
  """They are excluded from the numerator and the denominator, not just one."""
  weighted = _trial((1.0, 3.0), (0.0, 1.0))
  with_an_unweighted_pass = _trial((1.0, 3.0), (0.0, 1.0), (1.0, 0.0))

  assert with_an_unweighted_pass.score == pytest.approx(weighted.score)
  assert with_an_unweighted_pass.score == pytest.approx(0.75)


def test_a_trial_with_no_assertions_has_no_score():
  assert _trial().score is None


def test_a_trial_with_only_zero_weight_results_has_no_score():
  """Nothing was being scored, which is different from scoring zero."""
  assert _trial((1.0, 0.0), (0.0, 0.0)).score is None


def test_the_sql_expression_agrees_with_the_property(db_session: orm.Session):
  # Fractional weights, so a subquery that summed rows instead of weights
  # lands somewhere else. Expected: (0.8*2.5 + 0.2*0.5) / 3.0.
  trial = _persisted_trial(db_session, (0.8, 2.5), (0.2, 0.5), (1.0, 0.0))

  from_sql = _score_via_sql(db_session, trial)

  assert from_sql == pytest.approx(trial.score)
  assert from_sql == pytest.approx(0.7)


def test_the_sql_expression_returns_no_score_when_the_property_does(
    db_session: orm.Session,
):
  """A NULL here, not a zero: ordering by score must not rank it as worst."""
  trial = _persisted_trial(db_session, (1.0, 0.0))

  assert trial.score is None
  assert _score_via_sql(db_session, trial) is None
