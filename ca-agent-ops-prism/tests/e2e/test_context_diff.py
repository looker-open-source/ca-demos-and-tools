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

"""Journey: find out whether the agent has changed since a run was taken.

A run stores the agent's context as it was when the run started. Weeks later,
"is this run still comparable to today's agent?" is answered by "Compare to
Live Context", which re-fetches the published context and diffs it, and by
"Download diff", which hands you the unified diff as a file.

The download button existed in ``render_diff_modal`` and its callback in
``evaluation_callbacks``, but no test had ever pressed it, and until the
missing-id sweep the modal's own callbacks were pruned outright. This spec
covers both halves: the live re-fetch (served from a cassette) and the file the
button produces.
"""

from __future__ import annotations

import pathlib

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import EvaluationIds
import pytest

pytestmark = pytest.mark.e2e


def _diff_modal(page: Page):
  """The dialog, identified by the one button only it contains.

  Neither of the obvious handles works. The Dash id is on a zero-box wrapper
  that is never "visible", and dmc portals the dialog out of it instead of
  nesting it, so scoping by id finds nothing. The dialog's accessible name is
  its whole title subtree (title text, change badge, download button), which
  two callbacks rewrite as the live fetch progresses, so matching by name means
  matching a moving target.

  The download button is unique to this modal and its label never changes.
  """
  return page.get_by_role("dialog").filter(
      has=page.locator(f"#{EvaluationIds.BTN_DOWNLOAD_DIFF}")
  )


_SNAPSHOT_CONTEXT = {"system_instruction": "Answer questions about orders."}
# One line changed against the snapshot. Enough for a diff with a body, small
# enough that the assertions below can name the exact text.
_LIVE_CONTEXT = {
    "system_instruction": "Answer questions about orders. Prefer whole weeks."
}


@pytest.fixture(name="run_with_drifted_context")
def _run_with_drifted_context(seed, cassettes):
  """A finished run whose agent's published context has since changed."""
  agent = seed.agent()
  cassettes.agent_context(agent, _LIVE_CONTEXT)
  suite = seed.suite()
  seed.example(suite)
  snapshot = seed.snapshot(suite)
  run = seed.run(
      agent,
      snapshot,
      status=RunStatus.COMPLETED,
      agent_context_snapshot=_SNAPSHOT_CONTEXT,
  )
  seed.finish_trial(run.trials[0])
  return run


def test_the_modal_diffs_the_snapshot_against_the_live_context(
    page: Page, base_url: str, run_with_drifted_context
):
  """Opening the modal fetches the live context and reports the drift."""
  run = run_with_drifted_context

  page.goto(f"{base_url}/evaluations/runs/{run.id}")
  page.wait_for_load_state("networkidle")
  page.locator(f"#{EvaluationIds.RUN_CONTEXT_DIFF_BTN}").click()

  modal = _diff_modal(page)
  expect(modal).to_be_visible()
  # The badge comes from the second callback in the chain, the one that runs
  # after the live fetch returns, so waiting on it waits for the fetch.
  expect(modal).to_contain_text("Changes detected", timeout=60_000)
  expect(modal).to_contain_text("Prefer whole weeks")


def test_download_diff_produces_the_unified_diff(
    page: Page, base_url: str, run_with_drifted_context
):
  """The button hands back a file naming the run and containing the diff."""
  run = run_with_drifted_context

  page.goto(f"{base_url}/evaluations/runs/{run.id}")
  page.wait_for_load_state("networkidle")
  page.locator(f"#{EvaluationIds.RUN_CONTEXT_DIFF_BTN}").click()

  modal = _diff_modal(page)
  # download_diff_context reads the live context out of the store and returns
  # no_update if it is not there yet, so the click has to wait for the fetch.
  expect(modal).to_contain_text("Changes detected", timeout=60_000)

  with page.expect_download() as download_info:
    page.locator(f"#{EvaluationIds.BTN_DOWNLOAD_DIFF}").click()
  download = download_info.value

  assert download.suggested_filename == f"context_diff_run_{run.id}.txt"
  diff = pathlib.Path(download.path()).read_text(encoding="utf-8")
  assert (
      "Prefer whole weeks" in diff
  ), f"Not a diff of the live context:\n{diff}"
  # difflib's hunk marker. Without it this is a file, not a diff.
  assert "@@" in diff, f"No hunk header in the downloaded diff:\n{diff}"
