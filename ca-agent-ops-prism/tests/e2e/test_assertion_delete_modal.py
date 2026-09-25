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

"""Deleting an assertion hands off between two modals.

The Delete button lives in the Manage Assertion modal's header. Clicking it
runs ``open_delete_modal``, which opens the Confirm Deletion modal and closes
the assertion modal in the same response. Confirming then runs
``confirm_delete_item``, which has to pick the assertion branch over the test
case branch from which of two index stores is set, and persist by syncing the
whole suite. Creating an assertion is covered by ``test_suite_authoring``.
Deleting one was not covered anywhere.

I wrote this expecting it to pin ``MODAL_DELETE``'s ``zIndex=10000`` in
``pages/test_suite_questions.py``, on the theory that the closing modal's
overlay would swallow the confirm click. It does not: removing the zIndex
leaves this green, because Playwright retries the click until the overlay
finishes its exit transition and a real person gets the same retry by
clicking again. So the stacking is not what is tested here. The handoff is.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.server.models.assertion import Assertion
from prism.ui.ids import TestSuiteIds
import pytest
import sqlalchemy

pytestmark = pytest.mark.e2e


def test_deleting_an_assertion_from_its_editor_removes_it(
    page: Page, base_url: str, seed, db
):
  """Read back from the database, because the page drops the card either way."""
  suite = seed.suite()
  seed.example(
      suite,
      question="How many orders were there last week?",
      assertions=[(AssertionType.TEXT_CONTAINS, {"value": "128"})],
  )

  page.goto(f"{base_url}/test_suites/edit/{suite.id}")
  page.wait_for_load_state("networkidle")

  # The edit control is a pattern-matching id, so its DOM id is a JSON blob.
  # Matching on the substring beats escaping the braces and quotes.
  page.locator(f"[id*='{TestSuiteIds.ASSERT_EDIT_BTN}']").first.click()

  # By role, not by id: dmc.Modal puts the id on a zero-box root wrapper that
  # is never "visible" even with the dialog open.
  assertion_modal = page.get_by_role("dialog", name="Manage Assertion")
  confirm_modal = page.get_by_role("dialog", name="Confirm Deletion")
  expect(assertion_modal).to_be_visible()

  page.locator(f"#{TestSuiteIds.ASSERT_MODAL_DELETE_BTN}").click()
  expect(confirm_modal).to_be_visible(timeout=30_000)
  expect(confirm_modal).to_contain_text("delete this assertion")
  expect(assertion_modal).to_be_hidden(timeout=30_000)

  page.locator(f"#{TestSuiteIds.MODAL_CONFIRM_REMOVE_BTN}").click()
  expect(confirm_modal).to_be_hidden(timeout=30_000)

  db.expire_all()
  assert not db.execute(sqlalchemy.select(Assertion)).scalars().all(), (
      "The dialog closed but the assertion is still in the database, so the"
      " confirm click did not reach the delete."
  )
