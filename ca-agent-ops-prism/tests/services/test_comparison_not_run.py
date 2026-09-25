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

"""A case that never ran is not a regression.

The comparison read both sides with `trial.score or 0.0`. A PENDING or RUNNING
or CANCELLED trial has no score, so it came through as 0.0 and the case scored
as a fall to zero. Comparing a finished run against one still in flight
reported every unfinished case as a regression, and the accuracy delta was
dragged down by answers nobody had asked for yet.

Those cases are NOT_RUN now. They carry no deltas and they count towards no
total, the same way a case that exists on one side only does not.
"""

import datetime
from unittest import mock

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.comparison import ComparisonStatus
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import RunStatus
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.comparison_service import ComparisonService
import pytest

NOW = datetime.datetime.now(datetime.timezone.utc)

# The cases every test below draws from, in the order the suite held them.
CASES = ["case1", "case2"]


def _example(logical_id):
  """The snapshot row a trial was run against."""
  return ExampleSnapshot(logical_id=logical_id, question=logical_id.upper())


def _snapshot():
  """One run's snapshot of the suite, examples and all.

  A snapshot carries the examples its trials came from, and compare_runs
  reads the order of the report off that list. Seeded empty, every case here
  fell through to the tail that sorts whatever the two trial maps have left
  over, so the ordering path was never run. Each run snapshots the suite
  separately, which is why the two share an original_suite_id rather than an
  object.
  """
  snapshot = TestSuiteSnapshot(name="Suite", original_suite_id=7)
  snapshot.examples = [_example(logical_id) for logical_id in CASES]
  return snapshot


def _trial(
    tid, run_id, logical_id, status, score=None, latency=100, weight=1.0
):
  """One trial. A score of None leaves it with no assertion results.

  A weight of 0 gives it an assertion nobody scores, which is the other way a
  trial ends up with ``Trial.score`` of None while still being COMPLETED.
  """
  trial = Trial(
      id=tid,
      run_id=run_id,
      example_snapshot_id=tid,
      status=status,
      output_text="Response" if score is not None else None,
      created_at=NOW,
      started_at=NOW,
      completed_at=NOW + datetime.timedelta(milliseconds=latency),
      example_snapshot=_example(logical_id),
  )
  trial.assertion_results = []
  if score is not None:
    trial.assertion_results = [
        AssertionResult(
            score=score,
            passed=score >= 0.5,
            assertion_snapshot=AssertionSnapshot(
                id=tid,
                type=AssertionType.TEXT_CONTAINS,
                weight=weight,
                params={"value": "dummy"},
            ),
        )
    ]
  return trial


@pytest.fixture(name="service")
def _service():
  """The service with both repositories stubbed, as the unit tests do."""
  service = ComparisonService(
      mock.MagicMock(),
      run_repository=mock.MagicMock(),
      trial_repository=mock.MagicMock(),
  )
  agent = mock.MagicMock()
  agent.name = "Agent"
  runs = [
      Run(
          id=run_id,
          status=RunStatus.COMPLETED,
          test_suite_snapshot_id=run_id,
          agent_id=1,
          snapshot_suite=_snapshot(),
          agent=agent,
          created_at=NOW,
          is_archived=False,
      )
      for run_id in (1, 2)
  ]
  service.run_repository.get_by_id.side_effect = runs
  return service


@pytest.mark.parametrize(
    "status",
    [RunStatus.PENDING, RunStatus.RUNNING, RunStatus.CANCELLED],
)
def test_an_unfinished_challenger_is_not_run_not_a_regression(service, status):
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, "case1", RunStatus.COMPLETED, score=1.0)],
      [_trial(201, 2, "case1", status)],
  ]

  result = service.compare_runs(1, 2)

  case = result.cases[0]
  assert case.status == ComparisonStatus.NOT_RUN
  assert case.score_delta is None
  assert case.duration_delta is None
  assert result.delta.regressions_count == 0
  assert result.delta.accuracy_delta == 0.0
  assert result.delta.duration_delta_avg == 0.0


@pytest.mark.parametrize(
    "status",
    [RunStatus.PENDING, RunStatus.RUNNING, RunStatus.CANCELLED],
)
def test_an_unfinished_baseline_is_not_run_either(service, status):
  """The improvement the old code read here was the same arithmetic."""
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, "case1", status)],
      [_trial(201, 2, "case1", RunStatus.COMPLETED, score=1.0)],
  ]

  result = service.compare_runs(1, 2)

  assert result.cases[0].status == ComparisonStatus.NOT_RUN
  assert result.delta.improvements_count == 0
  assert result.delta.accuracy_delta == 0.0


def test_a_failed_trial_still_compares(service):
  """FAILED is a result: the agent answered and got it wrong.

  Run.accuracy scores it 0.0 and counts it. Bucketing it as NOT_RUN would hide
  the regression this comparison exists to show.
  """
  base = _trial(101, 1, "case1", RunStatus.COMPLETED, score=1.0)
  challenger = _trial(201, 2, "case1", RunStatus.FAILED)
  challenger.error_message = "boom"
  service.trial_repository.list_for_run.side_effect = [[base], [challenger]]

  result = service.compare_runs(1, 2)

  case = result.cases[0]
  assert case.status == ComparisonStatus.ERROR
  assert case.score_delta == -1.0
  assert result.delta.errors_count == 1


def test_a_completed_trial_nobody_scored_is_not_a_regression(service):
  """The same `or 0.0`, on the case the status check does not catch.

  A COMPLETED trial whose only assertion carries weight 0 has no score, and
  Run.accuracy drops it from the denominator. Read as 0.0 here, the compare
  page called it a fall from 1.0 while the run detail page was excluding the
  same trial from its average.
  """
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, "case1", RunStatus.COMPLETED, score=1.0)],
      [_trial(201, 2, "case1", RunStatus.COMPLETED, score=0.0, weight=0.0)],
  ]

  result = service.compare_runs(1, 2)

  case = result.cases[0]
  assert case.status == ComparisonStatus.NOT_RUN
  assert case.score_delta is None
  assert case.duration_delta is None
  assert result.delta.regressions_count == 0
  assert result.delta.accuracy_delta == 0.0
  assert result.delta.duration_delta_avg == 0.0


def test_an_unscored_baseline_is_not_an_improvement_either(service):
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, "case1", RunStatus.COMPLETED, score=0.0, weight=0.0)],
      [_trial(201, 2, "case1", RunStatus.COMPLETED, score=1.0)],
  ]

  result = service.compare_runs(1, 2)

  assert result.cases[0].status == ComparisonStatus.NOT_RUN
  assert result.delta.improvements_count == 0
  assert result.delta.accuracy_delta == 0.0


def test_a_failed_trial_with_no_error_message_still_scores_zero(service):
  """The other direction: FAILED is the one place a None score means 0.0.

  Run.accuracy counts a FAILED trial as a zero, so the comparison has to as
  well. Treating every None score as uncomparable would bucket the worst
  regression there is as NOT_RUN.
  """
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, "case1", RunStatus.COMPLETED, score=1.0)],
      [_trial(201, 2, "case1", RunStatus.FAILED)],
  ]

  result = service.compare_runs(1, 2)

  case = result.cases[0]
  assert case.status == ComparisonStatus.REGRESSION
  assert case.score_delta == -1.0
  assert result.delta.regressions_count == 1


def test_the_finished_cases_are_still_averaged_on_their_own(service):
  """The NOT_RUN case must not dilute the delta, nor suppress it."""
  service.trial_repository.list_for_run.side_effect = [
      [
          _trial(101, 1, "case1", RunStatus.COMPLETED, score=1.0),
          _trial(102, 1, "case2", RunStatus.COMPLETED, score=1.0),
      ],
      [
          _trial(201, 2, "case1", RunStatus.COMPLETED, score=0.0),
          _trial(202, 2, "case2", RunStatus.RUNNING),
      ],
  ]

  result = service.compare_runs(1, 2)

  # Snapshot order, which is the order the rows are read in.
  assert [c.logical_id for c in result.cases] == CASES
  by_id = {c.logical_id: c for c in result.cases}
  assert by_id["case1"].status == ComparisonStatus.REGRESSION
  assert by_id["case2"].status == ComparisonStatus.NOT_RUN
  # Averaged over case1 alone, not halved by the case that never ran.
  assert result.delta.accuracy_delta == pytest.approx(-1.0)
  assert result.delta.regressions_count == 1
