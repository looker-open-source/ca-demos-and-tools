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

"""Journey: create an agent, edit it, archive it.

Every other spec seeds its agent straight into the database. This is the only
one that drives the three calls reaching GDA (``create_agent``, ``get_agent``,
``update_agent``) through the forms.

Those three cassettes are keyed on the full ``AgentConfig`` the callback
builds, so the fixtures below double as contract assertions. If ``add_agent``
or ``submit_edit`` starts sending something different, the cassette misses
instead of the spec passing against a request production never makes.

The last two specs are here for a different reason. Raising the form's loading
overlay, and the whole instruction view switch, are clientside callbacks.
Clientside callbacks are inline JS: they are absent from the callback map, so
neither the contract tier nor the dispatch tier can see them. A browser is the
only place they run.
"""

from __future__ import annotations
from playwright.sync_api import expect
from playwright.sync_api import Page
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

# Emulated round-trip latency, so a spec can see the page mid-request. Against
# a local server the round trip is under 60ms.
_LATENCY_MS = 1500

_NEW_AGENT_NAME = "Orders Analyst"
# The id GCP would assign. Fixed here so the detail page's get_agent cassette
# can be installed before the agent exists.
_RESOURCE_ID = "orders-analyst-1"
_EDITED_INSTRUCTION = "Answer in one sentence, and always cite the row count."


def test_create_an_agent_from_the_form(
    page: Page, base_url: str, db, cassettes
):
  """The Add Agent form creates the agent on GCP and locally."""
  # What add_agent builds from the form. agent_resource_id is empty because GCP
  # assigns it; the local row is created from the config GCP returns, not from
  # this one.
  submitted = AgentConfig(
      project_id=E2E_PROJECT,
      location=E2E_LOCATION,
      agent_resource_id="",
      datasource=BigQueryConfig(tables=[E2E_TABLE]),
      system_instruction=traces.SYSTEM_INSTRUCTION,
  )
  cassettes.create_agent(
      _NEW_AGENT_NAME, submitted, agent_resource_id=_RESOURCE_ID
  )
  # Submitting redirects straight to the detail page, which fetches the remote
  # config on load, so there is no gap to install that cassette afterwards.
  # Install it now against a throwaway row standing in for the one the server is
  # about to write. Only the four fields making up the resource name and the
  # datasource are read.
  cassettes.get_agent(
      Agent(
          name=_NEW_AGENT_NAME,
          project_id=E2E_PROJECT,
          location=E2E_LOCATION,
          agent_resource_id=_RESOURCE_ID,
          datasource_config={"type": "bigquery", "tables": [E2E_TABLE]},
      )
  )

  page.goto(f"{base_url}/agents/onboard/new")
  page.wait_for_load_state("networkidle")

  page.locator(f"#{AgentIds.Form.INPUT_NAME}").fill(_NEW_AGENT_NAME)
  page.locator(f"#{AgentIds.Form.TEXTAREA_INSTRUCTION}").fill(
      traces.SYSTEM_INSTRUCTION
  )
  page.locator(f"#{AgentIds.Form.INPUT_BQ_TABLES}").fill(E2E_TABLE)

  # PRISM_GDA_PROJECTS offers exactly one project and the form preselects it.
  # Asserted instead of clicked, because if the preselection stops happening the
  # cassette key changes and this reports it directly instead of as a miss.
  expect(page.locator(f"#{AgentIds.Form.INPUT_PROJECT}")).to_have_value(
      E2E_PROJECT
  )
  # No location field to fill. The form hardcodes "global", which the row
  # assertion below checks.

  page.locator(f"#{AgentIds.Add.BTN_SUBMIT}").click()
  page.wait_for_url("**/agents/view/*", timeout=30_000)

  db.expire_all()
  agent = db.execute(sqlalchemy.select(Agent)).scalars().one()
  assert agent.name == _NEW_AGENT_NAME
  assert agent.project_id == E2E_PROJECT
  assert agent.location == E2E_LOCATION
  # The id has to be the one GDA returned. A local row holding the submitted
  # empty id is unusable, since every later call builds its resource name from
  # it.
  assert agent.agent_resource_id == _RESOURCE_ID
  assert (agent.datasource_config or {}).get("tables") == [E2E_TABLE]

  expect(page.locator(f"#{AgentIds.Detail.TITLE}")).to_contain_text(
      _NEW_AGENT_NAME
  )
  # The detail page fires a dozen callbacks on load (header, datasource,
  # analytics charts). Navigating away mid-flight aborts them, and an aborted
  # XHR reaches the console as "Callback failed: the server did not respond".
  # The error gate is right to fail on that, but here it would be this spec's
  # doing, not the app's.
  page.wait_for_load_state("networkidle")

  page.goto(f"{base_url}/agents")
  page.wait_for_load_state("networkidle")
  expect(page.locator(f"#{AgentIds.Home.CARD_GRID}")).to_contain_text(
      _NEW_AGENT_NAME
  )


def test_edit_and_archive_an_agent(
    page: Page, base_url: str, seed, db, cassettes
):
  """Editing pushes the new instruction to GCP; archiving hides the agent."""
  agent = seed.agent(name=_NEW_AGENT_NAME, agent_resource_id=_RESOURCE_ID)
  cassettes.get_agent(agent)
  # submit_edit rebuilds the config from the local row, replacing only the
  # instruction and the tables. Everything else carries over, so this has to
  # match field for field.
  cassettes.update_agent(
      agent,
      system_instruction=_EDITED_INSTRUCTION,
      config=AgentConfig(
          project_id=agent.project_id,
          location=agent.location,
          agent_resource_id=agent.agent_resource_id,
          datasource=BigQueryConfig(tables=[E2E_TABLE]),
          system_instruction=_EDITED_INSTRUCTION,
      ),
  )

  page.goto(f"{base_url}/agents/view/{agent.id}")
  page.wait_for_load_state("networkidle")

  page.locator(f"#{AgentIds.Detail.BTN_EDIT}").click()
  instruction = page.locator(f"#{AgentIds.Detail.TEXTAREA_EDIT_INSTRUCTION}")
  expect(instruction).to_be_visible()
  instruction.fill(_EDITED_INSTRUCTION)
  page.locator(f"#{AgentIds.Detail.BTN_EDIT_SUBMIT}").click()

  # The modal closes only on success. On failure it stays open with a red toast,
  # so this is what asserts the GCP write went through.
  expect(page.locator(f"#{AgentIds.Detail.MODAL_EDIT}")).to_be_hidden(
      timeout=30_000
  )

  page.locator(f"#{AgentIds.Detail.BTN_ARCHIVE}").click()
  expect(page.locator(f"#{AgentIds.Detail.BTN_RESTORE}")).to_be_visible(
      timeout=30_000
  )

  db.expire_all()
  archived = db.get(Agent, agent.id)
  assert archived.is_archived, (
      "Archive reported success but the row is still active, so the agent "
      "keeps appearing everywhere it is listed."
  )

  # Let the archive's re-render settle. See the note in the creation spec about
  # aborted callbacks reaching the console as errors.
  page.wait_for_load_state("networkidle")

  # Archived agents are hidden from the list until the switch is turned on.
  page.goto(f"{base_url}/agents")
  page.wait_for_load_state("networkidle")
  expect(page.locator(f"#{AgentIds.Home.CARD_GRID}")).not_to_contain_text(
      _NEW_AGENT_NAME
  )


def test_a_rejected_form_lowers_the_overlay_it_raised(
    page: Page, base_url: str, db
):
  """Validation has to put the form back, not just refuse the submission."""
  page.goto(f"{base_url}/agents/onboard/new")
  page.wait_for_load_state("networkidle")

  overlay = page.locator(f"#{AgentIds.Add.LOADING_OVERLAY}")

  # Latency, so the raised state lasts long enough to be looked at. Without it
  # the request can land before the first assertion runs, and the spec passes
  # on an overlay that was never raised, which is the same result as the
  # clientside callback having been deleted.
  with added_latency(page, _LATENCY_MS):
    # Everything blank but the preselected project, so add_agent takes the
    # validation branch and never reaches GDA. No cassette needed.
    page.locator(f"#{AgentIds.Add.BTN_SUBMIT}").click()

    expect(overlay).to_be_visible()

  expect(page.get_by_text("Validation Error")).to_be_visible(timeout=30_000)

  # Only the server's False takes the overlay back down, so returning
  # no_update on this branch would leave the form covered with nothing to
  # click and no error to read.
  expect(overlay).to_be_hidden(timeout=30_000)

  name = page.locator(f"#{AgentIds.Form.INPUT_NAME}")
  name.fill(_NEW_AGENT_NAME)
  expect(name).to_have_value(_NEW_AGENT_NAME)

  assert not db.execute(sqlalchemy.select(Agent)).scalars().all()


def test_the_instruction_view_switch_swaps_the_two_panes(
    page: Page, base_url: str, seed, cassettes
):
  """Both panes are always in the DOM. The switch only changes display."""
  agent = seed.agent(name=_NEW_AGENT_NAME, agent_resource_id=_RESOURCE_ID)
  cassettes.get_agent(agent)

  page.goto(f"{base_url}/agents/view/{agent.id}")
  page.wait_for_load_state("networkidle")

  markdown = page.locator(f"#{AgentIds.Detail.INSTRUCTION_MARKDOWN}")
  raw = page.locator(f"#{AgentIds.Detail.INSTRUCTION_RAW}")
  expect(markdown).to_be_visible()
  expect(raw).to_be_hidden()

  page.locator(f"#{AgentIds.Detail.SWITCH_INSTRUCTION_VIEW}").click()
  expect(raw).to_be_visible(timeout=30_000)
  expect(markdown).to_be_hidden()
  # Same text either way. A swap showing the wrong pane's contents would still
  # satisfy the visibility checks above.
  expect(raw).to_contain_text(traces.SYSTEM_INSTRUCTION)

  page.locator(f"#{AgentIds.Detail.SWITCH_INSTRUCTION_VIEW}").click()
  expect(markdown).to_be_visible(timeout=30_000)
  expect(raw).to_be_hidden()
