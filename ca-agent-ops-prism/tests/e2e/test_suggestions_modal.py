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

"""Journey: reuse an assertion that a past run suggested.

The suite editor offers "Suggestions from recent runs", which lists the
assertions the suggestion service proposed on earlier trials of the same
question and lets you adopt them. Nothing covered it, and it did not work:

  * its trigger button was missing from the layout entirely, so
    ``suppress_callback_exceptions`` pruned both of its callbacks and the
    feature did not exist;
  * once the button was added, ``show_history_suggestions`` skipped every
    suggestion, because ``Trial.suggested_asserts`` holds ``Assertion``
    models and the loop tested ``isinstance(s, dict)``;
  * and "Add Selected" was hardcoded ``disabled=True`` with nothing to
    re-enable it, so even a populated modal could not be acted on.

This spec walks the whole feature, so it covers all three.

The empty case was wrong in a fourth way. ``show_history_suggestions`` writes
one of four messages saying why it found nothing, and the div it writes them to
was rendered once, outside the modal, under ``display: none``. Whichever one it
wrote, the modal said "No suggestions available."
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.assertion import Assertion
from prism.ui.ids import TestSuiteIds
import pytest
import sqlalchemy
from tests.e2e import traces

pytestmark = pytest.mark.e2e

_SUGGESTED_VALUE = "128"
# render_suggestion_list titlecases the type and appends the value.
_SUGGESTION_LABEL = f"Text Contains: {_SUGGESTED_VALUE}"
_MODAL_TITLE = "Suggestions from Recent Runs"


@pytest.fixture(name="suite_with_history")
def _suite_with_history(seed):
  """A one-question suite whose earlier trial left a suggestion behind."""
  agent = seed.agent()
  suite = seed.suite()
  example = seed.example(suite, question=traces.QUESTION)
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  trial = seed.finish_trial(run.trials[0])
  seed.suggest_assertion(
      trial,
      assertion_type=AssertionType.TEXT_CONTAINS,
      params={"value": _SUGGESTED_VALUE},
  )
  return suite, example


def test_the_modal_lists_a_suggestion_from_a_past_run(
    page: Page, base_url: str, suite_with_history
):
  """Opening the modal shows the suggestion rather than an empty state."""
  suite, _ = suite_with_history

  page.goto(f"{base_url}/test_suites/edit/{suite.id}")
  page.wait_for_load_state("networkidle")

  # The suite's only question is selected on load, which is what gives
  # show_history_suggestions an example id to look history up by.
  page.locator(f"#{TestSuiteIds.TC_HISTORY_SUGGESTIONS_BTN}").click()

  # By role, because dmc.Modal puts the Dash id on a zero-box wrapper and
  # #suggestion-modal is never "visible" even with the dialog open.
  modal = page.get_by_role("dialog", name=_MODAL_TITLE)
  expect(modal).to_be_visible()
  expect(modal).to_contain_text(_SUGGESTION_LABEL, timeout=30_000)
  # The two ways this used to fail, named so a regression says which one.
  expect(modal).not_to_contain_text("No valid suggestions found")
  expect(modal).not_to_contain_text("No historical suggestions found")


def test_the_modal_says_why_it_is_empty(page: Page, base_url: str, seed):
  """A question with no run history gets told that, not the generic line."""
  suite = seed.suite()
  seed.example(suite, question=traces.QUESTION)

  page.goto(f"{base_url}/test_suites/edit/{suite.id}")
  page.wait_for_load_state("networkidle")
  page.locator(f"#{TestSuiteIds.TC_HISTORY_SUGGESTIONS_BTN}").click()

  modal = page.get_by_role("dialog", name=_MODAL_TITLE)
  # Visible, not merely present. The div these messages land in was rendered
  # under display:none, and to_contain_text reads textContent, to which a
  # hidden element still contributes. That assertion passes against the bug.
  expect(
      modal.get_by_text("No historical suggestions found for this test case.")
  ).to_be_visible(timeout=30_000)
  # The reason has to be the only thing in there. Both messages at once reads
  # as two separate problems.
  expect(modal).not_to_contain_text("No suggestions available")


def test_adopting_a_suggestion_persists_it_as_an_assertion(
    page: Page, base_url: str, db, suite_with_history
):
  """Checking a suggestion and adding it writes a real assertion row."""
  suite, example = suite_with_history
  assert not db.execute(sqlalchemy.select(Assertion)).scalars().all(), (
      "The question starts with no assertions; the one this test looks for "
      "at the end has to be the adopted suggestion."
  )

  page.goto(f"{base_url}/test_suites/edit/{suite.id}")
  page.wait_for_load_state("networkidle")
  page.locator(f"#{TestSuiteIds.TC_HISTORY_SUGGESTIONS_BTN}").click()

  modal = page.get_by_role("dialog", name=_MODAL_TITLE)
  expect(modal).to_contain_text(_SUGGESTION_LABEL, timeout=30_000)

  modal.get_by_role("checkbox").first.check()
  add = modal.get_by_role("button", name="Add Selected")
  # It shipped disabled with nothing to re-enable it, which made the rest of
  # the feature moot.
  expect(add).to_be_enabled()
  add.click()

  # confirm_suggestions closes the modal only after sync_suite returns.
  expect(modal).to_be_hidden(timeout=30_000)

  db.expire_all()
  assertion = db.execute(sqlalchemy.select(Assertion)).scalars().one()
  assert assertion.example_id == example.id
  assert assertion.type == AssertionType.TEXT_CONTAINS
  assert assertion.params.get("value") == _SUGGESTED_VALUE
