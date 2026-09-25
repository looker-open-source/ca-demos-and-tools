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

"""Regression: the global error toast reaches the screen.

``handle_errors`` reports a failed callback through ``dash.set_props``, not
through a declared output. Dash puts that in a ``sideUpdate`` block, and
dash-renderer has to apply it to a component the firing callback never named.
Nothing below the browser can see whether that happens. ``tests/ui`` reads the
``sideUpdate`` out of the response body, which is true of a renderer that drops
it on the floor.

If it were dropped, every callback failure in the app would go silent at once,
and the page would look like the click did nothing. That is the state this
existed to fix, so it is worth one spec.

The failure is provoked, not simulated: the suite is deleted between loading
the page and saving, which is what a second tab does. ``sync_suite`` raises
``TestSuite with id N not found``, and the callback behind Save declares no
notification output, so the toast can only arrive through ``set_props``.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.server.models.example import Example

# Aliased, because pytest tries to collect any imported name starting "Test".
from prism.server.models.suite import TestSuite as SuiteModel
from prism.ui.ids import TestSuiteIds
import pytest
import sqlalchemy

pytestmark = [pytest.mark.e2e, pytest.mark.allow_errors]

# dmc renders notifications into a portal outside the page tree, so find them
# by class. Same locator as test_regression_archive_toast, for the same reason.
_TOAST = ".mantine-Notification-root"


def test_a_failed_callback_shows_a_toast_on_screen(
    page: Page, base_url: str, seed, db
):
  """Saving into a suite that is gone has to say so, not look like a no-op."""
  suite = seed.suite()
  seed.example(suite, question="How many orders were there last week?")

  page.goto(f"{base_url}/test_suites/edit/{suite.id}")
  page.wait_for_load_state("networkidle")

  question = page.locator(f"#{TestSuiteIds.TC_INPUT_TEST_CASE}")
  expect(question).to_be_visible()
  question.fill("How many orders were there this week?")

  # Child first. The Example backref carries no delete cascade, so deleting
  # the suite through the ORM nulls examples.test_suite_id and trips the
  # not-null constraint instead. Committed, because the server reads on its
  # own connection.
  db.execute(
      sqlalchemy.delete(Example).where(Example.test_suite_id == suite.id)
  )
  db.execute(sqlalchemy.delete(SuiteModel).where(SuiteModel.id == suite.id))
  db.commit()

  page.locator(f"#{TestSuiteIds.TC_SAVE_BTN}").click()

  toast = page.locator(_TOAST).first
  expect(toast).to_be_visible(timeout=30_000)
  expect(toast).to_contain_text("Something went wrong")
  # The reference is what ties the toast to the traceback in the server log.
  expect(toast).to_contain_text("ref ")
