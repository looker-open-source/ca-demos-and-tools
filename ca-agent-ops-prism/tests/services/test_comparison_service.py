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
from prism.server.services.comparison_service import ComparisonService


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
    # Setup Runs
    now = datetime.datetime.now(datetime.timezone.utc)
    suite1 = mock.MagicMock(examples=[])
    suite1.name = "Suite 1"
    agent1 = mock.MagicMock()
    agent1.name = "Agent 1"
    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=suite1,
        agent=agent1,
        created_at=now,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=suite1,
        agent=agent1,
        created_at=now,
    )
    self.run_repository.get_by_id.side_effect = [run1, run2]

    # Common Attributes
    now = datetime.datetime.now(datetime.timezone.utc)

    def create_trial(tid, score, latency, logical_id, question, run_id):

      t = Trial(
          id=tid,
          run_id=run_id,
          example_snapshot_id=tid,  # Dummy
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

    # Check Delta
    # Regressions: Case 2
    self.assertEqual(result.delta.regressions_count, 1)
    # Improvements: Case 3
    self.assertEqual(result.delta.improvements_count, 1)
    # Same: Case 1
    self.assertEqual(result.delta.same_count, 1)

    # Check Cases
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

  def test_compare_runs_populates_reasoning(self):
    """Verifies that assertion reasoning is correctly populated in TrialSchema."""
    now = datetime.datetime.now(datetime.timezone.utc)

    suite1 = mock.MagicMock(examples=[])
    suite1.name = "Suite 1"
    agent1 = mock.MagicMock()
    agent1.name = "Agent 1"
    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=suite1,
        agent=agent1,
        created_at=now,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=suite1,
        agent=agent1,
        created_at=now,
    )
    self.run_repository.get_by_id.side_effect = [run1, run2]

    # Create trial with reasoning
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

  def test_compare_runs_excludes_errors(self):
    """Verifies that trials with errors are excluded from accuracy and latency deltas."""
    now = datetime.datetime.now(datetime.timezone.utc)
    suite1 = mock.MagicMock(examples=[])
    suite1.name = "Suite 1"
    agent = mock.MagicMock()
    agent.name = "Agent 1"
    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        test_suite_snapshot_id=1,
        agent_id=1,
        snapshot_suite=suite1,
        agent=agent,
        created_at=now,
    )
    self.run_repository.get_by_id.side_effect = [run1, run1]

    # Success trial
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

    # Error trial (in Challenger)
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

    # Metrics should only reflect the success trial
    # Accuracy delta: (1.0 - 1.0) / 1 = 0.0
    self.assertEqual(result.delta.accuracy_delta, 0.0)
    # Duration delta: (150 - 100) / 1 = 50.0
    self.assertEqual(result.delta.duration_delta_avg, 50.0)
    # Error count should be 1
    self.assertEqual(result.delta.errors_count, 1)

    # Check case statuses
    case_map = {c.logical_id: c for c in result.cases}
    self.assertEqual(case_map["success"].status, ComparisonStatus.STABLE)
    self.assertEqual(case_map["error_chal"].status, ComparisonStatus.ERROR)


if __name__ == "__main__":
  unittest.main()
