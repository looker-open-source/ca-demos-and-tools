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

"""The two agent onboarding forms, driven over Dash's HTTP route.

Prism onboards an agent two ways. "Monitor existing" lists what is already on
GDA and adds a local row for the one you pick. "Create" builds the agent on
GDA from a form and then adds the row. Neither path had a test at any tier, and
both of them write the config every later run depends on.

Every callback here that would reach GDA has ``get_client`` patched in its own
module. ``tests/ui`` runs with ``PRISM_AGENT_BACKEND`` unset, which is live, so
an unpatched ``discover_gcp_agents`` or ``register_gcp_agent`` is a real call
against a real project.
"""

from __future__ import annotations
import datetime
from typing import Any
from unittest import mock
from prism.client import agent_client
from prism.common.schemas import agent as agent_schemas
from prism.server.models.agent import Agent as AgentRow
from prism.ui.callbacks import agent_add_callbacks
from prism.ui.callbacks import agent_monitor_callbacks
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.pages.agent_ids import AgentIds
import pytest
from tests.ui import dash_http

_PROJECT = "a-project"
_LOCATION = "us-central1"

# Placeholders. Nothing here is a credential, and nothing reaches Looker.
_CLIENT_ID = "an-id"
_CLIENT_SECRET = "a-secret"


def _server_dep(deps: list[dict[str, Any]], component_id: str):
  """The one server-side callback listening to ``component_id``.

  ``dash_http.find`` keys on the output, which does not tell the several
  callbacks writing ``redirect-handler`` apart, and each loading overlay has a
  clientside twin writing the same property.
  """
  matches = [
      dep
      for dep in deps
      if dep.get("clientside_function") is None
      and any(component_id in str(i["id"]) for i in dep["inputs"])
  ]
  assert (
      len(matches) == 1
  ), f"expected one server callback on {component_id}, found {len(matches)}"
  return matches[0]


def _discovered(
    name: str,
    resource_id: str,
    datasource: Any = None,
    instruction: str | None = None,
) -> agent_schemas.AgentBase:
  """One agent as ``discover_gcp_agents`` returns it."""
  return agent_schemas.AgentBase(
      name=name,
      config=agent_schemas.AgentConfig(
          project_id=_PROJECT,
          location=_LOCATION,
          agent_resource_id=resource_id,
          datasource=datasource,
          system_instruction=instruction,
      ),
  )


def _monitored(resource_id: str) -> agent_schemas.Agent:
  """One local row, as ``list_agents`` returns it."""
  return agent_schemas.Agent(
      id=1,
      name="Already Watched",
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      config=agent_schemas.AgentConfig(
          project_id=_PROJECT,
          location=_LOCATION,
          agent_resource_id=resource_id,
      ),
  )


@pytest.fixture(name="monitor_client")
def _monitor_client(monkeypatch):
  """Stands in for ``get_client()`` in the monitor page's callbacks."""
  client = mock.MagicMock()
  monkeypatch.setattr(agent_monitor_callbacks, "get_client", lambda: client)
  return client.agents


@pytest.fixture(name="add_client")
def _add_client(monkeypatch):
  """Stands in for ``get_client()`` in the add page's callbacks."""
  client = mock.MagicMock()
  monkeypatch.setattr(agent_add_callbacks, "get_client", lambda: client)
  return client.agents


def _discover(dash_client, project: str | None = _PROJECT):
  """Fires ``perform_discovery`` as the fetch button's trigger would."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Monitor.STORE_DISCOVERED}.data")
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{AgentIds.Monitor.STORE_FETCH_TRIGGER}.data": True,
          f"{AgentIds.Monitor.INPUT_PROJECT}.value": project,
      },
  )


def test_discovery_lists_only_the_agents_that_are_not_monitored_yet(
    dash_client, callback_errors, monitor_client
):
  """A monitored agent must not be offered again.

  Onboarding the same GDA agent twice gives two local rows pointing at one
  remote agent, and every list page then shows both. The key is the triple
  (project, location, resource id), because the display name is not unique and
  is editable locally.
  """
  monitor_client.discover_gcp_agents.return_value = [
      _discovered(
          "Already Watched",
          "res-old",
          agent_schemas.BigQueryConfig(tables=["p.d.t"]),
      ),
      _discovered(
          "Newly Found",
          "res-new",
          agent_schemas.LookerConfig(
              instance_uri="https://looker.example.com",
              explores=["model.explore"],
          ),
          instruction="Answer questions about orders.",
      ),
  ]
  monitor_client.list_agents.return_value = [_monitored("res-old")]

  response = _discover(dash_client)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  monitor_client.discover_gcp_agents.assert_called_once_with(
      project_id=_PROJECT
  )

  body = dash_http.body(response)["response"]
  table = str(body[AgentIds.Monitor.TABLE_ROOT]["children"])
  assert "Newly Found" in table
  assert "Already Watched" not in table
  # The label the row shows, not the config key it came from.
  assert "Looker" in table
  assert "Answer questions about orders." in table

  stored = body[AgentIds.Monitor.STORE_DISCOVERED]["data"]
  assert len(stored) == 1
  assert stored[0]["config"]["agent_resource_id"] == "res-new"


@pytest.mark.parametrize(
    "case,expected",
    [
        ("empty", "No agents found in this project."),
        ("all monitored", "All agents in this project are already monitored."),
        ("fetch failed", "Could not list the agents in this project."),
    ],
)
def test_discovery_says_why_it_has_no_table_to_show(
    dash_client, callback_errors, monitor_client, case, expected
):
  """Three different nothings, and the user has to be able to tell them apart.

  All three clear the store as well. Leaving the previous project's payload
  there would let a Monitor click onboard an agent the table no longer shows.
  """
  monitored = _discovered(
      "Already Watched",
      "res-old",
      agent_schemas.BigQueryConfig(tables=["p.d.t"]),
  )
  if case == "empty":
    monitor_client.discover_gcp_agents.return_value = []
  elif case == "all monitored":
    monitor_client.discover_gcp_agents.return_value = [monitored]
    monitor_client.list_agents.return_value = [_monitored("res-old")]
  else:
    monitor_client.discover_gcp_agents.side_effect = RuntimeError(
        "403 on projects/a-project/locations/us-central1/dataAgents"
    )

  response = _discover(dash_client)

  assert response.status_code == 200, response.data[:2000]

  body = dash_http.body(response)["response"]
  rendered = str(body[AgentIds.Monitor.TABLE_ROOT]["children"])
  assert expected in rendered, rendered[:1000]
  assert body[AgentIds.Monitor.STORE_DISCOVERED]["data"] == []
  # The GDA error carries the resource name it was building. That is a server
  # log line, not page content.
  assert "403 on projects" not in rendered

  if case == "fetch failed":
    assert any("403 on projects" in m for m in callback_errors.messages)
    callback_errors.clear()


def test_discovery_does_nothing_without_a_project(
    dash_client, callback_errors, monitor_client
):
  """The project Select is a State, so it can still be empty when this fires."""
  response = _discover(dash_client, project=None)

  assert response.status_code == 200, response.data[:500]
  # Dash answers 200 with nothing in it for a callback whose every output is
  # no_update, not 204. 204 is PreventUpdate.
  assert dash_http.body(response)["response"] == {}
  callback_errors.assert_none()
  assert not monitor_client.discover_gcp_agents.called


def _monitor_row(dash_client, store: list[dict[str, Any]], index: str):
  """Clicks the Monitor button on row ``index`` of a rendered table."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{REDIRECT_HANDLER}.pathname")
  buttons = dep["inputs"][0]
  loading = dash_http.outputs_grouping(dep["output"])[1]
  indices = [str(i) for i in range(len(store))]

  return dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(buttons): [
              (i, 1 if i == index else None) for i in indices
          ],
          f"{AgentIds.Monitor.STORE_DISCOVERED}.data": store,
      },
      changed=[dash_http.pattern_address(buttons, index)],
      rendered={dash_http.address(loading): indices},
  )


def test_monitoring_a_row_onboards_that_agent_and_redirects(
    dash_client, callback_errors, db_session, monitor_client
):
  """The row that was clicked is the row that gets onboarded.

  Every Monitor button shares one ALL input, so the callback has to read the
  index out of ``ctx.triggered``. Reading the list instead would onboard the
  first row whichever button was pressed. Two rows go in here and the second
  one is clicked, so that mistake writes the wrong agent.

  ``onboard_gcp_agent`` is the one call left real: it writes the local row and
  never touches GDA, and the row is what the click is for.
  """
  monitor_client.onboard_gcp_agent.side_effect = (
      agent_client.AgentsClient().onboard_gcp_agent
  )
  store = [
      _discovered("First Found", "res-first").model_dump(),
      _discovered(
          "Second Found",
          "res-second",
          agent_schemas.BigQueryConfig(tables=["p.d.t"]),
      ).model_dump(),
  ]

  response = _monitor_row(dash_client, store, "1")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  config = monitor_client.onboard_gcp_agent.call_args.kwargs["config"]
  assert config.agent_resource_id == "res-second"

  db_session.expire_all()
  written = (
      db_session.query(AgentRow).filter_by(agent_resource_id="res-second").one()
  )
  assert written.name == "Second Found"

  body = dash_http.body(response)["response"]
  assert body[REDIRECT_HANDLER]["pathname"] == f"/agents/view/{written.id}"
  # One value per button, or Dash drops the update. Both clear, because the
  # page navigates away and the row that spun is gone either way.
  spinners = [
      v["loading"] for k, v in body.items() if "agent-monitor-btn-add" in k
  ]
  assert spinners == [False, False], spinners


def test_a_failed_onboard_stops_the_button_spinning(
    dash_client, callback_errors, monitor_client
):
  """The spinner is only cleared by this callback returning.

  The clientside twin sets it on the click and never unsets it, so a failure
  that returned no_update here would leave the row spinning for good.
  """
  monitor_client.onboard_gcp_agent.side_effect = RuntimeError("boom")
  store = [_discovered("First Found", "res-first").model_dump()]

  response = _monitor_row(dash_client, store, "0")

  assert response.status_code == 200, response.data[:2000]
  assert any("boom" in m for m in callback_errors.messages)
  callback_errors.clear()

  body = dash_http.body(response)["response"]
  assert REDIRECT_HANDLER not in body
  spinners = [
      v["loading"] for k, v in body.items() if "agent-monitor-btn-add" in k
  ]
  assert spinners == [False]


def _submit_add(dash_client, **values):
  """Fires the Create Agent form with ``values`` filled in."""
  deps = dash_http.dependencies(dash_client)
  dep = _server_dep(deps, AgentIds.Add.BTN_SUBMIT)
  payload = {f"{AgentIds.Add.BTN_SUBMIT}.n_clicks": 1}
  payload.update(values)
  return dash_http.fire(
      dash_client,
      dep,
      payload,
      changed=[f"{AgentIds.Add.BTN_SUBMIT}.n_clicks"],
  )


def _looker_form() -> dict[str, Any]:
  """A complete Looker form, ready to submit."""
  return {
      f"{AgentIds.Form.INPUT_NAME}.value": "A Looker Agent",
      f"{AgentIds.Form.INPUT_PROJECT}.value": _PROJECT,
      f"{AgentIds.Form.TEXTAREA_INSTRUCTION}.value": "an instruction",
      f"{AgentIds.Form.SELECT_DATASOURCE_TYPE}.value": "looker",
      f"{AgentIds.Form.INPUT_LOOKER_URI}.value": "https://looker.example.com",
      f"{AgentIds.Form.INPUT_LOOKER_EXPLORES}.value": (
          "model.orders\nmodel.users"
      ),
      f"{AgentIds.Form.INPUT_LOOKER_CLIENT_ID}.value": _CLIENT_ID,
      f"{AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET}.value": _CLIENT_SECRET,
  }


def test_the_looker_branch_sends_the_credentials_and_the_explores(
    dash_client, callback_errors, add_client
):
  """A Looker agent created without its credentials cannot run anything.

  The form is the only place they are entered, and they travel on the
  AgentConfig, not on the LookerConfig, so a refactor that rebuilt the
  datasource would drop them and the failure would not show until the first
  run. The explores come off a textarea, one per line.
  """
  add_client.register_gcp_agent.return_value = agent_schemas.Agent(
      id=42,
      name="A Looker Agent",
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
  )

  response = _submit_add(dash_client, **_looker_form())

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  config = add_client.register_gcp_agent.call_args.kwargs["config"]
  assert isinstance(config.datasource, agent_schemas.LookerConfig)
  assert config.datasource.instance_uri == "https://looker.example.com"
  assert config.datasource.explores == ["model.orders", "model.users"]
  assert config.looker_client_id == _CLIENT_ID
  assert config.looker_client_secret == _CLIENT_SECRET
  assert config.project_id == _PROJECT
  # GCP allocates the resource id, so the form must not invent one.
  assert not config.agent_resource_id

  body = dash_http.body(response)["response"]
  assert body[REDIRECT_HANDLER]["href"] == "/agents/view/42"
  assert body[AgentIds.Add.LOADING_OVERLAY]["visible"] is False


@pytest.mark.parametrize(
    "changes,expected",
    [
        (
            {
                f"{AgentIds.Form.INPUT_NAME}.value": "",
                f"{AgentIds.Form.INPUT_PROJECT}.value": "",
                f"{AgentIds.Form.SELECT_DATASOURCE_TYPE}.value": "bigquery",
            },
            ["Agent Name", "GCP Project ID", "BigQuery Tables"],
        ),
        (
            {
                f"{AgentIds.Form.INPUT_LOOKER_URI}.value": "",
                f"{AgentIds.Form.INPUT_LOOKER_EXPLORES}.value": "",
                f"{AgentIds.Form.INPUT_LOOKER_CLIENT_ID}.value": "",
                f"{AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET}.value": "",
            },
            [
                "Looker Instance URI",
                "Looker Explores",
                "Looker Client ID",
                "Looker Client Secret",
            ],
        ),
        (
            {f"{AgentIds.Form.INPUT_LOOKER_EXPLORES}.value": "orders"},
            ["Invalid Looker Explore: orders"],
        ),
        (
            {
                f"{AgentIds.Form.SELECT_DATASOURCE_TYPE}.value": "bigquery",
                f"{AgentIds.Form.INPUT_BQ_TABLES}.value": "dataset.table",
            },
            ["Invalid BQ Table: dataset.table"],
        ),
    ],
)
def test_an_incomplete_form_names_every_missing_field(
    dash_client, callback_errors, add_client, changes, expected
):
  """One submit has to report every problem, not the first one.

  The form is long enough that fixing one field at a time is several round
  trips, and each of them creates nothing on GDA but does clear the page.
  """
  values = _looker_form()
  values.update(changes)

  response = _submit_add(dash_client, **values)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert not add_client.register_gcp_agent.called

  body = dash_http.body(response)["response"]
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  # NotificationContainer takes a list of actions and silently drops a bare
  # dict, so the toast only appears if this is a list.
  assert isinstance(notifications, list), notifications
  assert notifications[0]["title"] == "Validation Error"
  message = notifications[0]["message"]
  for field in expected:
    assert field in message, message

  assert REDIRECT_HANDLER not in body
  assert body[AgentIds.Add.LOADING_OVERLAY]["visible"] is False


def test_a_rejected_create_says_so_and_stays_on_the_form(
    dash_client, callback_errors, add_client
):
  """A rejected create has to leave the typed form on screen and reachable.

  ``add_agent`` catches its own exception, so none of the ``handle_errors``
  toast tests cover this return. Without the overlay cleared the page is left
  dimmed and unusable, and without autoClose False the one explanation of what
  happened disappears while the user is still reading the form.
  """
  add_client.register_gcp_agent.side_effect = RuntimeError(
      "409 already exists: projects/a-project/locations/global/dataAgents/x"
  )

  response = _submit_add(dash_client, **_looker_form())

  assert response.status_code == 200, response.data[:2000]
  # The callback logs the rejection itself. Consume that, then require nothing
  # else: a second error would mean handle_errors also had to step in.
  callback_errors.assert_logged("Failed to create agent")
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  notification = body[NOTIFICATION_CONTAINER]["sendNotifications"][0]
  assert notification["title"] == "Submission Error"
  assert notification["autoClose"] is False
  # Not the exception text: it carries the resource name it was building.
  assert "409 already exists" not in notification["message"]

  assert REDIRECT_HANDLER not in body
  assert body[AgentIds.Add.LOADING_OVERLAY]["visible"] is False


@pytest.mark.parametrize(
    "datasource_type,bq,looker",
    [
        ("looker", "none", "block"),
        ("bigquery", "block", "none"),
    ],
)
def test_the_datasource_control_swaps_the_two_config_blocks(
    dash_client, callback_errors, datasource_type, bq, looker
):
  """Both blocks are always in the layout, and only the style hides one.

  Show both and the submit reads whichever fields the user filled in last.
  Show neither and the page has no datasource fields at all.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{AgentIds.Add.CONTAINER_BQ_DATASOURCE}.style")

  response = dash_http.fire(
      dash_client,
      dep,
      {f"{AgentIds.Form.SELECT_DATASOURCE_TYPE}.value": datasource_type},
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[AgentIds.Add.CONTAINER_BQ_DATASOURCE]["style"] == {"display": bq}
  assert body[AgentIds.Add.CONTAINER_LOOKER_DATASOURCE]["style"] == {
      "display": looker
  }


_PROJECT_SELECTS = [AgentIds.Form.INPUT_PROJECT, AgentIds.Monitor.INPUT_PROJECT]


@pytest.mark.parametrize("select_id", _PROJECT_SELECTS)
@pytest.mark.parametrize(
    "session_project,expected",
    [
        ("second-project", "second-project"),
        ("a-project-nobody-configured", "first-project"),
        (None, "first-project"),
    ],
)
def test_the_session_project_wins_over_the_first_option(
    dash_client, callback_errors, select_id, session_project, expected
):
  """The project picked in the shell has to survive opening a form.

  Both onboarding forms carry their own copy of this callback, and the shell
  writes the choice to one store that both read. Falling back to the first
  option is for the first visit, and for a stored project that is no longer
  configured, where preselecting it would create the agent somewhere the user
  cannot see it.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{select_id}.value")
  options = [
      {"label": "first-project", "value": "first-project"},
      {"label": "second-project", "value": "second-project"},
  ]

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{select_id}.data": options,
          f"{GLOBAL_PROJECT_ID_STORE}.data": session_project,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert dash_http.body(response)["response"][select_id]["value"] == expected


@pytest.mark.parametrize("select_id", _PROJECT_SELECTS)
def test_no_configured_projects_leaves_the_select_alone(
    dash_client, callback_errors, select_id
):
  """An empty option list has no first entry to fall back on.

  This is what the page does with PRISM_GDA_PROJECTS unset. Indexing the
  options blind would be an IndexError inside a page-load callback.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{select_id}.value")

  response = dash_http.fire(
      dash_client,
      dep,
      {f"{select_id}.data": [], f"{GLOBAL_PROJECT_ID_STORE}.data": "anything"},
  )

  assert response.status_code == 200, response.data[:500]
  assert dash_http.body(response)["response"] == {}
  callback_errors.assert_none()


@pytest.mark.parametrize(
    "case,message,color",
    [
        ("incomplete", "Incomplete credentials", "orange"),
        ("pass", "Connected.", "green"),
        ("fail", "Invalid credentials.", "red"),
        ("raised", "Could not reach the Looker instance.", "red"),
    ],
)
def test_the_looker_test_button_reports_what_the_service_said(
    dash_client, callback_errors, add_client, case, message, color
):
  """Green means the credentials work, and nothing else may read as green.

  The colour is the whole answer here: the user is about to save an agent
  whose every trial calls a paid API with these credentials. The raised case
  must not quote the exception: it carries the instance URI.
  """
  values = {
      f"{AgentIds.Form.BTN_TEST_LOOKER}.n_clicks": 1,
      f"{AgentIds.Form.INPUT_LOOKER_URI}.value": "https://looker.example.com",
      f"{AgentIds.Form.INPUT_LOOKER_CLIENT_ID}.value": _CLIENT_ID,
      f"{AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET}.value": _CLIENT_SECRET,
  }
  if case == "incomplete":
    values[f"{AgentIds.Form.INPUT_LOOKER_CLIENT_SECRET}.value"] = ""
  elif case == "pass":
    add_client.test_looker_credentials.return_value = {
        "success": True,
        "message": "Connected.",
    }
  elif case == "fail":
    add_client.test_looker_credentials.return_value = {
        "success": False,
        "message": "Invalid credentials.",
    }
  else:
    add_client.test_looker_credentials.side_effect = RuntimeError("boom")

  deps = dash_http.dependencies(dash_client)
  dep = _server_dep(deps, AgentIds.Form.BTN_TEST_LOOKER)
  response = dash_http.fire(
      dash_client,
      dep,
      values,
      changed=[f"{AgentIds.Form.BTN_TEST_LOOKER}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  if case == "raised":
    # The callback logs the exception itself. Consuming that record and
    # leaving the gate empty is what proves handle_errors did not have to step
    # in on top of it.
    callback_errors.assert_logged("Looker connection test failed")
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  alert = body[AgentIds.Form.ALERT_LOOKER_TEST]
  assert message in str(alert["children"])
  assert alert["color"] == color
  assert alert["hide"] is False
  # The spinner is Dash's running= now, so it is not in the response body.
  assert AgentIds.Form.BTN_TEST_LOOKER not in body
  assert "boom" not in str(alert["children"])

  if case == "incomplete":
    assert not add_client.test_looker_credentials.called


@pytest.mark.parametrize(
    "field_id,preview_id,good,bad",
    [
        (
            AgentIds.Form.INPUT_BQ_TABLES,
            AgentIds.Form.INPUT_BQ_TABLES_PREVIEW,
            "proj.dataset.table",
            "dataset.table",
        ),
        (
            AgentIds.Form.INPUT_LOOKER_EXPLORES,
            AgentIds.Form.INPUT_LOOKER_EXPLORES_PREVIEW,
            "model.orders",
            "orders",
        ),
    ],
)
def test_the_path_preview_badges_the_line_that_is_wrong(
    dash_client, callback_errors, field_id, preview_id, good, bad
):
  """One badge per line, and the bad one is red and named in the error.

  This is advisory: the submit validator is what refuses the form. It still
  has to name the offending line, because the textarea holds many and the
  submit toast is the only other place the user finds out.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{preview_id}.children")

  response = dash_http.fire(
      dash_client, dep, {f"{field_id}.value": f"{good}\n{bad}"}
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  badges = body[preview_id]["children"]
  assert [b["props"]["children"] for b in badges] == [good, bad]
  assert [b["props"]["color"] for b in badges] == ["blue", "red"]
  assert bad in body[field_id]["error"]

  # Emptying the field clears both, or the last bad path stays on screen
  # under an empty textarea.
  cleared = dash_http.body(
      dash_http.fire(dash_client, dep, {f"{field_id}.value": ""})
  )["response"]
  assert cleared[preview_id]["children"] == []
  assert cleared[field_id]["error"] is False
