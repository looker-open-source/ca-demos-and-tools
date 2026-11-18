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

"""Journey: server-side pagination and column sorting on /evaluations."""

from __future__ import annotations

import datetime

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.ui.ids import EvaluationIds
import pytest
from tests.e2e.conftest import select_option

pytestmark = pytest.mark.e2e


def _seed_many_runs(db, seed, count: int = 30):
  """Seeds 30 runs across two agents and two suites for paging and sorting."""
  alpha_agent = seed.agent(name="Alpha Agent", agent_resource_id="alpha-e2e")
  zeta_agent = seed.agent(name="Zeta Agent", agent_resource_id="zeta-e2e")

  alpha_suite = seed.suite(name="Alpha Suite")
  zeta_suite = seed.suite(name="Zeta Suite")
  alpha_snap = seed.snapshot(alpha_suite)
  zeta_snap = seed.snapshot(zeta_suite)

  t0 = datetime.datetime(2026, 2, 1, 12, 0, tzinfo=datetime.timezone.utc)
  for i in range(count):
    is_alpha = i % 2 == 0
    run = Run(
        agent_id=alpha_agent.id if is_alpha else zeta_agent.id,
        test_suite_snapshot_id=alpha_snap.id if is_alpha else zeta_snap.id,
        status=RunStatus.COMPLETED,
        created_at=t0 + datetime.timedelta(minutes=i),
        started_at=t0 + datetime.timedelta(minutes=i),
        completed_at=t0 + datetime.timedelta(minutes=i, seconds=10 + i),
    )
    db.add(run)
  db.commit()
  return alpha_agent, zeta_agent


def test_evaluations_pagination_and_sorting_survive_reload_and_back_forward(
    page: Page, base_url: str, db, seed
):
  """Paginating and sorting /evaluations persist across reload and history."""
  alpha_agent, _ = _seed_many_runs(db, seed, count=30)

  page.goto(f"{base_url}/evaluations")
  page.wait_for_load_state("networkidle")

  summary = page.locator(f"#{EvaluationIds.PAGINATION_SUMMARY}")
  indicator = page.locator(f"#{EvaluationIds.PAGINATION_INDICATOR}")
  prev_btn = page.get_by_role("button", name="Previous")
  next_btn = page.get_by_role("button", name="Next")
  rows = page.locator(f"#{EvaluationIds.RUN_LIST_CONTAINER} tbody tr")

  expect(summary).to_have_text("Showing 1–25 of 30 runs", timeout=30_000)
  expect(indicator).to_have_text("Page 1 of 2")
  expect(prev_btn).to_be_disabled()
  expect(next_btn).to_be_enabled()
  expect(rows).to_have_count(25)

  # Next page -> URL updates to ?page=2 and renders remaining 5 rows.
  next_btn.click()
  page.wait_for_url("**page=2**", timeout=30_000)
  expect(summary).to_have_text("Showing 26–30 of 30 runs", timeout=30_000)
  expect(indicator).to_have_text("Page 2 of 2")
  expect(prev_btn).to_be_enabled()
  expect(next_btn).to_be_disabled()
  expect(rows).to_have_count(5)

  # Reload preserves page 2.
  page.reload()
  page.wait_for_load_state("networkidle")
  expect(indicator).to_have_text("Page 2 of 2", timeout=30_000)
  expect(rows).to_have_count(5)

  # Browser Back returns to page 1; Forward returns to page 2.
  page.go_back()
  expect(indicator).to_have_text("Page 1 of 2", timeout=30_000)
  expect(rows).to_have_count(25)

  page.go_forward()
  expect(indicator).to_have_text("Page 2 of 2", timeout=30_000)
  expect(rows).to_have_count(5)

  # Clicking Agent sort resets to page 1 and sorts asc ("Alpha Agent" first).
  page.get_by_role("button", name="Sort by Agent").click()
  page.wait_for_url("**sort=agent**", timeout=30_000)
  assert "dir=asc" in page.url
  assert "page=" not in page.url
  expect(indicator).to_have_text("Page 1 of 2", timeout=30_000)
  expect(rows.first).to_contain_text("Alpha Agent")

  # Clicking Agent sort again flips to desc and survives reload.
  page.get_by_role("button", name="Sort by Agent").click()
  page.wait_for_url("**dir=desc**", timeout=30_000)
  expect(rows.first).to_contain_text("Zeta Agent", timeout=30_000)

  page.reload()
  page.wait_for_load_state("networkidle")
  expect(rows.first).to_contain_text("Zeta Agent", timeout=30_000)
  assert "sort=agent" in page.url and "dir=desc" in page.url

  # Navigate to page 2, then change Agent filter -> resets to page 1.
  next_btn.click()
  page.wait_for_url("**page=2**", timeout=30_000)
  select_option(page, EvaluationIds.FILTER_AGENT, alpha_agent.name)
  page.wait_for_url(f"**agent_id={alpha_agent.id}**", timeout=30_000)
  assert "page=" not in page.url
  expect(summary).to_have_text("Showing 1–15 of 15 runs", timeout=30_000)
  expect(indicator).to_have_text("Page 1 of 1")
  expect(rows).to_have_count(15)


def test_evaluations_page_size_selector_persists_and_resets_page(
    page: Page, base_url: str, db, seed
):
  """Choosing a different page size updates URL, persists on reload, and resets page."""
  _seed_many_runs(db, seed, count=30)

  page.goto(f"{base_url}/evaluations")
  page.wait_for_load_state("networkidle")

  summary = page.locator(f"#{EvaluationIds.PAGINATION_SUMMARY}")
  indicator = page.locator(f"#{EvaluationIds.PAGINATION_INDICATOR}")
  rows = page.locator(f"#{EvaluationIds.RUN_LIST_CONTAINER} tbody tr")
  page_size_input = page.get_by_role("textbox", name="Rows per page")

  expect(indicator).to_have_text("Page 1 of 2", timeout=30_000)
  expect(rows).to_have_count(25)

  # Switch to 10 rows per page -> ?page_size=10, 3 pages, 10 rows.
  page_size_input.click()
  page.get_by_role("option", name="10", exact=True).click()
  page.wait_for_url("**page_size=10**", timeout=30_000)
  expect(summary).to_have_text("Showing 1–10 of 30 runs", timeout=30_000)
  expect(indicator).to_have_text("Page 1 of 3")
  expect(rows).to_have_count(10)

  # Go to page 2 and reload -> keeps page_size=10 and page=2.
  page.get_by_role("button", name="Next").click()
  page.wait_for_url("**page=2**", timeout=30_000)
  expect(summary).to_have_text("Showing 11–20 of 30 runs", timeout=30_000)
  expect(indicator).to_have_text("Page 2 of 3")
  page.reload()
  page.wait_for_load_state("networkidle")
  expect(indicator).to_have_text("Page 2 of 3", timeout=30_000)
  expect(rows).to_have_count(10)

  # Switch back to default 25 -> omits page_size and resets to page 1.
  page.get_by_role("textbox", name="Rows per page").click()
  page.get_by_role("option", name="25", exact=True).click()
  expect(indicator).to_have_text("Page 1 of 2", timeout=30_000)
  expect(rows).to_have_count(25)
  assert "page_size=" not in page.url
  assert "page=" not in page.url


def test_test_suites_coverage_badge_is_right_aligned(
    page: Page, base_url: str, seed
):
  """The coverage badge sits on the right side of its cell under COVERAGE."""
  suite = seed.suite(name="Aligned Coverage Suite")
  seed.example(
      suite,
      question="How many rows?",
      assertions=[(AssertionType.TEXT_CONTAINS, {"value": "10"})],
  )

  page.goto(f"{base_url}/test_suites")
  page.wait_for_load_state("networkidle")

  badge = page.get_by_text("FULL COVERAGE").first
  expect(badge).to_be_visible(timeout=30_000)
  metrics = badge.evaluate("""el => {
    const td = el.closest('td');
    const tdRect = td.getBoundingClientRect();
    const bRect = el.getBoundingClientRect();
    return {
      leftGap: bRect.left - tdRect.left,
      rightGap: tdRect.right - bRect.right,
    };
  }""")
  assert metrics["leftGap"] > metrics["rightGap"], metrics
