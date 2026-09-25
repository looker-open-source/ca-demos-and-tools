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

"""Journey: discover the agents already on GCP and start monitoring one.

Every Monitor button on the discovery table shares one pattern-matching id, so
one clientside callback owns the ``loading`` flag for all of them. It gets the
whole list of click counts and has to return a list the same length, with True
in one slot. Returning True everywhere, or a list of the wrong length, are both
easy mistakes and neither raises: Dash just sets what it is given, and the page
shows every row spinning while one of them is being onboarded.

Nothing below the browser can see that. The callback is inline JS, and a
clientside callback is absent from the callback map, so the contract and
dispatch tiers do not know it exists.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.server.models.agent import Agent
from prism.ui.pages.agent_ids import AgentIds
import pytest
import sqlalchemy
from tests.e2e import traces
from tests.e2e.conftest import added_latency
from tests.e2e.conftest import E2E_LOCATION
from tests.e2e.conftest import E2E_PROJECT
from tests.e2e.conftest import E2E_TABLE

pytestmark = pytest.mark.e2e

# Long enough that the onboarding round trip is still in flight when the
# spinners are inspected. See conftest.added_latency.
_LATENCY_MS = 2000

_MONITOR_BUTTONS = "[id*='agent-monitor-btn-add']"


def _remote_agent(name: str, resource_id: str) -> AgentBase:
  """One of the agents GDA reports as living in the project."""
  return AgentBase(
      name=name,
      config=AgentConfig(
          project_id=E2E_PROJECT,
          location=E2E_LOCATION,
          agent_resource_id=resource_id,
          datasource=BigQueryConfig(tables=[E2E_TABLE]),
          system_instruction=traces.SYSTEM_INSTRUCTION,
      ),
  )


def test_only_the_clicked_monitor_button_spins(
    page: Page, base_url: str, db, cassettes
):
  """Two rows, one click, one spinner, one local agent."""
  cassettes.list_agents([
      _remote_agent("Orders Analyst", "orders-analyst"),
      _remote_agent("Returns Analyst", "returns-analyst"),
  ])
  # Onboarding redirects to the detail page, which fetches the remote config on
  # load. Installed against a throwaway row standing in for the one the server
  # is about to write; only the resource name is read off it.
  cassettes.get_agent(
      Agent(
          name="Returns Analyst",
          project_id=E2E_PROJECT,
          location=E2E_LOCATION,
          agent_resource_id="returns-analyst",
          datasource_config={"type": "bigquery", "tables": [E2E_TABLE]},
      )
  )

  page.goto(f"{base_url}/agents/onboard/existing")
  page.wait_for_load_state("networkidle")

  # PRISM_GDA_PROJECTS offers exactly one project and the form preselects it.
  expect(page.locator(f"#{AgentIds.Monitor.INPUT_PROJECT}")).to_have_value(
      E2E_PROJECT
  )
  page.locator(f"#{AgentIds.Monitor.BTN_FETCH}").click()

  buttons = page.locator(_MONITOR_BUTTONS)
  expect(buttons).to_have_count(2, timeout=30_000)

  with added_latency(page, _LATENCY_MS):
    buttons.nth(1).click()

    # Mantine puts data-loading on the button root when loading is set.
    expect(buttons.nth(1)).to_have_attribute("data-loading", "true")
    expect(buttons.nth(0)).not_to_have_attribute("data-loading", "true")

  page.wait_for_url("**/agents/view/*", timeout=60_000)

  agent = db.execute(sqlalchemy.select(Agent)).scalars().one()
  assert agent.name == "Returns Analyst", (
      "The clicked row and the onboarded agent have to be the same one. The "
      "server callback reads the index out of the triggered id, so an off-by-"
      "one here monitors the wrong agent."
  )
  page.wait_for_load_state("networkidle")
