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

"""Regression: restoring a suite left the page still offering Restore.

The suite view renders both buttons and hides one, picking which from
``suite.is_archived`` at render time. Nothing on the page reacts to the row
changing, so the swap depends entirely on the page being rendered again.

``toggle_suite_archive`` gets that re-render by writing the current pathname
to ``dcc.Location(id="redirect-handler", refresh=True)``. Writing a location's
href the value it already holds is the part worth testing: the archive
direction is reached from wherever the user was, but by the restore click
``redirect-handler.href`` already equals the pathname being written, and a
renderer that treats that as a no-op leaves the user on a page still saying
Restore for a suite that is no longer archived.

The dispatch tier cannot see it. The response body is byte-identical whether
or not the renderer navigates. The agent equivalent does not transfer either:
``toggle_agent_archive`` re-renders by writing a timestamp store, not a
location.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page

# Aliased because pytest tries to collect any module-level name starting with
# Test and warns when it cannot.
from prism.server.models.suite import TestSuite as SuiteRow
from prism.ui.ids import TestSuiteIds
import pytest

pytestmark = pytest.mark.e2e


def test_archive_then_restore_swaps_the_button_both_ways(
    page: Page, base_url: str, seed, db
):
  """Both directions, because only the second one writes the href twice."""
  suite = seed.suite()

  page.goto(f"{base_url}/test_suites/view/{suite.id}")
  page.wait_for_load_state("networkidle")

  archive = page.locator(f"#{TestSuiteIds.BTN_ARCHIVE}")
  restore = page.locator(f"#{TestSuiteIds.BTN_RESTORE}")
  expect(archive).to_be_visible()
  expect(restore).to_be_hidden()

  archive.click()
  expect(restore).to_be_visible(timeout=30_000)
  expect(archive).to_be_hidden()

  db.expire_all()
  assert db.get(SuiteRow, suite.id).is_archived

  restore.click()
  expect(archive).to_be_visible(timeout=30_000)
  expect(restore).to_be_hidden()

  # Checked as well as the button, so a page that swaps back without the write
  # landing cannot pass.
  db.expire_all()
  assert not db.get(SuiteRow, suite.id).is_archived, (
      "The page offers Archive again but the suite is still archived, so the"
      " next click archives something already archived."
  )
