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

"""Journey: build a test suite by hand.

Everything a suite is made of (the suite, a question, an assertion on that
question) created through the pages a person uses, then read back out of the
database. No agent is involved, so no cassettes. This journey never leaves the
app.

Counterpart to ``test_run_execution``, which starts from a seeded suite.
Between them, the authoring path and the execution path are each covered by at
least one spec.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.server.models.assertion import Assertion
from prism.server.models.example import Example

# Aliased, because pytest tries to collect any imported name starting "Test".
from prism.server.models.suite import TestSuite as SuiteModel
from prism.ui.ids import TestSuiteIds
import pytest
import sqlalchemy
from tests.e2e.conftest import select_option

pytestmark = pytest.mark.e2e

_SUITE_NAME = "Order volume checks"
_SUITE_DESCRIPTION = "Questions about how many orders there were."
_QUESTION = "How many orders were there last week?"
_ASSERT_VALUE = "128"


def test_create_a_suite_with_a_question_and_an_assertion(
    page: Page, base_url: str, db
):
  """A suite authored through the UI is persisted with its assertion."""
  page.goto(f"{base_url}/test_suites/new")
  page.wait_for_load_state("networkidle")

  page.locator(f"#{TestSuiteIds.NAME}").fill(_SUITE_NAME)
  page.locator(f"#{TestSuiteIds.DESC}").fill(_SUITE_DESCRIPTION)
  page.locator(f"#{TestSuiteIds.SAVE_NEW_BTN}").click()

  # Saving redirects to the new suite, which is how its id becomes known.
  page.wait_for_url("**/test_suites/view/*", timeout=30_000)
  suite = db.execute(sqlalchemy.select(SuiteModel)).scalars().one()
  assert suite.name == _SUITE_NAME
  assert suite.description == _SUITE_DESCRIPTION
  page.wait_for_load_state("networkidle")

  page.goto(f"{base_url}/test_suites/edit/{suite.id}")
  page.wait_for_load_state("networkidle")

  # Adding a question writes a placeholder row immediately and selects it. Only
  # Save persists the text.
  page.locator(f"#{TestSuiteIds.TC_PLAYGROUND_ADD_BTN}").click()
  question = page.locator(f"#{TestSuiteIds.TC_INPUT_TEST_CASE}")
  expect(question).to_be_visible()
  question.fill(_QUESTION)
  page.locator(f"#{TestSuiteIds.TC_SAVE_BTN}").click()

  # The add-assertion tile is a div with n_clicks, not a button.
  page.locator(f"#{TestSuiteIds.ASSERT_MODAL_OPEN_BTN}").click()
  # By role, not by id, because dmc.Modal puts the id on a zero-box root wrapper
  # and #assert-modal is never "visible" even with the dialog open.
  modal = page.get_by_role("dialog", name="Manage Assertion")
  expect(modal).to_be_visible()

  select_option(page, TestSuiteIds.TC_ASSERT_TYPE, "Text Contains")
  # Which input is shown depends on the type. Structured assertions get a YAML
  # editor instead of this one.
  value = page.locator(f"#{TestSuiteIds.TC_ASSERT_VALUE}")
  expect(value).to_be_visible()
  value.fill(_ASSERT_VALUE)
  page.locator(f"#{TestSuiteIds.ASSERT_MODAL_CONFIRM_BTN}").click()
  # The modal closes only once the assertion validates and saves.
  expect(modal).to_be_hidden(timeout=30_000)

  db.expire_all()
  example = db.execute(sqlalchemy.select(Example)).scalars().one()
  assert example.test_suite_id == suite.id
  assert example.question == _QUESTION, (
      "The question was not persisted, so the suite holds the placeholder "
      "text the Add button wrote rather than what was typed."
  )

  assertion = db.execute(sqlalchemy.select(Assertion)).scalars().one()
  assert assertion.example_id == example.id
  assert assertion.type == AssertionType.TEXT_CONTAINS
  assert assertion.params.get("value") == _ASSERT_VALUE

  # And it reads back on the page a run is started from. Scoped to the card
  # list and asserted visible: against the body this passed on the question
  # sitting in a closed modal, in a dcc.Store, or in any other node the page
  # keeps around but never shows.
  page.goto(f"{base_url}/test_suites/view/{suite.id}")
  page.wait_for_load_state("networkidle")
  card_list = page.locator(f"#{TestSuiteIds.TEST_CASE_LIST}")
  expect(card_list.get_by_text(_QUESTION, exact=True)).to_be_visible()
