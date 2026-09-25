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

"""Journey: start an evaluation and watch it finish.

The only spec that drives the real execution path end to end. Clicking Start
Run creates the run, snapshots the agent's published context, and hands the
trials to the worker pool, which spawns each one in a ``multiprocessing``
subprocess under the ``spawn`` context: a fresh interpreter that re-imports
everything and shares no state with the server or this test.

That subprocess is why the replay backend is selected by environment variable
instead of monkeypatch. A patch applied here would not survive the re-import
and the child would call the real API.
"""

from __future__ import annotations

from playwright.sync_api import expect
from playwright.sync_api import Page
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.ui.ids import EvaluationIds
import pytest
import sqlalchemy
from tests.e2e import traces
from tests.e2e.conftest import select_option

pytestmark = pytest.mark.e2e

# Trials run in spawned subprocesses, each paying a fresh interpreter start.
_RUN_TIMEOUT_MS = 120_000


def test_start_a_run_and_see_it_complete(
    page: Page, base_url: str, seed, db, cassettes
):
  """A run started from the UI executes its trials and reports 100%."""
  agent = seed.agent()
  suite = seed.suite()
  seed.example(
      suite,
      question=traces.QUESTION,
      assertions=[
          (AssertionType.TEXT_CONTAINS, {"value": "128"}),
          (AssertionType.QUERY_CONTAINS, {"value": "COUNT(*)"}),
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

  # The callback redirects to the new run's detail page.
  page.wait_for_url("**/evaluations/runs/*", timeout=30_000)

  # The page polls while the run is active, so the badge is the real signal that
  # the worker pool picked the run up, ran it, and aggregated the result.
  expect(page.locator(f"#{EvaluationIds.RUN_STATUS_BADGE}")).to_contain_text(
      "COMPLETED", timeout=_RUN_TIMEOUT_MS, ignore_case=True
  )

  stats = page.locator(f"#{EvaluationIds.RUN_DETAIL_STATS}")
  expect(stats).to_contain_text("100.0%")

  trials = page.locator(f"#{EvaluationIds.RUN_TRIALS_CONTAINER}")
  expect(trials).to_contain_text(traces.QUESTION)
  expect(trials).to_contain_text("Completed")

  # The subprocess is the part that could have quietly hit the network. It
  # writes back through the database, so that is where to confirm its work.
  db.expire_all()
  run = db.execute(sqlalchemy.select(Run)).scalars().one()
  assert run.status == RunStatus.COMPLETED
  trial = (
      db.execute(sqlalchemy.select(Trial).where(Trial.run_id == run.id))
      .scalars()
      .one()
  )
  assert trial.status == RunStatus.COMPLETED
  assert trial.trace_results, "The replayed trace was never persisted."
  assert traces.ANSWER in (trial.output_text or "")
  # The count first. all() on an empty list is True, so a trial that scored
  # nothing at all read the same here as a trial that passed both assertions.
  assert len(trial.assertion_results) == 2
  assert all(result.passed for result in trial.assertion_results)
