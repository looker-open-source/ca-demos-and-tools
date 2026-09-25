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

"""Regression: double-clicking a submit button did the work twice.

None of the three eval-start buttons declared a Dash ``running=`` spec, so each
stayed live for the whole round trip: creating a run, snapshotting the agent's
published context, handing it to the worker pool. A second click inside that
window created a second run, and both ran every trial in the suite against a
paid API.

The three agent write forms guard the same window a different way. Each raises
a ``dmc.LoadingOverlay`` over the form from a clientside callback on click, and
the server callback lowers it when the write finishes. The overlay is what
swallows a second click, so it has to be inside the same positioned container
as the button. Nothing but a browser can tell you that it is: the raise is
inline JS, and whether one element covers another is layout.

The defect lives in the gap between the click and the response, so only a
browser reproduces it. ``test_callback_contracts`` checks that all three
``running=`` specs are declared; the two specs below check that a declared one
has the effect we want. The third button, on the agent detail page's eval
modal, is left to the contract check. It is the same callback shape, and a spec
for it would cost another full run.

Two things have to be right for these specs to mean anything. Both were wrong
in earlier drafts, which passed against an unguarded button:

* ``dblclick`` does not work. Two clicks in one frame land in a single React
  batch, so Dash sees one ``n_clicks`` change and fires the callback once
  whether or not the guard exists. The clicks need a gap.
* The gap needs somewhere to fit. Against a local server the round trip is
  under 60ms, so by the time a second click is attempted the page has already
  navigated to the new run, and a spec that never lands its second click passes
  for the wrong reason. CDP latency emulation widens the window instead of
  hoping for one.
"""

from __future__ import annotations
from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.ui.ids import EvaluationIds
from prism.ui.pages.agent_ids import AgentIds
import pytest
import sqlalchemy
from tests.e2e import traces
from tests.e2e.conftest import added_latency
from tests.e2e.conftest import E2E_LOCATION
from tests.e2e.conftest import E2E_PROJECT
from tests.e2e.conftest import E2E_TABLE
from tests.e2e.conftest import select_option

pytestmark = pytest.mark.e2e

# Emulated round-trip latency, and how long after the first click the second
# one lands. The second click has to fall inside the first request's flight.
_LATENCY_MS = 1500
_SECOND_CLICK_AT_MS = 500

_NEW_AGENT_NAME = "Orders Analyst"
_COPY_NAME = "Orders Analyst (copy)"
# The ids GCP would assign. Fixed so the detail page each redirect lands on can
# have its get_agent cassette installed before the agent exists.
_RESOURCE_ID = "orders-analyst-1"
_COPY_RESOURCE_ID = "orders-analyst-2"
_EDITED_INSTRUCTION = "Answer in one sentence, and always cite the row count."


def test_double_clicking_start_run_creates_one_run(
    page: Page, base_url: str, seed, db, cassettes
):
  """A second click while the first is in flight creates no second run."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(suite)
  cassettes.agent_context(agent)
  cassettes.datasource_kind(agent)
  cassettes.ask_question(agent)

  page.goto(f"{base_url}/test_suites/view/{suite.id}")
  page.wait_for_load_state("networkidle")

  page.locator(f"#{EvaluationIds.BTN_OPEN_RUN_MODAL}").click()
  select_option(page, EvaluationIds.AGENT_SELECT, agent.name)

  start = page.locator(f"#{EvaluationIds.BTN_START_RUN}")
  expect(start).to_be_enabled()

  with added_latency(page, _LATENCY_MS):
    start.click()
    page.wait_for_timeout(_SECOND_CLICK_AT_MS)

    # The guard has had every chance to apply by now. Dash sets the running
    # values when it dispatches the request, not when the response lands.
    expect(start).to_be_disabled()

    # force=True makes this an attempt, not a wait. An ordinary click() would
    # block until the button re-enabled, by which point the run exists and there
    # is nothing left to race. Against a disabled button the browser fires no
    # click event, which is the protection under test.
    start.click(force=True)

  # The callback redirects to the new run once it finishes.
  page.wait_for_url("**/evaluations/runs/*", timeout=60_000)

  runs = db.execute(sqlalchemy.select(Run.id)).scalars().all()
  assert len(runs) == 1, (
      f"A double-click created {len(runs)} runs ({runs}). Each one executes "
      "every trial in the suite against a paid API."
  )


def test_double_clicking_start_new_eval_creates_one_run(
    page: Page, base_url: str, seed, db, cassettes
):
  """The Evaluations page has its own Start Run button and its own callback.

  Same defect, second site. The two buttons share nothing but a label, so
  guarding one leaves the other open.
  """
  agent = seed.agent()
  suite = seed.suite()
  seed.example(suite)
  cassettes.agent_context(agent)
  cassettes.datasource_kind(agent)
  cassettes.ask_question(agent)

  page.goto(f"{base_url}/evaluations")
  page.wait_for_load_state("networkidle")

  page.locator(f"#{EvaluationIds.BTN_NEW_EVAL}").click()
  # Opening the modal is what fills both selects, over the wire. Picking an
  # option before that lands would open an empty listbox.
  page.wait_for_load_state("networkidle")
  select_option(page, EvaluationIds.NEW_EVAL_AGENT_SELECT, agent.name)
  select_option(page, EvaluationIds.NEW_EVAL_SUITE_SELECT, suite.name)

  start = page.locator(f"#{EvaluationIds.BTN_START_NEW_EVAL}")
  expect(start).to_be_enabled()

  with added_latency(page, _LATENCY_MS):
    start.click()
    page.wait_for_timeout(_SECOND_CLICK_AT_MS)

    expect(start).to_be_disabled()
    # force=True for the same reason as the spec above: an attempt, not a wait.
    start.click(force=True)

  page.wait_for_url("**/evaluations/runs/*", timeout=60_000)

  runs = db.execute(sqlalchemy.select(Run.id)).scalars().all()
  assert len(runs) == 1, (
      f"A double-click created {len(runs)} runs ({runs}). Each one executes "
      "every trial in the suite against a paid API."
  )


def test_double_clicking_create_agent_creates_one_agent(
    page: Page, base_url: str, db, cassettes
):
  """A second click while the first is in flight creates no second agent."""
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
  # config on load. See the note in test_agent_crud about installing this
  # against a throwaway row.
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

  submit = page.locator(f"#{AgentIds.Add.BTN_SUBMIT}")
  with added_latency(page, _LATENCY_MS):
    submit.click()
    page.wait_for_timeout(_SECOND_CLICK_AT_MS)

    expect(page.locator(f"#{AgentIds.Add.LOADING_OVERLAY}")).to_be_visible()

    # force=True for the same reason as the run spec above: an attempt, not a
    # wait. The click is dispatched at the button's coordinates, so whatever is
    # on top of them receives it.
    submit.click(force=True)

  page.wait_for_url("**/agents/view/*", timeout=60_000)

  agents = db.execute(sqlalchemy.select(Agent.id)).scalars().all()
  assert len(agents) == 1, (
      f"A double-click created {len(agents)} agents ({agents}). Each one is a "
      "real agent on GCP that someone has to find and delete."
  )
  page.wait_for_load_state("networkidle")


def test_double_clicking_duplicate_creates_one_copy(
    page: Page, base_url: str, seed, db, cassettes
):
  """Same window, same overlay, on the duplicate modal."""
  agent = seed.agent(name=_NEW_AGENT_NAME, agent_resource_id=_RESOURCE_ID)
  cassettes.get_agent(agent)
  # duplicate_agent reads the config back off GCP and registers it under the
  # new name, so the copy's cassette key is the original's config unchanged.
  copied = AgentConfig(
      project_id=agent.project_id,
      location=agent.location,
      agent_resource_id=agent.agent_resource_id,
      datasource=BigQueryConfig(tables=[E2E_TABLE]),
      system_instruction=traces.SYSTEM_INSTRUCTION,
  )
  cassettes.create_agent(
      _COPY_NAME, copied, agent_resource_id=_COPY_RESOURCE_ID
  )
  cassettes.get_agent(
      Agent(
          name=_COPY_NAME,
          project_id=E2E_PROJECT,
          location=E2E_LOCATION,
          agent_resource_id=_COPY_RESOURCE_ID,
          datasource_config={"type": "bigquery", "tables": [E2E_TABLE]},
      )
  )

  page.goto(f"{base_url}/agents/view/{agent.id}")
  page.wait_for_load_state("networkidle")

  page.locator(f"#{AgentIds.Detail.BTN_DUPLICATE}").click()
  name = page.locator(f"#{AgentIds.Detail.INPUT_DUPLICATE_NAME}")
  expect(name).to_be_visible()
  # The modal prefills "Copy of <name>". Overwritten with a fixed name because
  # it is part of the cassette key.
  name.fill(_COPY_NAME)

  submit = page.locator(f"#{AgentIds.Detail.BTN_DUPLICATE_SUBMIT}")
  with added_latency(page, _LATENCY_MS):
    submit.click()
    page.wait_for_timeout(_SECOND_CLICK_AT_MS)

    expect(
        page.locator(f"#{AgentIds.Detail.DUPLICATE_LOADING_OVERLAY}")
    ).to_be_visible()
    submit.click(force=True)

  # Both pages are /agents/view/<id>, so the URL pattern cannot tell the
  # redirect from where we started. The title can.
  expect(page.locator(f"#{AgentIds.Detail.TITLE}")).to_contain_text(
      _COPY_NAME, timeout=60_000
  )

  names = db.execute(sqlalchemy.select(Agent.name)).scalars().all()
  assert names == [
      _NEW_AGENT_NAME,
      _COPY_NAME,
  ], f"Expected the original and one copy, got {names}."
  page.wait_for_load_state("networkidle")


def test_the_edit_modal_covers_its_submit_button_while_saving(
    page: Page, base_url: str, seed, cassettes
):
  """Editing twice is harmless, so this asserts the cover, not the row count.

  Saving the same instruction twice leaves nothing behind to count. What can
  still break is the cover itself: move the LoadingOverlay out of the
  positioned div holding the button and it renders over the wrong box, with
  nothing failing anywhere else.
  """
  agent = seed.agent(name=_NEW_AGENT_NAME, agent_resource_id=_RESOURCE_ID)
  cassettes.get_agent(agent)
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

  submit = page.locator(f"#{AgentIds.Detail.BTN_EDIT_SUBMIT}")
  with added_latency(page, _LATENCY_MS):
    submit.click()
    page.wait_for_timeout(_SECOND_CLICK_AT_MS)

    expect(
        page.locator(f"#{AgentIds.Detail.EDIT_LOADING_OVERLAY}")
    ).to_be_visible()

    # Ask the browser what is under the button's centre. Everything Playwright
    # offers here retries until the element is actionable, and the overlay
    # comes down the moment the save lands, so any of them would go green by
    # waiting rather than by the cover being wrong. This is one question asked
    # once, while the save is still in flight.
    on_top = page.evaluate(
        """([id]) => {
            const button = document.getElementById(id);
            const box = button.getBoundingClientRect();
            const top = document.elementFromPoint(
                box.x + box.width / 2, box.y + box.height / 2);
            return button.contains(top) ? 'the button itself' : top.className;
        }""",
        [AgentIds.Detail.BTN_EDIT_SUBMIT],
    )
    assert on_top != "the button itself", (
        "Save Changes is still the topmost element while the save is in "
        "flight, so a second click reaches it and pushes the edit to GCP "
        "twice."
    )

  expect(page.locator(f"#{AgentIds.Detail.MODAL_EDIT}")).to_be_hidden(
      timeout=60_000
  )
  page.wait_for_load_state("networkidle")
