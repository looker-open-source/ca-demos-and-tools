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

"""Journey: compare two runs of the same suite and narrow to the regressions.

The compare page is the one place Prism answers "did this change make the agent
worse?". Two of its controls had never been exercised by anything:

  * the four filter buttons (All / Regressed / Improved / Unchanged). They are
    declared as ``Input``s on ``synchronize_filters`` but only rendered by
    ``update_page_content``, into ``FILTER_BAR``. Until the missing-id sweep
    added placeholders to the layout, none of those ids existed in any page
    layout at import time, so ``suppress_callback_exceptions`` pruned the
    callback outright.
  * the "View Run Page" links under the run selectors, rendered by
    ``populate_run_nav`` into ``BASE_RUN_NAV`` / ``CHALLENGE_RUN_NAV``. Same
    story, and their containers live inside a modal, so nothing loads them
    until it opens.

A pruned callback raises nothing, it just leaves a button that does nothing,
so both are easy to break without noticing.
"""

from __future__ import annotations

import urllib.parse

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import ComparisonIds
import pytest

pytestmark = pytest.mark.e2e

# Two questions, so filtering has something to filter out. The first regresses
# between the runs and the second does not.
_REGRESSED_QUESTION = "How many orders were there?"
_STABLE_QUESTION = "How many customers were there?"


@pytest.fixture(name="compared_runs")
def _compared_runs(seed):
  """Two runs of one suite, differing on exactly one of two questions.

  Both runs share one snapshot. Comparison matches trials by the example's
  logical id, so a single snapshot is enough and keeps the two runs comparable.
  """
  agent = seed.agent()
  suite = seed.suite()
  assertions = [(AssertionType.TEXT_CONTAINS, {"value": "1"})]
  seed.example(suite, question=_REGRESSED_QUESTION, assertions=assertions)
  seed.example(suite, question=_STABLE_QUESTION, assertions=assertions)
  snapshot = seed.snapshot(suite)

  base = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  challenger = seed.run(agent, snapshot, status=RunStatus.COMPLETED)

  for run, regressed_passed in ((base, True), (challenger, False)):
    for trial in run.trials:
      question = trial.example_snapshot.question
      seed.finish_trial(
          trial,
          passed=regressed_passed if question == _REGRESSED_QUESTION else True,
      )

  return suite, base, challenger


def _compare_url(base_url: str, suite, base_run, challenger_run) -> str:
  """The page as it appears once two runs have been chosen."""
  query = urllib.parse.urlencode({
      ComparisonIds.URL_SUITE_ID: suite.id,
      ComparisonIds.URL_BASE_RUN_ID: base_run.id,
      ComparisonIds.URL_CHALLENGER_RUN_ID: challenger_run.id,
  })
  return f"{base_url}/compare?{query}"


def test_the_regressed_filter_narrows_the_trial_list(
    page: Page, base_url: str, compared_runs
):
  """Clicking "Regressed" filters the list and says so in the URL."""
  suite, base_run, challenger_run = compared_runs

  page.goto(_compare_url(base_url, suite, base_run, challenger_run))
  page.wait_for_load_state("networkidle")

  comparison_list = page.locator(f"#{ComparisonIds.COMPARISON_LIST}")
  # Unfiltered, both questions are listed.
  expect(comparison_list).to_contain_text(_REGRESSED_QUESTION, timeout=30_000)
  expect(comparison_list).to_contain_text(_STABLE_QUESTION)

  page.locator(f"#{ComparisonIds.FILTER_REGRESSIONS}").click()

  # The filter lives in the URL, not in a store. synchronize_filters rewrites
  # the search string and update_page_content re-renders off it, so waiting on
  # the URL waits for the first half of that round trip.
  page.wait_for_url(f"**{ComparisonIds.URL_FILTER}=REGRESSION*", timeout=30_000)
  expect(comparison_list).not_to_contain_text(_STABLE_QUESTION, timeout=30_000)
  expect(comparison_list).to_contain_text(_REGRESSED_QUESTION)

  # And back. "All" clears the filter instead of setting another one.
  page.locator(f"#{ComparisonIds.FILTER_ALL}").click()
  expect(comparison_list).to_contain_text(_STABLE_QUESTION, timeout=30_000)
  assert f"{ComparisonIds.URL_FILTER}=" not in page.url


def test_the_select_runs_modal_links_to_both_run_pages(
    page: Page, base_url: str, compared_runs
):
  """Opening the picker offers a way out to each run's own page."""
  suite, base_run, challenger_run = compared_runs

  page.goto(_compare_url(base_url, suite, base_run, challenger_run))
  page.wait_for_load_state("networkidle")
  page.locator(f"#{ComparisonIds.BTN_OPEN_SELECT_RUNS}").click()

  # populate_run_nav fires on the selects' values, which
  # handle_select_runs_modal fills in from the URL as it opens the modal, so the
  # links appear a beat after the modal does.
  base_nav = page.locator(f"#{ComparisonIds.BASE_RUN_NAV}")
  challenger_nav = page.locator(f"#{ComparisonIds.CHALLENGE_RUN_NAV}")
  expect(base_nav.get_by_role("link", name="View Run Page")).to_have_attribute(
      "href", f"/evaluations/runs/{base_run.id}", timeout=30_000
  )
  expect(
      challenger_nav.get_by_role("link", name="View Run Page")
  ).to_have_attribute("href", f"/evaluations/runs/{challenger_run.id}")
