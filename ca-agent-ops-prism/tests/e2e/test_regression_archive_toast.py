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

"""Regression: archive confirmations and, worse, archive failures were silent.

``dmc.NotificationContainer``'s ``sendNotifications`` property takes a list of
action dicts. ``toggle_run_archive`` and ``toggle_agent_archive`` each returned
a bare dict. That isn't an error, the component just renders nothing, so the
success path only felt unresponsive.

The failure path is the real cost. Both callbacks catch their exception and
report it through the same channel, so an archive that failed looked like one
that worked: nothing happened on screen either way.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.execution import RunStatus
from prism.ui.ids import EvaluationIds
from prism.ui.pages.agent_ids import AgentIds
import pytest

pytestmark = pytest.mark.e2e

# dmc renders notifications into a portal outside the page tree, so find them
# by class, not by container id. Not by ``role=alert`` either: dmc.Alert carries
# that role too, and the run detail page renders one ("No assertion data
# available for this run") that would satisfy a role-based locator with no
# notification sent at all.
_TOAST = ".mantine-Notification-root"


def test_archiving_a_run_shows_a_toast(page: Page, base_url: str, seed):
  """Archiving a run says so."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(suite)
  snapshot = seed.snapshot(suite)
  run = seed.run(agent, snapshot, status=RunStatus.COMPLETED)
  for trial in run.trials:
    seed.finish_trial(trial)

  page.goto(f"{base_url}/evaluations/runs/{run.id}")
  page.wait_for_load_state("networkidle")

  archive = page.locator(f"#{EvaluationIds.BTN_ARCHIVE}")
  expect(archive).to_be_visible()
  archive.click()

  expect(page.locator(_TOAST).first).to_contain_text("archived")


def test_archiving_an_agent_shows_a_toast(
    page: Page, base_url: str, seed, cassettes
):
  """Archiving an agent says so."""
  agent = seed.agent()
  cassettes.get_agent(agent)

  page.goto(f"{base_url}/agents/view/{agent.id}")
  page.wait_for_load_state("networkidle")

  archive = page.locator(f"#{AgentIds.Detail.BTN_ARCHIVE}")
  expect(archive).to_be_visible()
  archive.click()

  expect(page.locator(_TOAST).first).to_contain_text("archived")
