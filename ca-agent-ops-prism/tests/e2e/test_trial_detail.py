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

"""Journey: read the result of a single trial.

The trial detail and agent trace pages are where someone goes to find out why
an assertion failed, so they matter most when something is wrong, and nothing
covered them. Both are path-template routes, so ``test_navigation`` skips them.

The trial here is seeded, not executed. ``test_run_execution`` owns the real
path. This spec is about what the pages render, and spawning a subprocess to
find that out would only be slower and flakier.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import EvaluationIds
import pytest
from tests.e2e import traces

pytestmark = pytest.mark.e2e


def _completed_trial(
    seed,
    passed: bool = True,
    trace: list[dict[str, object]] | None = None,
):
  """A finished trial with one assertion, passing or failing per ``passed``."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite,
      question=traces.QUESTION,
      assertions=[(AssertionType.TEXT_CONTAINS, {"value": "128"})],
  )
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  trial = run.trials[0]
  seed.finish_trial(trial, trace=trace, passed=passed)
  return trial


def test_trial_detail_renders_the_result(page: Page, base_url: str, seed):
  """The page shows the question, the answer and the assertion outcome."""
  trial = _completed_trial(seed)

  page.goto(f"{base_url}/evaluations/trials/{trial.id}")
  page.wait_for_load_state("networkidle")

  container = page.locator(f"#{EvaluationIds.TRIAL_DETAIL_CONTAINER}")
  # The layout's placeholder is a loader, so real content means the callback ran
  # instead of the page hanging on a spinner.
  expect(container).to_contain_text(traces.QUESTION)
  expect(container).to_contain_text(traces.ANSWER)
  # The assertions table renders the type as a label, not as the
  # ``text-contains`` enum value.
  expect(container).to_contain_text("Text Contains")
  expect(container).to_contain_text("PASS")


def test_trial_detail_shows_a_failed_assertion(page: Page, base_url: str, seed):
  """A failing assertion is legible as a failure, not just absent."""
  trial = _completed_trial(seed, passed=False)

  page.goto(f"{base_url}/evaluations/trials/{trial.id}")
  page.wait_for_load_state("networkidle")

  container = page.locator(f"#{EvaluationIds.TRIAL_DETAIL_CONTAINER}")
  expect(container).to_contain_text("Text Contains")
  # The outcome and the reason for it. Both, since a bare FAIL is not much use.
  expect(container).to_contain_text("FAIL")
  expect(container).to_contain_text("Seeded by the E2E suite.")


def test_agent_trace_renders_the_replayed_trace(
    page: Page, base_url: str, seed
):
  """The trace page renders the SQL and the answer from trace_results."""
  trial = _completed_trial(seed)

  page.goto(f"{base_url}/evaluations/trials/{trial.id}/trace")
  page.wait_for_load_state("networkidle")

  container = page.locator(f"#{EvaluationIds.AGENT_TRACE_CONTAINER}")
  expect(container).to_contain_text("COUNT(*)")
  expect(container).to_contain_text(traces.ANSWER)


def test_trial_detail_shows_an_errored_assertion(
    page: Page, base_url: str, seed
):
  """An un-evaluated assertion renders an ERROR badge and diagnostic reason."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite,
      question=traces.QUESTION,
      assertions=[(AssertionType.AI_JUDGE, {"value": "Is the tone helpful?"})],
  )
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  trial = run.trials[0]
  seed.finish_trial(
      trial,
      passed=False,
      assertion_error_message=(
          "AI Judge requires PRISM_GENAI_CLIENT_PROJECT to evaluate criteria."
      ),
  )

  page.goto(f"{base_url}/evaluations/trials/{trial.id}")
  page.wait_for_load_state("networkidle")

  container = page.locator(f"#{EvaluationIds.TRIAL_DETAIL_CONTAINER}")
  expect(container).to_contain_text("AI Judge")
  expect(container).to_contain_text("ERROR")
  expect(container).to_contain_text("PRISM_GENAI_CLIENT_PROJECT")


def test_agent_trace_renders_matched_verified_query(
    page: Page, base_url: str, seed
):
  """The trace page renders matched Verified Query SQL and parameters."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite,
      question=traces.QUESTION,
      assertions=[(AssertionType.QUERY_CONTAINS, {"value": "verified_orders"})],
  )
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  trial = run.trials[0]
  verified_trace = [
      {
          "system_message": {
              "data": {
                  "matched_query": {
                      "example_query": {
                          "sql_query": "SELECT COUNT(*) FROM verified_orders"
                      },
                      "query_parameter_values": [
                          {"name": "status", "value": "SHIPPED"}
                      ],
                  }
              }
          }
      },
      {
          "system_message": {
              "text": {"text_type": "RESPONSE", "parts": [traces.ANSWER]}
          }
      },
  ]
  for message, timestamp in zip(
      verified_trace, traces._timestamps(len(verified_trace))  # pylint: disable=protected-access
  ):
    message["timestamp"] = timestamp
  seed.finish_trial(trial, trace=verified_trace, passed=True)

  page.goto(f"{base_url}/evaluations/trials/{trial.id}/trace")
  page.wait_for_load_state("networkidle")

  container = page.locator(f"#{EvaluationIds.AGENT_TRACE_CONTAINER}")
  expect(container).to_contain_text("Matched Verified Query")
  expect(container).to_contain_text("SELECT COUNT(*) FROM verified_orders")


def test_curating_suggestions_keeps_accordion_expanded(
    page: Page, base_url: str, seed
):
  """Accepting or rejecting a suggestion leaves the accordion open."""
  trial = _completed_trial(seed)
  seed.suggest_assertion(trial, params={"value": "keep-open-first"})
  seed.suggest_assertion(trial, params={"value": "keep-open-second"})

  page.goto(f"{base_url}/evaluations/trials/{trial.id}")
  page.wait_for_load_state("networkidle")

  accordion = page.locator(f"#{EvaluationIds.TRIAL_SUG_ACCORDION}")
  control = accordion.get_by_role("button", name="Suggested Assertions")
  control.click()

  content = page.locator(f"#{EvaluationIds.TRIAL_SUGGESTIONS_CONTENT}")
  expect(content.get_by_text("keep-open-first")).to_be_visible()
  expect(content.get_by_text("keep-open-second")).to_be_visible()

  content.get_by_role("button", name="Accept").first.click()
  expect(content.get_by_text("keep-open-first")).to_be_hidden(timeout=15_000)
  expect(content.get_by_text("keep-open-second")).to_be_visible()
  expect(control).to_have_attribute("aria-expanded", "true")

  content.get_by_role("button", name="Reject").first.click()
  expect(content.get_by_text("No suggested assertions.")).to_be_visible(
      timeout=15_000
  )
  expect(
      content.get_by_role("button", name="Suggest Assertions")
  ).to_be_visible()
  expect(control).to_have_attribute("aria-expanded", "true")


def test_generating_suggestions_keeps_accordion_expanded(
    page: Page, base_url: str, seed
):
  """Generating suggestions leaves the accordion open until cards arrive."""
  # Empty trace keeps the background generator from calling GenAI or racing
  # with the seeded suggestion row below.
  trial = _completed_trial(seed, trace=[])

  page.goto(f"{base_url}/evaluations/trials/{trial.id}")
  page.wait_for_load_state("networkidle")

  accordion = page.locator(f"#{EvaluationIds.TRIAL_SUG_ACCORDION}")
  control = accordion.get_by_role("button", name="Suggested Assertions")
  control.click()

  content = page.locator(f"#{EvaluationIds.TRIAL_SUGGESTIONS_CONTENT}")
  generate_btn = content.get_by_role("button", name="Suggest Assertions")
  expect(generate_btn).to_be_visible()

  generate_btn.click()
  # Skeletons replace the empty state inside the open panel while polling runs.
  expect(generate_btn).to_be_hidden(timeout=15_000)
  expect(content.locator(".mantine-Skeleton-root").first).to_be_visible(
      timeout=15_000
  )
  expect(control).to_have_attribute("aria-expanded", "true")

  # Simulate the background generator finishing so the 3s poll picks it up.
  seed.suggest_assertion(trial, params={"value": "polled-suggestion"})
  expect(content.get_by_text("polled-suggestion")).to_be_visible(timeout=15_000)
  expect(control).to_have_attribute("aria-expanded", "true")
