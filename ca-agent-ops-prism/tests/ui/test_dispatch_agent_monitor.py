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

"""Dispatch tests for agent discovery and the agent trace page.

The browser suite covers discovery: ``tests/e2e/conftest.py`` has a
``list_agents`` cassette and ``tests/e2e/test_agent_discovery.py`` installs it.
The trace page it cannot reach, because that route is a path template, so
``dash.page_registry`` holds ``/evaluations/trials/none/trace`` and the
``int()`` in the callback rejects it. Everything these callbacks produce is
text in the ``/_dash-update-component`` body, so a POST sees all of it.
"""

from __future__ import annotations
import datetime
import json
import re
import pytest
from tests.ui import dash_http

from prism.common.schemas.agent import AgentBase
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import BigQueryConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Trial

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import
from prism.ui.callbacks import agent_monitor_callbacks
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
from prism.ui.pages.agent_ids import AgentIds

_DISCOVERY_PATH = "/agents/onboard/existing"

_BQ_AGENT = AgentBase(
    name="Orders Analyst",
    config=AgentConfig(
        project_id="proj-a",
        location="us",
        agent_resource_id="orders-analyst",
        datasource=BigQueryConfig(tables=["proj-a.sales.orders"]),
        system_instruction="Answer questions about orders.",
    ),
)

_LOOKER_AGENT = AgentBase(
    name="Looker Analyst",
    config=AgentConfig(
        project_id="proj-a",
        location="global",
        agent_resource_id="looker-analyst",
        datasource=LookerConfig(
            instance_uri="https://example.looker.com", explores=["sales"]
        ),
    ),
)


class _FakeAgents:
  """The slice of ``get_client().agents`` the discovery callback uses."""

  def __init__(self, discovered=(), monitored=(), projects=(), error=None):
    self.discovered = list(discovered)
    self.monitored = list(monitored)
    self.projects = list(projects)
    self.error = error

  def discover_gcp_agents(self, project_id):
    del project_id
    if self.error:
      raise self.error
    return self.discovered

  def list_agents(self):
    return self.monitored

  def get_configured_gda_projects(self):
    return self.projects


def _use_agents(monkeypatch, agents: _FakeAgents) -> None:
  """Points the discovery callbacks at ``agents`` instead of the real GDA API.

  ``tests/ui`` runs with ``PRISM_AGENT_BACKEND`` unset, so without this
  ``discover_gcp_agents`` reaches Google Cloud.
  """

  class _Client:
    pass

  _Client.agents = agents
  monkeypatch.setattr(agent_monitor_callbacks, "get_client", _Client)


def _discovery_dep(dash_client):
  """The ``perform_discovery`` entry.

  Addressed by the store rather than by the table, because
  ``start_discovery`` writes the same table with ``allow_duplicate``.
  """
  deps = dash_http.dependencies(dash_client)
  return dash_http.find(deps, f"{AgentIds.Monitor.STORE_DISCOVERED}.data")


def _discover(dash_client, project_id="proj-a"):
  """Fires ``perform_discovery`` as the fetch trigger would."""
  dep = _discovery_dep(dash_client)
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{AgentIds.Monitor.STORE_FETCH_TRIGGER}.data": True,
          f"{AgentIds.Monitor.INPUT_PROJECT}.value": project_id,
      },
  )


def test_clicking_fetch_twice_writes_a_different_trigger_each_time(
    dash_client, callback_errors
):
  """The trigger is a Store, so the same value twice is not a change.

  ``start_discovery`` used to write a bare True. ``perform_discovery`` reads
  that store and nothing resets it, so the second click wrote True over True,
  the observer did not fire and the fetch never ran again. Changing the
  project and clicking Fetch left the skeleton up until a reload.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Monitor.STORE_FETCH_TRIGGER}.data")
  clicks = f"{AgentIds.Monitor.BTN_FETCH}.n_clicks"

  triggers = []
  for n_clicks in (1, 2):
    response = dash_http.fire(
        dash_client, dep, {clicks: n_clicks}, changed=[clicks]
    )
    assert response.status_code == 200, response.data[:2000]

    body = dash_http.body(response)["response"]
    # The skeleton goes up on every click, not only on the first.
    assert "Skeleton" in json.dumps(
        body[AgentIds.Monitor.TABLE_ROOT]["children"]
    )
    triggers.append(body[AgentIds.Monitor.STORE_FETCH_TRIGGER]["data"])

  callback_errors.assert_none()
  for trigger in triggers:
    assert isinstance(trigger, dict), trigger
    assert isinstance(trigger["ts"], float), trigger
  assert triggers[0] != triggers[1], triggers


def test_discovery_renders_the_agents_it_found(
    dash_client, callback_errors, monkeypatch
):
  """The results table has to carry what the user picks an agent by.

  Name, which datasource it is wired to, and the system instruction. The
  datasource label is derived from the shape of the dumped config, not from a
  type tag, so a BigQuery agent showing as Looker is the regression here.
  """
  _use_agents(monkeypatch, _FakeAgents(discovered=[_BQ_AGENT, _LOOKER_AGENT]))

  response = _discover(dash_client)
  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  table = json.dumps(body[AgentIds.Monitor.TABLE_ROOT]["children"])
  assert "Orders Analyst" in table
  assert "Answer questions about orders." in table
  assert "BigQuery" in table
  assert "Looker" in table
  assert "Unknown" not in table

  # The store is what the Monitor button reads back, so the rows on screen are
  # useless if it did not come with them.
  stored = body[AgentIds.Monitor.STORE_DISCOVERED]["data"]
  assert [a["config"]["agent_resource_id"] for a in stored] == [
      "orders-analyst",
      "looker-analyst",
  ]


def test_discovery_says_which_kind_of_nothing_it_found(
    dash_client, callback_errors, monkeypatch
):
  """The three empty outcomes are different problems and must read that way.

  A project with no agents is a project id to check. A project whose agents
  are all monitored already is nothing to do. A failed call is a server log to
  read. One shared "no agents" alert for all three sends the user to the wrong
  place.
  """
  cases = [
      (
          _FakeAgents(discovered=[]),
          "No agents found in this project.",
          "yellow",
          False,
      ),
      (
          _FakeAgents(discovered=[_BQ_AGENT], monitored=[_BQ_AGENT]),
          "No new agents found.",
          "yellow",
          False,
      ),
      (
          _FakeAgents(error=RuntimeError("seeded failure")),
          "Could not list the agents in this project.",
          "red",
          True,
      ),
  ]

  for agents, expected, color, logs in cases:
    _use_agents(monkeypatch, agents)
    response = _discover(dash_client)
    assert response.status_code == 200, response.data[:2000]

    body = dash_http.body(response)["response"]
    alert = body[AgentIds.Monitor.TABLE_ROOT]["children"]
    assert expected in json.dumps(alert), alert
    assert alert["props"]["color"] == color
    # An empty store, so a stale table cannot be acted on.
    assert body[AgentIds.Monitor.STORE_DISCOVERED]["data"] == []

    if logs:
      # The alert names no exception, so the log line is the only way to the
      # cause. It is caught and logged, not raised, so the gate has to see it.
      assert any("seeded failure" in m for m in callback_errors.messages)
      callback_errors.clear()
    else:
      callback_errors.assert_none()


def test_monitoring_a_discovered_agent_writes_the_row_and_redirects(
    dash_client, callback_errors, db_session
):
  """Clicking Monitor has to onboard the agent the user clicked.

  Every Monitor button shares one id pattern, so which agent to onboard comes
  out of ``ctx.triggered``, not out of the click list. Two rows go in with the
  second one clicked, so reading the list instead would onboard the first.
  ``onboard_gcp_agent`` also normalizes the location, which is what the local
  row is later looked up by.

  Nothing is patched here. ``onboard_gcp_agent`` only writes the local row, so
  this runs the real dependency chain without reaching Google Cloud.
  """
  discovered = AgentBase(
      name="Region Analyst",
      config=AgentConfig(
          project_id="proj-a",
          location="US",
          agent_resource_id="region-analyst",
          datasource=BigQueryConfig(tables=["proj-a.sales.regions"]),
          system_instruction="Not persisted locally.",
      ),
  )

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{REDIRECT_HANDLER}.pathname")
  buttons = dep["inputs"][0]
  loading = next(
      o
      for o in dash_http.outputs_grouping(dep["output"])
      if isinstance(o["id"], dict)
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(buttons): [(0, None), (1, 1)],
          f"{AgentIds.Monitor.STORE_DISCOVERED}.data": [
              _BQ_AGENT.model_dump(),
              discovered.model_dump(),
          ],
      },
      changed=[dash_http.pattern_address(buttons, 1)],
      rendered={dash_http.address(loading): [0, 1]},
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  db_session.expire_all()
  written = db_session.query(Agent).filter_by(name="Region Analyst").one()
  assert written.project_id == "proj-a"
  assert written.agent_resource_id == "region-analyst"
  # Onboarding lowercases it, so the row matches what discovery returns next
  # time and the agent is filtered out of the results as already monitored.
  assert written.location == "us"
  assert written.datasource_config == {"tables": ["proj-a.sales.regions"]}

  body = dash_http.body(response)["response"]
  assert body[REDIRECT_HANDLER]["pathname"] == f"/agents/view/{written.id}"
  # Both buttons stop spinning, not just the one that was clicked.
  loading_states = [v["loading"] for k, v in body.items() if k.startswith("{")]
  assert loading_states == [False, False], body


def test_the_project_select_offers_the_configured_projects(
    dash_client, callback_errors, monkeypatch
):
  """A discovery page with no projects in the select has a dead button.

  The page-load sweep fires this on every route but only checks the status
  code, so an empty options list passes it. The guard on the pathname is here
  too: the options are loaded on one route and the callback sees every
  navigation.
  """
  _use_agents(monkeypatch, _FakeAgents(projects=["proj-a", "proj-b"]))

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Monitor.INPUT_PROJECT}.data")

  response = dash_http.fire_url(dash_client, dep, _DISCOVERY_PATH)
  assert response.status_code == 200, response.data[:2000]
  options = dash_http.body(response)["response"][
      AgentIds.Monitor.INPUT_PROJECT
  ]["data"]
  assert options == [
      {"label": "proj-a", "value": "proj-a"},
      {"label": "proj-b", "value": "proj-b"},
  ]

  elsewhere = dash_http.fire_url(dash_client, dep, "/evaluations")
  assert dash_http.body(elsewhere)["response"] == {}

  callback_errors.assert_none()


@pytest.mark.parametrize(
    "global_project,expected",
    [
        ("proj-b", "proj-b"),
        ("proj-elsewhere", "proj-a"),
        (None, "proj-a"),
    ],
)
def test_the_project_select_preselects_the_global_project(
    dash_client, callback_errors, global_project, expected
):
  """The select starts on the project the rest of the app is using.

  Falling back to the first option matters because the global store holds
  whatever ADC resolved, which need not be a configured GDA project. Leaving
  the select empty there is a dead Discover button.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Monitor.INPUT_PROJECT}.value")

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{AgentIds.Monitor.INPUT_PROJECT}.data": [
              {"label": "proj-a", "value": "proj-a"},
              {"label": "proj-b", "value": "proj-b"},
          ],
          f"{GLOBAL_PROJECT_ID_STORE}.data": global_project,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  value = dash_http.body(response)["response"][AgentIds.Monitor.INPUT_PROJECT][
      "value"
  ]
  assert value == expected


_TRACE = [
    {
        "timestamp": "2024-05-01T10:00:00Z",
        "system_message": {
            "text": {"parts": ["Working on it"], "text_type": "THOUGHT"}
        },
    },
    {
        "timestamp": "2024-05-01T10:00:02Z",
        "system_message": {"data": {"generated_sql": "SELECT COUNT(*)"}},
    },
]


@pytest.fixture(name="trace_trial")
def _trace_trial(db_session, seeded):
  """The seeded run's trials, with a trace and a duration on the first one.

  ``seeded`` leaves every trial without timings, and ``duration_ms`` is
  derived from ``started_at`` and ``completed_at``, so the trace page has
  nothing to render until they are set here. Worth hoisting into
  ``tests/ui/conftest.py`` if another file needs a real trace.
  """
  trials = (
      db_session.query(Trial)
      .filter_by(run_id=seeded.run_id)
      .order_by(Trial.id)
      .all()
  )
  started = datetime.datetime(
      2024, 5, 1, 10, 0, 0, tzinfo=datetime.timezone.utc
  )
  traced, bare = trials[2], trials[0]
  traced.status = RunStatus.COMPLETED
  traced.started_at = started
  traced.completed_at = started + datetime.timedelta(milliseconds=2400)
  traced.trace_results = _TRACE
  bare.status = RunStatus.FAILED
  bare.started_at = started
  bare.completed_at = started + datetime.timedelta(milliseconds=500)
  db_session.commit()
  return traced.id, bare.id


def test_the_trace_page_header_names_the_trial_and_its_outcome(
    dash_client, callback_errors, seeded, trace_trial
):
  """The trace page is reached from a link, so the header is the only context.

  Title, breadcrumbs back to the run and the trial, the pass or fail badge
  with its colour, and the duration. All seven outputs come out of one
  callback, and returning them in the wrong order puts the alert in the
  breadcrumb bar.
  """
  traced_id, failed_id = trace_trial
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.AGENT_TRACE_TITLE}.children")

  # The header reads its label off the shared status map, so a completed
  # trial says "Completed", not "Success". It used to map COMPLETED to
  # "Success" and everything else to "Failed", which named a cancelled trial
  # a failure.
  for trial_id, label, color in (
      (traced_id, "Completed", "green"),
      (failed_id, "Failed", "red"),
  ):
    response = dash_http.fire_url(
        dash_client, dep, f"/evaluations/trials/{trial_id}/trace"
    )
    assert response.status_code == 200, response.data[:2000]

    body = dash_http.body(response)["response"]
    assert (
        body[EvaluationIds.AGENT_TRACE_TITLE]["children"]
        == f"Agent Trace for Trial #{trial_id}"
    )
    assert body[EvaluationIds.AGENT_TRACE_STATUS]["children"] == label
    assert body[EvaluationIds.AGENT_TRACE_STATUS]["color"] == color

    crumbs = json.dumps(
        body[EvaluationIds.AGENT_TRACE_BREADCRUMBS_CONTAINER]["children"]
    )
    assert "Evaluations" in crumbs
    assert f"Run #{seeded.run_id}" in crumbs
    assert f"Trial #{trial_id}" in crumbs
    assert "Trace" in crumbs

  callback_errors.assert_none()


def test_a_trial_with_no_trace_says_so_and_a_real_one_renders_its_groups(
    dash_client, callback_errors, trace_trial
):
  """The timeline has to be readable, and empty has to look empty.

  A trial with no trace produces a Timeline with no groups, which must render
  as a sentence rather than an empty card. A trial with one renders group
  headers, and those carry a wall-clock time and the group's share of the run.
  The share is a progress bar width, so over 100 silently overflows the card.
  """
  traced_id, bare_id = trace_trial
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.AGENT_TRACE_TITLE}.children")

  empty = dash_http.body(
      dash_http.fire_url(
          dash_client, dep, f"/evaluations/trials/{bare_id}/trace"
      )
  )["response"]
  assert "No trace data available." in json.dumps(
      empty[EvaluationIds.AGENT_TRACE_CONTAINER]["children"]
  )

  body = dash_http.body(
      dash_http.fire_url(
          dash_client, dep, f"/evaluations/trials/{traced_id}/trace"
      )
  )["response"]
  timeline = json.dumps(body[EvaluationIds.AGENT_TRACE_CONTAINER]["children"])
  assert "No trace data available." not in timeline
  assert "SELECT COUNT(*)" in timeline
  # 2400ms of wall clock, rendered next to the title.
  assert "2.4s" in timeline

  # A local wall-clock time, not the ISO string off the trace event.
  assert re.search(r"\d{2}:\d{2}:\d{2}\.\d{3}", timeline), timeline
  assert "2024-05-01T10:00:00Z" not in timeline

  percentages = [float(p) for p in re.findall(r'"(\d+\.\d)%"', timeline)]
  assert percentages, timeline
  assert all(0 <= p <= 100 for p in percentages), percentages

  callback_errors.assert_none()


def test_downloading_a_trace_names_the_file_after_the_trial(
    dash_client, callback_errors, trace_trial
):
  """A folder of ``trace_.json`` files is no use.

  The trial id comes off the pathname, not off the store, which holds the
  trace alone. The split is unguarded, so the test below pins the precondition
  it rests on: no route but the trace page renders the button.
  """
  traced_id, _ = trace_trial
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(
      deps, f"{EvaluationIds.AGENT_TRACE_DOWNLOAD_COMPONENT}.data"
  )

  address = f"{EvaluationIds.AGENT_TRACE_DOWNLOAD_BTN}.n_clicks"
  response = dash_http.fire(
      dash_client,
      dep,
      {
          address: 1,
          f"{EvaluationIds.AGENT_TRACE_RAW_STORE}.data": '[{"a": 1}]',
          "url.pathname": f"/evaluations/trials/{traced_id}/trace",
      },
      changed=[address],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  data = dash_http.body(response)["response"][
      EvaluationIds.AGENT_TRACE_DOWNLOAD_COMPONENT
  ]["data"]
  assert data == {
      "content": '[{"a": 1}]',
      "filename": f"trace_{traced_id}.json",
  }


@pytest.mark.parametrize(
    "pathname", ["/", "/evaluations", "/evaluations/trials/7"]
)
def test_the_download_button_is_built_on_no_route_but_the_trace_page(
    dash_client, callback_errors, pathname
):
  """``download_trace`` splits the path with no fallback, and needs none.

  ``(pathname or "").split("/")[-2]`` raises IndexError on a path with one
  segment and names the file after the wrong one on a path that does not end
  in /trace. Neither is reachable, because the actions slot holding the button
  is written by ``render_agent_trace``, which returns seven no_updates for any
  path but its own. An empty response body is the button never being built.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.AGENT_TRACE_ACTIONS}.children")

  response = dash_http.fire_url(dash_client, dep, pathname)

  assert response.status_code in (200, 204), response.data[:2000]
  assert dash_http.body(response).get("response", {}) == {}
  callback_errors.assert_none()
