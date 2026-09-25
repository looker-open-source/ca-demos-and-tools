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

"""Regression: text-contains matched progress chatter as if it were the answer.

``check_text_contains`` joined every ``TextMessage`` in the trace except those
typed THOUGHT, and asserted against that. But the agent also streams PROGRESS
messages while it works ("Scanning the orders table." and the like). Those
aren't part of the answer; the UI renders only the FINAL_RESPONSE. So an
assertion could pass on text the displayed response never contained.

The trace replayed here carries both kinds. One assertion looks for text that
appears only in the progress stream and must fail. The other looks for text in
the final response and must pass. Both are needed, or an over-broad fix that
stopped matching anything at all would still pass.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.server.models.assertion import AssertionResult
from prism.server.models.run import Trial
from prism.ui.ids import EvaluationIds
import pytest
import sqlalchemy
from tests.e2e import traces
from tests.e2e.conftest import select_option

pytestmark = pytest.mark.e2e

_RUN_TIMEOUT_MS = 120_000

# Appears in the PROGRESS message and nowhere in the final response.
_PROGRESS_ONLY = "Scanning the orders"
# Appears in the final response.
_IN_ANSWER = "128"


def test_progress_text_does_not_satisfy_text_contains(
    page: Page, base_url: str, seed, db, cassettes
):
  """Only the final response counts towards a text-contains assertion."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite,
      question=traces.QUESTION,
      assertions=[
          (AssertionType.TEXT_CONTAINS, {"value": _PROGRESS_ONLY}),
          (AssertionType.TEXT_CONTAINS, {"value": _IN_ANSWER}),
      ],
  )
  cassettes.agent_context(agent)
  cassettes.datasource_kind(agent)
  cassettes.ask_question(agent, traces.QUESTION)

  page.goto(f"{base_url}/test_suites/view/{suite.id}")
  page.wait_for_load_state("networkidle")
  page.locator(f"#{EvaluationIds.BTN_OPEN_RUN_MODAL}").click()
  select_option(page, EvaluationIds.AGENT_SELECT, agent.name)
  page.locator(f"#{EvaluationIds.BTN_START_RUN}").click()

  page.wait_for_url("**/evaluations/runs/*", timeout=30_000)
  expect(page.locator(f"#{EvaluationIds.RUN_STATUS_BADGE}")).to_contain_text(
      "COMPLETED", timeout=_RUN_TIMEOUT_MS, ignore_case=True
  )

  # One of two equally weighted assertions passed.
  expect(page.locator(f"#{EvaluationIds.RUN_DETAIL_STATS}")).to_contain_text(
      "50.0%"
  )

  db.expire_all()
  results = (
      db.execute(sqlalchemy.select(AssertionResult).join(Trial)).scalars().all()
  )
  by_value = {
      result.assertion_snapshot.params["value"]: result for result in results
  }
  assert set(by_value) == {_PROGRESS_ONLY, _IN_ANSWER}

  assert not by_value[_PROGRESS_ONLY].passed, (
      f"An assertion for {_PROGRESS_ONLY!r} passed. That text is only in the "
      "agent's progress stream; the response the user is shown does not "
      "contain it, so the tick contradicts what is on screen."
  )
  assert by_value[_IN_ANSWER].passed, (
      f"An assertion for {_IN_ANSWER!r} failed, but the final response says "
      f"{traces.ANSWER!r}. Excluding PROGRESS must not exclude the answer."
  )
