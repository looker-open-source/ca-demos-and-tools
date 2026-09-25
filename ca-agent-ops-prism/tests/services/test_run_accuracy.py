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

"""Unit tests for ``Run.accuracy``.

The rule is short but has three cases that pull in different directions, and
getting it wrong isn't visible: it still reports a plausible number. It once
excluded errored trials from the denominator, so a run where half the trials
crashed displayed as 100% accurate.

These build detached ORM objects instead of going through a session. The
property reads ``self.trials`` and ``trial.assertion_results``, both of which
work in memory, and all we want to pin here is the arithmetic.
"""

from __future__ import annotations

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
import pytest


def _trial(status: RunStatus, *scores: float, weight: float = 1.0) -> Trial:
  """A trial with one assertion result per score."""
  trial = Trial(status=status)
  for score in scores:
    trial.assertion_results.append(
        AssertionResult(
            assertion_snapshot=AssertionSnapshot(
                type=AssertionType.TEXT_CONTAINS, weight=weight, params={}
            ),
            passed=score >= 1.0,
            score=score,
        )
    )
  return trial


def _run(*trials: Trial) -> Run:
  run = Run()
  run.trials.extend(trials)
  return run


def test_no_trials_has_no_accuracy():
  assert _run().accuracy is None


def test_mean_over_completed_trials():
  run = _run(
      _trial(RunStatus.COMPLETED, 1.0),
      _trial(RunStatus.COMPLETED, 0.0),
  )
  assert run.accuracy == pytest.approx(0.5)


def test_failed_trials_score_zero_rather_than_dropping_out():
  """The regression this property was fixed for."""
  run = _run(
      _trial(RunStatus.COMPLETED, 1.0),
      _trial(RunStatus.FAILED),
  )
  assert run.accuracy == pytest.approx(0.5), (
      "A crashed trial was excluded from the denominator, so a run that half "
      "failed reports as fully accurate."
  )


def test_completed_trial_with_no_weighted_assertions_is_excluded():
  """Distinct from FAILED: there was nothing to be right or wrong about."""
  run = _run(
      _trial(RunStatus.COMPLETED, 1.0),
      _trial(RunStatus.COMPLETED, 0.0, weight=0.0),
  )
  assert run.accuracy == pytest.approx(1.0)


def test_unfinished_trials_are_excluded():
  """A run in flight reports the accuracy of what has finished so far."""
  run = _run(
      _trial(RunStatus.COMPLETED, 1.0),
      _trial(RunStatus.RUNNING),
      _trial(RunStatus.PENDING),
      _trial(RunStatus.CANCELLED),
  )
  assert run.accuracy == pytest.approx(1.0)


def test_only_unfinished_trials_has_no_accuracy():
  assert _run(_trial(RunStatus.RUNNING)).accuracy is None


def test_only_failed_trials_is_zero_not_none():
  """Zero and "not measured" are different answers and must look different."""
  assert _run(_trial(RunStatus.FAILED)).accuracy == pytest.approx(0.0)
