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
import unittest
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


def _snapshot(name, cases):
  """A run's snapshot suite, holding the examples its trials came from.

  cases is a list of (logical_id, question) pairs, in the order the suite
  held them. A snapshot is never empty in production, and seeding it empty
  sent every case down the tail of compare_runs that sorts whatever the two
  trial maps have left over. The ordering the report is read in came from
  that tail, so it could have broken with nothing going red.

  Each run gets its own snapshot carrying the same original_suite_id, which
  is what two runs of one suite look like. One shared mock satisfied the
  same-suite guard without either side of it being a real value.
  """
  snapshot = TestSuiteSnapshot(name=name, original_suite_id=7)
  snapshot.examples = [
      ExampleSnapshot(logical_id=logical_id, question=question)
      for logical_id, question in cases
  ]
  return snapshot


def _trial(
    tid,
    run_id,
    logical_id,
    question,
    now,
    score=None,
    latency=100,
    status=RunStatus.COMPLETED,
    error_message=None,
):
  """One trial. A score of None leaves it with no assertion results."""
  trial = Trial(
      id=tid,
      run_id=run_id,
      example_snapshot_id=tid,
      status=status,
      error_message=error_message,
      created_at=now,
      started_at=now,
      completed_at=now + datetime.timedelta(milliseconds=latency),
      example_snapshot=ExampleSnapshot(
          logical_id=logical_id, question=question
      ),
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
                weight=1.0,
                params={"value": "dummy"},
            ),
        )
    ]
  return trial


class TestComparisonService(unittest.TestCase):

  def setUp(self):
    self.session = mock.MagicMock()
    self.run_repository = mock.MagicMock()
    self.trial_repository = mock.MagicMock()
    self.service = ComparisonService(
        self.session,
        run_repository=self.run_repository,
        trial_repository=self.trial_repository,
    )

  def test_compare_runs_success(self):
    now = datetime.datetime.now(datetime.timezone.utc)
    base_suite = _snapshot(
        "Suite 1",
        [("case1", "Q1"), ("case2", "Q2"), ("case3", "Q3"), ("case5", "Q5")],
    )
    chal_suite = _snapshot(
        "Suite 1",
        [("case1", "Q1"), ("case2", "Q2"), ("case3", "Q3"), ("case4", "Q4")],
    )
    agent1 = mock.MagicMock()
    agent1.name = "Agent 1"
    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=base_suite,
        agent=agent1,
        created_at=now,
        is_archived=False,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=2,
        agent_id=1,
        snapshot_suite=chal_suite,
        agent=agent1,
        created_at=now,
        is_archived=False,
    )
    self.run_repository.get_by_id.side_effect = [run1, run2]

    def create_trial(tid, score, latency, logical_id, question, run_id):

      t = Trial(
          id=tid,
          run_id=run_id,
          example_snapshot_id=tid,
          status=RunStatus.COMPLETED,
          output_text="Response",
          created_at=now,
          started_at=now,
          completed_at=now + datetime.timedelta(milliseconds=latency),
          example_snapshot=ExampleSnapshot(
              logical_id=logical_id, question=question
          ),
      )
      if score is not None:
        t.assertion_results = [
            AssertionResult(
                score=score,
                passed=score >= 0.5,
                assertion_snapshot=AssertionSnapshot(
                    id=tid,
                    type=AssertionType.TEXT_CONTAINS,
                    weight=1.0,
                    params={"value": "dummy"},
                ),
            )
        ]
      else:
        t.assertion_results = []
      return t

    # Case 1: Stable (Same score)
    t1_base = create_trial(101, 1.0, 100, "case1", "Q1", 1)
    t1_chal = create_trial(201, 1.0, 120, "case1", "Q1", 2)

    # Case 2: Regression (1.0 -> 0.0)
    t2_base = create_trial(102, 1.0, 100, "case2", "Q2", 1)
    t2_chal = create_trial(202, 0.0, 100, "case2", "Q2", 2)

    # Case 3: Improvement (0.5 -> 0.9)
    t3_base = create_trial(103, 0.5, 100, "case3", "Q3", 1)
    t3_chal = create_trial(203, 0.9, 100, "case3", "Q3", 2)

    # Case 4: New (Only in Challenger)
    t4_chal = create_trial(204, 1.0, 100, "case4", "Q4", 2)

    # Case 5: Removed (Only in Base)
    t5_base = create_trial(105, 1.0, 100, "case5", "Q5", 1)

    self.trial_repository.list_for_run.side_effect = [
        [t1_base, t2_base, t3_base, t5_base],  # Base Trials
        [t1_chal, t2_chal, t3_chal, t4_chal],  # Challenger Trials
    ]

    result = self.service.compare_runs(1, 2)

    self.assertEqual(result.metadata.total_cases, 5)

    # Challenger snapshot order, the base-only case after it.
    self.assertEqual(
        [c.logical_id for c in result.cases],
        ["case1", "case2", "case3", "case4", "case5"],
    )

    # Regressions: Case 2
    self.assertEqual(result.delta.regressions_count, 1)
    # Improvements: Case 3
    self.assertEqual(result.delta.improvements_count, 1)
    # Same: Case 1
    self.assertEqual(result.delta.same_count, 1)

    case_map = {c.logical_id: c for c in result.cases}

    self.assertEqual(case_map["case1"].status, ComparisonStatus.STABLE)
    self.assertEqual(case_map["case1"].score_delta, 0.0)
    self.assertEqual(case_map["case1"].duration_delta, 20)

    self.assertEqual(case_map["case2"].status, ComparisonStatus.REGRESSION)
    self.assertEqual(case_map["case2"].score_delta, -1.0)

    self.assertEqual(case_map["case3"].status, ComparisonStatus.IMPROVED)
    self.assertAlmostEqual(case_map["case3"].score_delta, 0.4)

    self.assertEqual(case_map["case4"].status, ComparisonStatus.NEW)
    self.assertIsNone(case_map["case4"].base_trial)

    self.assertEqual(case_map["case5"].status, ComparisonStatus.REMOVED)
    self.assertIsNone(case_map["case5"].challenger_trial)

  def test_compare_runs_keeps_both_questions_of_a_duplicated_logical_id(self):
    """Nothing stops a suite holding two questions with one logical_id.

    The case key was the logical_id alone, so the second trial overwrote the
    first in the map. Two questions came back as one case, total_cases
    disagreed with the run, and the surviving row differenced two trials that
    were not answers to the same question.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    ex_first = ExampleSnapshot(id=1, logical_id="dup", question="Q1")
    ex_second = ExampleSnapshot(id=2, logical_id="dup", question="Q2")
    snapshot = TestSuiteSnapshot(id=1, name="Suite", original_suite_id=7)
    snapshot.examples = [ex_first, ex_second]

    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=snapshot,
        created_at=now,
        is_archived=False,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=snapshot,
        created_at=now,
        is_archived=False,
    )
    self.run_repository.get_by_id.side_effect = [run1, run2]

    def scored_trial(tid, run_id, example, score):
      trial = Trial(
          id=tid,
          run_id=run_id,
          example_snapshot_id=example.id,
          status=RunStatus.COMPLETED,
          created_at=now,
          started_at=now,
          completed_at=now,
          example_snapshot=example,
      )
      trial.assertion_results = [
          AssertionResult(
              score=score,
              passed=score >= 0.5,
              assertion_snapshot=AssertionSnapshot(
                  id=tid,
                  type=AssertionType.TEXT_CONTAINS,
                  weight=1.0,
                  params={"value": "dummy"},
              ),
          )
      ]
      return trial

    self.trial_repository.list_for_run.side_effect = [
        [
            scored_trial(101, 1, ex_first, 1.0),
            scored_trial(102, 1, ex_second, 1.0),
        ],
        [
            scored_trial(201, 2, ex_first, 1.0),
            scored_trial(202, 2, ex_second, 0.0),
        ],
    ]

    result = self.service.compare_runs(1, 2)

    self.assertEqual(result.metadata.total_cases, 2)
    # Snapshot order, so the first row is the first question. Only the second
    # one lost its point.
    self.assertEqual([c.score_delta for c in result.cases], [0.0, -1.0])
    self.assertEqual(result.delta.regressions_count, 1)
    self.assertEqual(result.delta.same_count, 1)

  def test_compare_runs_populates_reasoning(self):
    now = datetime.datetime.now(datetime.timezone.utc)

    agent1 = mock.MagicMock()
    agent1.name = "Agent 1"
    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=_snapshot("Suite 1", [("case1", "Q1")]),
        agent=agent1,
        created_at=now,
        is_archived=False,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=2,
        agent_id=1,
        snapshot_suite=_snapshot("Suite 1", [("case1", "Q1")]),
        agent=agent1,
        created_at=now,
        is_archived=False,
    )
    self.run_repository.get_by_id.side_effect = [run1, run2]

    t1_base = Trial(
        id=101,
        run_id=1,
        example_snapshot_id=1,
        status=RunStatus.COMPLETED,
        created_at=now,
        example_snapshot=ExampleSnapshot(logical_id="case1", question="Q1"),
    )
    t1_base.assertion_results = [
        AssertionResult(
            score=1.0,
            passed=True,
            reasoning="Expected reason",
            assertion_snapshot=AssertionSnapshot(
                id=1,
                type=AssertionType.TEXT_CONTAINS,
                weight=1.0,
                params={"value": "test"},
            ),
        )
    ]

    self.trial_repository.list_for_run.side_effect = [[t1_base], [t1_base]]

    result = self.service.compare_runs(1, 2)
    case = result.cases[0]
    self.assertEqual(
        case.base_trial.assertion_results[0].reasoning, "Expected reason"
    )
    self.assertEqual(
        case.challenger_trial.assertion_results[0].reasoning, "Expected reason"
    )

  def test_compare_runs_counts_errors_in_accuracy_but_not_latency(self):
    """An errored trial is a zero in the accuracy delta, not an absence.

    Run.accuracy scores a FAILED trial 0.0, so a run whose trials all failed
    reads 0% on the run detail page. Dropping those trials from the comparison
    had the same pair report "+0.0% accuracy, 0 regressions" with every row
    below it showing -100%. Latency is the exception: a trial that died on its
    first event is fast for a reason that is not a speed-up.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    agent = mock.MagicMock()
    agent.name = "Agent 1"
    cases = [("success", "Q1"), ("error_chal", "Q2")]
    runs = [
        Run(
            id=run_id,
            status=RunStatus.COMPLETED,
            test_suite_snapshot_id=run_id,
            agent_id=1,
            snapshot_suite=_snapshot("Suite 1", cases),
            agent=agent,
            created_at=now,
            is_archived=False,
        )
        for run_id in (1, 2)
    ]
    self.run_repository.get_by_id.side_effect = runs

    t_success_base = Trial(
        id=101,
        run_id=1,
        status=RunStatus.COMPLETED,
        started_at=now,
        completed_at=now + datetime.timedelta(milliseconds=100),
        created_at=now,
        modified_at=now,
        example_snapshot_id=101,
        example_snapshot=ExampleSnapshot(logical_id="success", question="Q1"),
    )
    t_success_base.assertion_results = [
        AssertionResult(
            score=1.0,
            passed=True,
            created_at=now,
            modified_at=now,
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS,
                weight=1.0,
                params={"value": "test"},
                created_at=now,
                modified_at=now,
                example_snapshot_id=101,
            ),
        )
    ]

    t_success_chal = Trial(
        id=201,
        run_id=2,
        status=RunStatus.COMPLETED,
        started_at=now,
        completed_at=now + datetime.timedelta(milliseconds=150),  # +50ms
        created_at=now,
        modified_at=now,
        example_snapshot_id=201,
        example_snapshot=ExampleSnapshot(logical_id="success", question="Q1"),
    )
    t_success_chal.assertion_results = [
        AssertionResult(
            score=1.0,
            passed=True,
            created_at=now,
            modified_at=now,
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS,
                weight=1.0,
                params={"value": "test"},
                created_at=now,
                modified_at=now,
                example_snapshot_id=201,
            ),
        )
    ]

    t_error_chal = Trial(
        id=202,
        run_id=2,
        status=RunStatus.FAILED,
        error_message="Failed to execute",
        started_at=now,
        completed_at=now + datetime.timedelta(milliseconds=0),
        created_at=now,
        modified_at=now,
        example_snapshot_id=202,
        example_snapshot=ExampleSnapshot(
            logical_id="error_chal", question="Q2"
        ),
    )
    t_error_chal.assertion_results = []

    t_error_base = Trial(
        id=102,
        run_id=1,
        status=RunStatus.COMPLETED,
        started_at=now,
        completed_at=now + datetime.timedelta(milliseconds=100),
        created_at=now,
        modified_at=now,
        example_snapshot_id=102,
        example_snapshot=ExampleSnapshot(
            logical_id="error_chal", question="Q2"
        ),
    )
    t_error_base.assertion_results = [
        AssertionResult(
            score=1.0,
            passed=True,
            created_at=now,
            modified_at=now,
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS,
                weight=1.0,
                params={"value": "test"},
                created_at=now,
                modified_at=now,
                example_snapshot_id=102,
            ),
        )
    ]

    self.trial_repository.list_for_run.side_effect = [
        [t_success_base, t_error_base],
        [t_success_chal, t_error_chal],
    ]

    result = self.service.compare_runs(1, 2)

    # Accuracy is over both cases, the errored one scoring 0.0 against a base
    # of 1.0: (0.0 + -1.0) / 2. Latency is the success trial alone, so
    # (150 - 100) / 1.
    self.assertEqual(result.delta.accuracy_delta, -0.5)
    self.assertEqual(result.delta.duration_delta_avg, 50.0)
    self.assertEqual(result.delta.errors_count, 1)
    # The case lost a point, but its bucket is the error bucket alone. Its
    # status is ERROR, and the Regressed chip counts rows by status.
    self.assertEqual(result.delta.regressions_count, 0)

    case_map = {c.logical_id: c for c in result.cases}
    self.assertEqual(case_map["success"].status, ComparisonStatus.STABLE)
    self.assertEqual(case_map["error_chal"].status, ComparisonStatus.ERROR)

  def _two_runs(self, cases, now):
    """Two runs of one suite, each with its own snapshot of the same cases."""
    agent = mock.MagicMock()
    agent.name = "Agent 1"
    return [
        Run(
            id=run_id,
            status=RunStatus.COMPLETED,
            test_suite_snapshot_id=run_id,
            agent_id=1,
            snapshot_suite=_snapshot("Suite 1", cases),
            agent=agent,
            created_at=now,
            is_archived=False,
        )
        for run_id in (1, 2)
    ]

  def test_every_case_lands_in_one_bucket_only(self):
    """The Regressions card and the Regressed chip counted different sets.

    An errored pair was counted by its score delta and then again as an
    error, and its status was overwritten to ERROR last. The card read
    regressions_count and showed 1, the chip counted rows by status and showed
    0, so clicking it listed nothing. The four counts could also sum past
    total_cases, which is the number on the All chip.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    cases = [
        ("stable", "Q1"),
        ("regressed", "Q2"),
        ("improved", "Q3"),
        ("errored", "Q4"),
    ]
    self.run_repository.get_by_id.side_effect = self._two_runs(cases, now)

    self.trial_repository.list_for_run.side_effect = [
        [
            _trial(101, 1, "stable", "Q1", now, score=1.0),
            _trial(102, 1, "regressed", "Q2", now, score=1.0),
            _trial(103, 1, "improved", "Q3", now, score=0.0),
            _trial(104, 1, "errored", "Q4", now, score=1.0),
        ],
        [
            _trial(201, 2, "stable", "Q1", now, score=1.0),
            _trial(202, 2, "regressed", "Q2", now, score=0.0),
            _trial(203, 2, "improved", "Q3", now, score=1.0),
            _trial(
                204,
                2,
                "errored",
                "Q4",
                now,
                status=RunStatus.FAILED,
                error_message="boom",
            ),
        ],
    ]

    result = self.service.compare_runs(1, 2)

    counts = {
        ComparisonStatus.REGRESSION: result.delta.regressions_count,
        ComparisonStatus.IMPROVED: result.delta.improvements_count,
        ComparisonStatus.STABLE: result.delta.same_count,
        ComparisonStatus.ERROR: result.delta.errors_count,
    }
    for status, count in counts.items():
      rows = [c for c in result.cases if c.status == status]
      self.assertEqual(count, len(rows), status)
      self.assertEqual(count, 1, status)
    self.assertEqual(sum(counts.values()), result.metadata.total_cases)

    # The errored case is out of the regression bucket, not out of the
    # accuracy average: (0.0 + -1.0 + 1.0 + -1.0) / 4.
    case_map = {c.logical_id: c for c in result.cases}
    self.assertEqual(case_map["errored"].score_delta, -1.0)
    self.assertEqual(result.delta.accuracy_delta, -0.25)

  def test_a_one_sided_errored_case_is_not_counted_as_an_error(self):
    """errors_count is the pairs the latency average dropped.

    A question the challenger had added was never in that average, so erroring
    its trial fired the "excluded from latency calculations" note over a case
    that had been excluded from nothing. Its mirror, a removed case whose base
    trial errored, counted nothing at all.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    base_run, chal_run = self._two_runs([("stable", "Q1")], now)
    base_run.snapshot_suite.examples.append(
        ExampleSnapshot(logical_id="dropped", question="Q2")
    )
    chal_run.snapshot_suite.examples.append(
        ExampleSnapshot(logical_id="added", question="Q3")
    )
    self.run_repository.get_by_id.side_effect = [base_run, chal_run]

    self.trial_repository.list_for_run.side_effect = [
        [
            _trial(101, 1, "stable", "Q1", now, score=1.0),
            _trial(
                102,
                1,
                "dropped",
                "Q2",
                now,
                status=RunStatus.FAILED,
                error_message="boom",
            ),
        ],
        [
            _trial(201, 2, "stable", "Q1", now, score=1.0),
            _trial(
                202,
                2,
                "added",
                "Q3",
                now,
                status=RunStatus.FAILED,
                error_message="boom",
            ),
        ],
    ]

    result = self.service.compare_runs(1, 2)

    self.assertEqual(result.delta.errors_count, 0)
    case_map = {c.logical_id: c for c in result.cases}
    self.assertEqual(case_map["added"].status, ComparisonStatus.NEW)
    self.assertEqual(case_map["dropped"].status, ComparisonStatus.REMOVED)


if __name__ == "__main__":
  unittest.main()
