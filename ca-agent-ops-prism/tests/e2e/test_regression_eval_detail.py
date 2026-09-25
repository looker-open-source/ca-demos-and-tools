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

"""Regression: the run detail page loaded but rendered nothing.

``evaluation_detail.layout`` declared ``run_id: str = None``. Dash calls a
path-template layout with no argument when it first registers the page, and
``run_id`` is interpolated into the pattern-matching id of the "Compare to"
button. So the default reached dict id construction as None and Dash raised
``TypeError: dict id values must be strings, numbers or bools, found None``.

``test_navigation`` can't catch this, because it skips routes with a path
template. The page 500s for every run in the product.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import EvaluationIds
import pytest

pytestmark = pytest.mark.e2e


def test_run_detail_page_renders(page: Page, base_url: str, seed):
  """A run detail URL renders its stats and trials, not a stack trace."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite,
      assertions=[(AssertionType.TEXT_CONTAINS, {"value": "128"})],
  )
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  for trial in run.trials:
    seed.finish_trial(trial)

  page.goto(f"{base_url}/evaluations/runs/{run.id}")
  page.wait_for_load_state("networkidle")

  # The stats grid starts as three skeletons. Real content means the callback
  # ran instead of the page dying on load.
  stats = page.locator(f"#{EvaluationIds.RUN_DETAIL_STATS}")
  expect(stats).to_contain_text("Avg Accuracy")
  expect(stats).to_contain_text(agent.name)

  expect(
      page.locator(f"#{EvaluationIds.RUN_TRIALS_CONTAINER}")
  ).to_contain_text("Trials")
  expect(page.locator(f"#{EvaluationIds.RUN_STATUS_BADGE}")).to_contain_text(
      "COMPLETED", ignore_case=True
  )
