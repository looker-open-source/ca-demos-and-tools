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

"""Regression: errored trials were dropped from the accuracy denominator.

``Run.accuracy`` averaged ``trial.score`` over trials whose score was not None.
A FAILED trial produces no assertion results, so its score is None and it fell
out of the average. A run where half the trials crashed reported 100% accuracy.

``render_run_detail_components`` computes the same average a second time for
the "Avg Accuracy" card. Both are checked here, since a correct number on the
list page and a wrong one on the detail page still misleads.

A COMPLETED trial with no weighted assertions is a different case: nothing was
asked of it, so it can't be right or wrong, and it stays excluded.
``test_accuracy_ignores_unasserted_trials`` pins that, so a later "fix" that
scores it 0 fails here.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import EvaluationIds
import pytest

pytestmark = pytest.mark.e2e

_ASSERTION = (AssertionType.TEXT_CONTAINS, {"value": "128"})


def _run_with_one_pass_and_one_error(seed):
  """A COMPLETED run: one trial passed everything, one trial crashed."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite, question="How many orders were there?", assertions=[_ASSERTION]
  )
  seed.example(
      suite, question="How many customers were there?", assertions=[_ASSERTION]
  )
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)

  passed, errored = sorted(run.trials, key=lambda t: t.id)
  seed.finish_trial(passed, passed=True)
  seed.finish_trial(
      errored,
      status=RunStatus.FAILED,
      error_message="The agent timed out.",
  )
  return run


def test_detail_page_accuracy_counts_errored_trials(
    page: Page, base_url: str, seed
):
  """One of two trials crashed, so the run is 50% accurate, not 100%."""
  run = _run_with_one_pass_and_one_error(seed)

  page.goto(f"{base_url}/evaluations/runs/{run.id}")
  page.wait_for_load_state("networkidle")

  stats = page.locator(f"#{EvaluationIds.RUN_DETAIL_STATS}")
  expect(stats).to_contain_text("50.0%")
  expect(stats).not_to_contain_text("100.0%")


def test_run_list_accuracy_counts_errored_trials(
    page: Page, base_url: str, seed
):
  """The runs list reports the same 50%, via ``Run.accuracy``."""
  run = _run_with_one_pass_and_one_error(seed)

  page.goto(f"{base_url}/evaluations")
  page.wait_for_load_state("networkidle")

  # Anchor on the row's own "View Report" link, so the assertion is about this
  # run and not whatever else the table holds.
  row = page.locator(f"#{EvaluationIds.RUN_LIST_CONTAINER} tr").filter(
      has=page.locator(f'a[href="/evaluations/runs/{run.id}"]')
  )
  expect(row).to_contain_text("50.0%")
  expect(row).not_to_contain_text("100.0%")


def test_accuracy_ignores_unasserted_trials(page: Page, base_url: str, seed):
  """A trial with nothing asserted is not scored zero, it is not scored.

  This is the boundary the fix must not cross. Both trials below completed and
  neither carries an assertion, so there is no accuracy to report.
  """
  agent = seed.agent()
  suite = seed.suite()
  seed.example(suite, question="How many orders were there?")
  seed.example(suite, question="How many customers were there?")
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  for trial in run.trials:
    seed.finish_trial(trial)

  page.goto(f"{base_url}/evaluations/runs/{run.id}")
  page.wait_for_load_state("networkidle")

  # The card, not the whole stats row. "not 0.0%" held for an empty card, a
  # missing card and any other number, so the only thing it ruled out was the
  # one wrong answer somebody had already thought of. Run.accuracy returns
  # None here and the card renders None as "N/A", so that is the whole answer.
  card = page.locator(f"#{EvaluationIds.RUN_DETAIL_STATS} > div").filter(
      has_text="Avg Accuracy"
  )
  expect(card).to_have_count(1)
  expect(card).to_contain_text("N/A")
  expect(card).not_to_contain_text("%")
