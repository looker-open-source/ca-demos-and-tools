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

"""Two runs of different suites are not a comparison.

The Compare modal opened from the Evaluations page header does not filter the
run list, so any two runs could be picked. Nothing checked they were runs of
the same suite. Every logical_id then lands on one side only, every case comes
out NEW or REMOVED, and the report reads "0.0% change, 0 regressions" over a
set where nothing was compared at all.

It raises now. The UI renders a ValueError from this service as an alert.
"""

import datetime
from unittest import mock

from prism.common.schemas.comparison import ComparisonStatus
from prism.server.models.run import Run
from prism.server.models.run import RunStatus
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.server.services.comparison_service import ComparisonService
import pytest

NOW = datetime.datetime.now(datetime.timezone.utc)


def _snapshot(snapshot_id, suite_id, name, logical_id):
  """A frozen suite holding one question."""
  snapshot = TestSuiteSnapshot(
      id=snapshot_id, name=name, original_suite_id=suite_id
  )
  snapshot.examples = [
      ExampleSnapshot(
          id=snapshot_id, logical_id=logical_id, question=logical_id.upper()
      )
  ]
  return snapshot


def _run(run_id, snapshot):
  return Run(
      id=run_id,
      status=RunStatus.COMPLETED,
      snapshot_suite=snapshot,
      test_suite_snapshot_id=snapshot.id,
      agent_id=1,
      created_at=NOW,
      is_archived=False,
  )


def _trial(trial_id, run_id, snapshot):
  return Trial(
      id=trial_id,
      run_id=run_id,
      example_snapshot_id=snapshot.examples[0].id,
      status=RunStatus.COMPLETED,
      created_at=NOW,
      example_snapshot=snapshot.examples[0],
  )


@pytest.fixture(name="service")
def _service():
  return ComparisonService(
      mock.MagicMock(),
      run_repository=mock.MagicMock(),
      trial_repository=mock.MagicMock(),
  )


def test_comparing_runs_of_two_different_suites_raises(service):
  base_snapshot = _snapshot(1, 11, "Sales QA", "sales1")
  challenger_snapshot = _snapshot(2, 22, "Ops QA", "ops1")
  service.run_repository.get_by_id.side_effect = [
      _run(1, base_snapshot),
      _run(2, challenger_snapshot),
  ]
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, base_snapshot)],
      [_trial(201, 2, challenger_snapshot)],
  ]

  with pytest.raises(ValueError) as caught:
    service.compare_runs(1, 2)

  # The alert has to say which suites, or the operator is left guessing why a
  # pair the dropdown offered them will not compare.
  assert "Sales QA" in str(caught.value)
  assert "Ops QA" in str(caught.value)


def test_two_snapshots_of_no_suite_at_all_raise(service):
  """A null original_suite_id is not evidence the suites match.

  None != None is False, so two snapshots that point at nothing walked through
  the guard and produced the empty report it exists to stop.
  """
  base_snapshot = _snapshot(1, None, "Sales QA", "sales1")
  challenger_snapshot = _snapshot(2, None, "Ops QA", "ops1")
  service.run_repository.get_by_id.side_effect = [
      _run(1, base_snapshot),
      _run(2, challenger_snapshot),
  ]
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, base_snapshot)],
      [_trial(201, 2, challenger_snapshot)],
  ]

  with pytest.raises(ValueError):
    service.compare_runs(1, 2)


def test_two_runs_of_the_same_suite_still_compare(service):
  """The suite is the same one even after it has been renamed.

  The check is on original_suite_id, so a snapshot taken before the rename and
  one taken after are still the same suite. On the name they would not be.
  """
  base_snapshot = _snapshot(1, 11, "Sales QA", "case1")
  challenger_snapshot = _snapshot(2, 11, "Adhoc Checks", "case1")
  service.run_repository.get_by_id.side_effect = [
      _run(1, base_snapshot),
      _run(2, challenger_snapshot),
  ]
  service.trial_repository.list_for_run.side_effect = [
      [_trial(101, 1, base_snapshot)],
      [_trial(201, 2, challenger_snapshot)],
  ]

  result = service.compare_runs(1, 2)

  assert [c.logical_id for c in result.cases] == ["case1"]
  # Both sides are present, so it is not the NEW-and-REMOVED pair a mismatched
  # comparison produces.
  assert result.cases[0].status != ComparisonStatus.NEW
  assert result.cases[0].status != ComparisonStatus.REMOVED
