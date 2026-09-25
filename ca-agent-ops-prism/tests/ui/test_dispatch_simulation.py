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

"""The playground simulation, driven through Dash's HTTP dispatch route.

Three callbacks run a simulation between them. ``start_simulation_run`` answers
the click with a skeleton and a fresh timestamp, ``execute_simulation`` reads
that timestamp and does the work, and ``load_playground_data`` fills the page
the two of them run on. None of it needs a browser: the banner, the alert and
the skeletons are server-built components that arrive in the POST response, and
the stores are plain JSON.

``execute_simulation`` carries no ``@handle_errors`` of its own, so its except
branch is the only thing that reports a failed run. The gate sees the log line
it writes, which is why the failure test consumes one error rather than
asserting there were none.
"""

from __future__ import annotations

import datetime
import json
from typing import Any
from unittest import mock

from prism.client.playground_client import PlaygroundClient
from prism.common.schemas import assertion as assertion_schemas
from prism.common.schemas.execution import AssertionResult
from prism.common.schemas.trace import PlaygroundTraceSchema
from prism.common.schemas.trace import SimulationResult
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.services.playground_service import PlaygroundService
from prism.server.services.suggestion_service import SuggestionService
from prism.server.services.suite_service import SuiteService
from prism.ui.callbacks import test_suite_questions_callbacks
from prism.ui.ids import TestSuiteIds
import pytest
from tests.ui import dash_http

_UTC = datetime.timezone.utc


def _rendered(body: dict[str, Any], address: str) -> str:
  """The JSON of one returned property, for substring assertions.

  The values are serialized component trees. Reading them as text is enough
  here, and it keeps the test off the shape of dmc's JSON.
  """
  component_id, prop = address.rsplit(".", 1)
  assert component_id in body["response"], (
      f"{address} was not written. The callback returned:"
      f" {sorted(body['response'])}"
  )
  return json.dumps(body["response"][component_id][prop])


def _assertion_result(
    value: str, passed: bool, score: float, weight: float
) -> AssertionResult:
  """One scored assertion, with the weight that decides if it counts."""
  return AssertionResult(
      assertion=assertion_schemas.TextContains(value=value, weight=weight),
      passed=passed,
      score=score,
  )


def _simulation_result(passed: bool) -> SimulationResult:
  """What ``PlaygroundClient.run_simulation`` hands the callback.

  Produced by the real method over stubbed services, not hand-written.
  ``result_summary`` is a plain dict the callback indexes by key, so a key
  renamed in the client and not in the callback is invisible to a fixture that
  spells the keys out itself. Two weighted assertions and one diagnostic, so
  the "N of M" count and the accuracy average cannot come out the same number.
  """
  results = [
      _assertion_result("orders", True, 1.0, 1.0),
      _assertion_result("revenue", False, 0.0, 1.0),
      _assertion_result("diagnostic", True, 1.0, 0.0),
  ]
  trace = PlaygroundTraceSchema(
      id=7,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=_UTC),
      question="How many seeded orders are there?",
      agent_id=1,
      trace_results=[],
      assertion_results=results,
      output_text="42 orders",
      score=0.5,
      duration_ms=1234,
      passed=passed,
  )

  playground_service = mock.Mock(spec=PlaygroundService)
  playground_service.execute_and_save.return_value = trace
  suite_service = mock.Mock(spec=SuiteService)
  suite_service.get_example.return_value = mock.Mock(asserts=[])
  suggestion_service = mock.Mock(spec=SuggestionService)
  suggestion_service.suggest_assertions_from_trace.return_value = [
      assertion_schemas.TextContains(value="42", weight=1.0)
  ]
  agent_repo = mock.Mock(spec=AgentRepository)
  agent_repo.get_by_id.return_value = None

  return PlaygroundClient().run_simulation(
      agent_id=1,
      example_id=11,
      playground_service=playground_service,
      suggestion_service=suggestion_service,
      suite_service=suite_service,
      agent_repo=agent_repo,
  )


@pytest.fixture(name="playground")
def _playground(monkeypatch):
  """Puts a stub where the playground callbacks reach for their client.

  tests/ui runs with ``PRISM_AGENT_BACKEND`` unset, which is live, so a real
  client here would put the question to the agent for real.
  """
  client = mock.Mock()
  monkeypatch.setattr(
      test_suite_questions_callbacks, "get_client", lambda: client
  )
  return client.playground


def _fire_simulation(dash_client, agent_id: str, example_id: int):
  """POSTs the trigger ``start_simulation_run`` would have written."""
  deps = dash_http.dependencies(dash_client)
  # Named by its trigger: the delete-confirm callback clears the same store.
  dep = dash_http.find(
      deps,
      f"{TestSuiteIds.STORE_PLAYGROUND_RESULT}.data",
      triggered_by=TestSuiteIds.STORE_START_RUN,
  )
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{TestSuiteIds.STORE_START_RUN}.data": {"ts": 1758000000000},
          f"{TestSuiteIds.STORE_BUILDER}.data": [
              {"id": example_id, "question": "q", "asserts": []}
          ],
          f"{TestSuiteIds.STORE_SELECTED_INDEX}.data": 0,
          f"{TestSuiteIds.TC_AGENT_SELECT}.value": agent_id,
      },
  )


def test_a_successful_simulation_renders_the_result_banner(
    dash_client, callback_errors, playground
):
  """The banner is the only report of what the simulation did.

  Everything asserted here is read out of ``result_summary`` by key, so a key
  drift in ``PlaygroundClient`` shows up as a missing count, a missing duration
  or a KeyError on ``passed``. The stores matter too: the suggestion list and
  every later suggestion action read them, so a result that will not serialize
  leaves the page with a banner and nothing to act on.
  """
  playground.run_simulation.return_value = _simulation_result(passed=True)

  response = _fire_simulation(dash_client, "3", example_id=11)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  playground.run_simulation.assert_called_once_with(agent_id=3, example_id=11)

  body = dash_http.body(response)
  banner = _rendered(body, f"{TestSuiteIds.SIM_CONTEXT_CONTAINER}.children")
  # Two of the three assertions passed, and only the two weighted ones count
  # towards accuracy, so 2 of 3 and 50.0% have to disagree.
  assert "2 of 3 assertions passed" in banner
  assert "Duration: 1234ms" in banner
  assert "Accuracy: 50.0%" in banner
  assert "material-symbols:check-circle" in banner
  # green, not emerald. Mantine has no emerald palette, so the old
  # c="emerald.7" fell through to the theme default and left the banner
  # the same colour whether the run passed or not.
  assert "green" in banner

  result = body["response"][TestSuiteIds.STORE_PLAYGROUND_RESULT]["data"]
  assert result["passed"] is True
  assert len(result["assertion_results"]) == 3
  suggestions = body["response"][TestSuiteIds.STORE_SUGGESTIONS]["data"]
  assert [s["value"] for s in suggestions] == ["42"]
  assert body["response"][TestSuiteIds.TC_RUN_BTN]["loading"] is False


def test_a_failing_simulation_is_banded_red_not_green(
    dash_client, callback_errors, playground
):
  """A run that failed its assertions must not read as a pass.

  The colour and the icon are the whole signal at a glance, and they come off
  ``result["passed"]``, not off the count.
  """
  playground.run_simulation.return_value = _simulation_result(passed=False)

  response = _fire_simulation(dash_client, "3", example_id=11)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  banner = _rendered(
      dash_http.body(response), f"{TestSuiteIds.SIM_CONTEXT_CONTAINER}.children"
  )
  assert "material-symbols:cancel" in banner
  assert "green" not in banner


def test_clicking_run_writes_a_fresh_trigger_and_the_skeletons(
    dash_client, callback_errors
):
  """The click does nothing by itself. It writes the timestamp that does.

  ``execute_simulation`` is driven by ``store-start-run``, so a click that
  stops writing a new value there leaves the button dead with no error. The
  skeletons are the only thing on screen for the length of the run.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteIds.STORE_START_RUN}.data")

  # Both ends are whole milliseconds, because the callback truncates and a
  # fractional bound rejects a timestamp taken in the same millisecond.
  before = int(datetime.datetime.now(_UTC).timestamp() * 1000)
  response = dash_http.fire(
      dash_client, dep, {f"{TestSuiteIds.TC_RUN_BTN}.n_clicks": 1}
  )
  after = int(datetime.datetime.now(_UTC).timestamp() * 1000)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)
  ts = body["response"][TestSuiteIds.STORE_START_RUN]["data"]["ts"]
  # Wall clock rather than two fires, because two POSTs can land in the same
  # millisecond. A constant would fail this on the second day.
  assert before <= ts <= after, ts

  assert body["response"][TestSuiteIds.TC_RUN_BTN]["loading"] is True
  context = _rendered(body, f"{TestSuiteIds.SIM_CONTEXT_CONTAINER}.children")
  suggestions = _rendered(body, f"{TestSuiteIds.SUG_LIST}.children")
  assert context.count('"Skeleton"') == 2, context
  assert suggestions.count('"Skeleton"') == 2, suggestions


def test_a_failed_simulation_alerts_and_stops_the_spinner(
    dash_client, callback_errors, playground
):
  """The except branch is the only thing that stops the button spinning.

  ``start_simulation_run`` set ``loading=True`` and nothing else turns it off,
  so a simulation that raises without this leaves the page spinning forever
  with no reason given. Both stores are cleared on the way out. Holding the
  last good result kept the previous run's pass and fail badges on the
  assertions under the error, and left the suggestion skeleton spinning for a
  list that will never arrive.
  """
  playground.run_simulation.side_effect = RuntimeError("no such agent")

  response = _fire_simulation(dash_client, "3", example_id=11)

  assert response.status_code == 200, response.data[:2000]
  # The except branch logs the exception itself. Consuming that one record and
  # leaving the gate empty is what proves handle_errors did not have to step in
  # on top of it.
  callback_errors.assert_logged("Simulation failed")
  callback_errors.assert_none()

  body = dash_http.body(response)
  alert = _rendered(body, f"{TestSuiteIds.SIM_CONTEXT_CONTAINER}.children")
  assert "Simulation Error" in alert
  assert "no such agent" not in alert, "the exception text belongs in the log"
  assert body["response"][TestSuiteIds.TC_RUN_BTN]["loading"] is False
  assert body["response"][TestSuiteIds.STORE_PLAYGROUND_RESULT]["data"] is None
  assert body["response"][TestSuiteIds.STORE_SUGGESTIONS]["data"] is None


def test_the_suite_edit_page_load_fills_the_agent_dropdown(
    dash_client, callback_errors, seeded
):
  """Nothing else loads the playground, and no sweep reaches it.

  Its one Input is ``tc-agent-select.id``, a component mount rather than a
  location property, so ``url_only`` drops it and the page-load sweep in
  test_callback_dispatch never fires it. With an empty dropdown there is no
  agent to run against and the Run button stays disabled.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteIds.TC_AGENT_SELECT}.data")

  pathname = f"/test_suites/edit/{seeded.suite_id}"
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{TestSuiteIds.TC_AGENT_SELECT}.id": TestSuiteIds.TC_AGENT_SELECT,
          "url.pathname": pathname,
          "url.search": "",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)
  agents = body["response"][TestSuiteIds.TC_AGENT_SELECT]["data"]
  assert agents == [
      {"label": seeded.agent_name, "value": str(seeded.agent_id)}
  ], agents

  builder = body["response"][TestSuiteIds.STORE_BUILDER]["data"]
  assert [tc["question"] for tc in builder] == [seeded.question], builder
  assert body["response"][TestSuiteIds.STORE_SELECTED_INDEX]["data"] == 0

  breadcrumb = body["response"][TestSuiteIds.TC_BREADCRUMB_SUITE_NAME]
  assert breadcrumb["children"] == seeded.suite_name
  assert breadcrumb["href"] == f"/test_suites/view/{seeded.suite_id}"
