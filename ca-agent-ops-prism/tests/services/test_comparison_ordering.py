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

from prism.server.models.run import Run
from prism.server.models.run import RunStatus
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.comparison_service import ComparisonService


class TestComparisonOrdering(unittest.TestCase):

  def setUp(self):
    self.session = mock.MagicMock()
    self.run_repository = mock.MagicMock()
    self.trial_repository = mock.MagicMock()
    self.service = ComparisonService(
        self.session,
        run_repository=self.run_repository,
        trial_repository=self.trial_repository,
    )

  def test_compare_runs_respects_snapshot_order(self):
    now = datetime.datetime.now(datetime.timezone.utc)
    ex_a = ExampleSnapshot(id=1, logical_id="caseA", question="Q A")
    ex_b = ExampleSnapshot(id=2, logical_id="caseB", question="Q B")
    ex_c = ExampleSnapshot(id=3, logical_id="caseC", question="Q C")

    snapshot = TestSuiteSnapshot(id=1, name="Suite", original_suite_id=7)
    snapshot.examples = [
        ex_b,
        ex_a,
        ex_c,
    ]  # Out of alphabetical order, so sorting by name would show up.

    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        snapshot_suite=snapshot,
        test_suite_snapshot_id=1,
        agent_id=1,
        created_at=now,
        is_archived=False,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        snapshot_suite=snapshot,
        test_suite_snapshot_id=1,
        agent_id=1,
        created_at=now,
        is_archived=False,
    )

    self.run_repository.get_by_id.side_effect = [run1, run2]

    t_a = Trial(
        id=10,
        run_id=1,
        example_snapshot_id=1,
        status=RunStatus.COMPLETED,
        example_snapshot=ex_a,
        created_at=now,
    )
    t_b = Trial(
        id=20,
        run_id=1,
        example_snapshot_id=2,
        status=RunStatus.COMPLETED,
        example_snapshot=ex_b,
        created_at=now,
    )
    t_c = Trial(
        id=30,
        run_id=1,
        example_snapshot_id=3,
        status=RunStatus.COMPLETED,
        example_snapshot=ex_c,
        created_at=now,
    )

    self.trial_repository.list_for_run.side_effect = [
        # The repository has no order of its own, so the service is the only
        # thing that can put the cases back into snapshot order.
        [t_a, t_c, t_b],
        [t_c, t_b, t_a],
    ]

    result = self.service.compare_runs(1, 2)

    ordered_logical_ids = [c.logical_id for c in result.cases]
    self.assertEqual(ordered_logical_ids, ["caseB", "caseA", "caseC"])

  def test_compare_runs_appends_base_only_cases(self):
    # Base Snapshot (Case A, Case B)
    ex_a = ExampleSnapshot(id=1, logical_id="caseA", question="Q A")
    ex_b = ExampleSnapshot(id=2, logical_id="caseB", question="Q B")
    # Two snapshots of one suite, so the same-suite guard lets them compare.
    snap1 = TestSuiteSnapshot(id=1, name="Suite 1", original_suite_id=7)
    snap1.examples = [ex_a, ex_b]

    # Challenger Snapshot (Case C, Case A)
    ex_c = ExampleSnapshot(id=3, logical_id="caseC", question="Q C")
    snap2 = TestSuiteSnapshot(id=2, name="Suite 2", original_suite_id=7)
    snap2.examples = [ex_c, ex_a]

    run1 = Run(
        id=1,
        status=RunStatus.COMPLETED,
        snapshot_suite=snap1,
        test_suite_snapshot_id=1,
        agent_id=1,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        is_archived=False,
    )
    run2 = Run(
        id=2,
        status=RunStatus.COMPLETED,
        snapshot_suite=snap2,
        test_suite_snapshot_id=2,
        agent_id=1,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        is_archived=False,
    )

    self.run_repository.get_by_id.side_effect = [run1, run2]

    t_a = Trial(
        id=10,
        run_id=1,
        example_snapshot_id=1,
        status=RunStatus.COMPLETED,
        example_snapshot=ex_a,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    t_b = Trial(
        id=20,
        run_id=1,
        example_snapshot_id=2,
        status=RunStatus.COMPLETED,
        example_snapshot=ex_b,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    t_c = Trial(
        id=30,
        run_id=2,
        example_snapshot_id=3,
        status=RunStatus.COMPLETED,
        example_snapshot=ex_c,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )

    self.trial_repository.list_for_run.side_effect = [
        [t_a, t_b],
        [t_c, t_a],
    ]

    result = self.service.compare_runs(1, 2)

    # The challenger's order first, then whatever only the base had.
    ordered_logical_ids = [c.logical_id for c in result.cases]
    self.assertEqual(ordered_logical_ids, ["caseC", "caseA", "caseB"])


if __name__ == "__main__":
  unittest.main()
