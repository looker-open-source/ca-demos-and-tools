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

"""The agent detail page, driven over Dash's HTTP route.

The page is built in two passes. ``update_agent_details`` renders everything
that comes out of the local database and sets a trigger Store.
``fetch_remote_config`` picks the trigger up and fills in what has to come from
GDA. Everything else on the page hangs off one of the two modals.

Anything that reaches GDA has ``get_client`` patched in
``agent_detail_callbacks``. ``tests/ui`` runs with ``PRISM_AGENT_BACKEND``
unset, which is live, so an unpatched ``get_gcp_agent_details``,
``update_agent``, ``duplicate_agent``, ``create_run``,
``test_looker_credentials`` or ``format_golden_queries_with_ai`` is a real call
against a real project. ``get_agent``, ``list_suites``, ``get_suite``,
``get_agent_dashboard_stats``, ``archive_agent`` and ``unarchive_agent`` are
local, so the tests that want the real wiring leave those unpatched.

The Looker secret is covered by ``tests/ui/test_agent_edit_secret.py``, which
calls the callbacks directly. What is added here is the same guarantee over the
wire, where the response body is the thing the browser receives.
"""

from __future__ import annotations
import datetime
import json
import logging
from typing import Any
from unittest import mock
from prism.common.schemas import agent as agent_schemas
from prism.common.schemas import assertion as assertion_schemas
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.ui.callbacks import agent_detail_callbacks
from prism.ui.constants import CP
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.pages.agent_ids import AgentIds
import pytest
from sqlalchemy import orm
from tests.ui import dash_http

_DETAIL = AgentIds.Detail
_EVAL_MODAL = AgentIds.Detail.EvalModal

_URI = "https://looker.example.com"

# Placeholders. Nothing here is a credential, and nothing reaches Looker.
_CLIENT_ID = "an-id"
_CLIENT_SECRET = "a-secret"

_GOLDEN_QUERY = {
    "natural_language_questions": ["How many orders were there?"],
    "looker_query": {"model": "a_model", "explore": "orders"},
}


def _dep_on(deps: list[dict[str, Any]], *addresses: str) -> dict[str, Any]:
  """The one server-side callback taking all of ``addresses`` as inputs.

  ``dash_http.find`` keys on the output, and half of this page's outputs are
  declared ``allow_duplicate=True``: two callbacks open the edit modal, two
  write ``redirect-handler``, two write the refresh trigger. Each loading
  overlay also has a clientside twin writing the same property, hence the
  filter.
  """
  wanted = set(addresses)
  matches = [
      dep
      for dep in deps
      if dep.get("clientside_function") is None
      and wanted <= {dash_http.address(i) for i in dep["inputs"]}
  ]
  assert (
      len(matches) == 1
  ), f"expected one server callback on {wanted}, found {len(matches)}"
  return matches[0]


def _strings(node: Any) -> list[str]:
  """Every string leaf of a rendered component tree.

  Substring matching on ``str(children)`` says nothing about where the text
  landed, and "p" or "l" would match a style prop. This matches whole values.
  """
  if isinstance(node, str):
    return [node]
  if isinstance(node, list):
    return [s for item in node for s in _strings(item)]
  if isinstance(node, dict):
    return [s for value in node.values() for s in _strings(value)]
  return []


def _agent(
    agent_id: int = 7,
    datasource: Any = None,
    client_id: str | None = None,
    secret: str | None = None,
    golden_queries: Any = None,
) -> agent_schemas.Agent:
  """One registered agent, as ``get_agent`` returns it."""
  return agent_schemas.Agent(
      id=agent_id,
      name="Remote Agent",
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      config=agent_schemas.AgentConfig(
          project_id="a-project",
          location="us-central1",
          agent_resource_id="agent-7",
          system_instruction="an instruction",
          datasource=datasource,
          looker_client_id=client_id,
          looker_client_secret=secret,
          golden_queries=golden_queries,
      ),
  )


def _looker(explores: list[str] | None = None) -> agent_schemas.LookerConfig:
  return agent_schemas.LookerConfig(
      instance_uri=_URI, explores=explores or ["a_model.orders"]
  )


def _stored_looker_agent(
    db_session: orm.Session,
    client_id: str | None = None,
    secret: str | None = None,
    archived: bool = False,
) -> int:
  """Writes a real Looker agent row and returns its id."""
  repo = AgentRepository(db_session)
  agent = repo.create(
      name="Stored Looker Agent",
      config=agent_schemas.AgentConfig(
          project_id="a-project",
          location="us-central1",
          agent_resource_id="agent-stored",
          datasource=_looker(),
          looker_client_id=client_id,
          looker_client_secret=secret,
      ),
  )
  if archived:
    repo.archive(agent.id)
  return agent.id


@pytest.fixture(name="detail_client")
def _detail_client(monkeypatch):
  """Stands in for ``get_client()`` in the detail page's callbacks."""
  client = mock.MagicMock()
  monkeypatch.setattr(agent_detail_callbacks, "get_client", lambda: client)
  return client


def _fire_details(dash_client, agent_id: int):
  """Fires the local first pass for one agent."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{_DETAIL.CONTENT}.{CP.CHILDREN}")
  return dash_http.fire_url(dash_client, dep, f"/agents/view/{agent_id}")


def _fire_remote(dash_client, agent_id: int = 7):
  """Fires the remote second pass, as the trigger Store would."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{_DETAIL.STORE_GCP_CONFIG}.{CP.DATA}")
  return dash_http.fire(
      dash_client,
      dep,
      {f"{_DETAIL.STORE_REMOTE_TRIGGER}.{CP.DATA}": {"agent_id": agent_id}},
  )


def test_the_detail_page_renders_the_runs_that_exist(
    dash_client, callback_errors, seeded
):
  """An agent with runs gets both charts and the recent evaluations table.

  The page picks between this and a placeholder on ``recent_evals``, so the
  branch is only exercised by an agent that has actually been run. The local
  pass also has to hand the remote pass the agent id, or the second half of
  the page never loads.
  """
  response = _fire_details(dash_client, seeded.agent_id)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.TITLE][CP.CHILDREN] == seeded.agent_name
  assert body[AgentIds.Detail.LOADING]["visible"] is False
  assert body[_DETAIL.STORE_REMOTE_TRIGGER][CP.DATA]["agent_id"] == (
      seeded.agent_id
  )

  content = body[_DETAIL.CONTENT][CP.CHILDREN]
  text = _strings(content)
  # The metadata grid, labels and the values behind them.
  assert "GCP Parent Project" in text
  assert "GDA Resource ID" in text
  assert {"p", "l", "r"} <= set(text)

  rendered = str(content)
  assert "Evaluation Accuracies" in rendered
  assert "Recent Evaluations" in rendered
  assert seeded.suite_name in rendered
  assert f"/evaluations/runs/{seeded.run_id}" in rendered
  assert "Agent not yet evaluated" not in rendered


@pytest.mark.parametrize(
    "client_id,secret,warned",
    [
        (None, None, True),
        (_CLIENT_ID, None, True),
        (_CLIENT_ID, _CLIENT_SECRET, False),
    ],
)
def test_a_looker_agent_is_warned_when_its_credentials_are_incomplete(
    dash_client, callback_errors, db_session, client_id, secret, warned
):
  """Half a Looker credential is as useless as none, and has to read that way.

  Every trial in a run against a Looker agent fails without both halves, so
  the banner is the only warning before a run is started and burns the quota.
  """
  agent_id = _stored_looker_agent(
      db_session, client_id=client_id, secret=secret
  )

  response = _fire_details(dash_client, agent_id)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  text = _strings(body[_DETAIL.CONTENT][CP.CHILDREN])
  assert ("Missing Credentials" in text) is warned
  if warned:
    assert any("Evaluations will be disabled" in s for s in text)


@pytest.mark.parametrize(
    "case,label,color,disabled,fragment",
    [
        ("looker", "Looker", "blue", False, _URI),
        ("looker without credentials", "Looker", "blue", True, _URI),
        ("bq", "BQ", "orange", False, "a-project.a_dataset.a_table"),
        ("none", "None", "gray", False, "No datasource configured on GCP."),
    ],
)
def test_the_remote_config_renders_whichever_datasource_gda_has(
    dash_client,
    callback_errors,
    detail_client,
    case,
    label,
    color,
    disabled,
    fragment,
):
  """The badge, the datasource block and the Run Eval gate all read one config.

  The badge colour is how the page says which kind of agent this is, and the
  Run Eval button is disabled off the same pass. A Looker agent with no secret
  must come back disabled, and the secret must not come back at all: the
  config goes into a ``dcc.Store``, which is serialized into the page.
  """
  if case == "bq":
    datasource = agent_schemas.BigQueryConfig(
        tables=["a-project.a_dataset.a_table"]
    )
    agent = _agent(datasource=datasource)
  elif case == "none":
    agent = _agent(datasource=None)
  else:
    agent = _agent(
        datasource=_looker(),
        client_id=_CLIENT_ID,
        secret=None if disabled else _CLIENT_SECRET,
        golden_queries=[
            agent_schemas.LookerGoldenQuery.model_validate(_GOLDEN_QUERY)
        ],
    )
  detail_client.agents.get_gcp_agent_details.return_value = agent

  response = _fire_remote(dash_client)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  badge = body[_DETAIL.BADGE_DATASOURCE][CP.CHILDREN]["props"]
  assert badge[CP.CHILDREN] == label
  assert badge[CP.COLOR] == color

  assert body[_DETAIL.BTN_EDIT][CP.DISABLED] is False
  assert body[_DETAIL.BTN_DUPLICATE][CP.DISABLED] is False
  assert body[_DETAIL.BTN_RUN_EVAL][CP.DISABLED] is disabled

  assert fragment in str(body[_DETAIL.CONTAINER_DATASOURCE][CP.CHILDREN])
  assert "an instruction" in str(body[_DETAIL.INSTRUCTION][CP.CHILDREN])

  golden = str(body[_DETAIL.CARD_GOLDEN_QUERIES][CP.CHILDREN])
  if case.startswith("looker"):
    assert "How many orders were there?" in golden
    assert "looker_query" in golden
  else:
    assert "No golden queries configured." in golden

  stored = body[_DETAIL.STORE_GCP_CONFIG][CP.DATA]
  assert "looker_client_secret" not in stored
  assert _CLIENT_SECRET not in response.data.decode()


@pytest.mark.parametrize(
    "case,expected",
    [
        ("raised", "Could not load the agent's configuration from GDA."),
        ("not found", "Error: Agent not found on GCP."),
    ],
)
def test_a_remote_fetch_that_fails_leaves_edit_disabled(
    dash_client, caplog, detail_client, case, expected
):
  """Editing an agent whose instruction never loaded destroyed it.

  Both buttons start disabled and only this callback touches them. This branch
  used to enable Edit while leaving the config Store at no_update, and the
  instruction reaches the form only through that Store. The textarea opened
  blank, submit_edit copied the blank onto the config it sent, and update_agent
  pushes any instruction that is not None. A rename published an empty
  instruction over the real one and the user got a green success toast.

  Duplicate stays enabled because it sends the config it reads back from GDA at
  submit time and never writes to this agent.
  """
  if case == "raised":
    detail_client.agents.get_gcp_agent_details.side_effect = RuntimeError(
        "404 on projects/a-project/locations/us-central1/dataAgents/agent-7"
    )
  else:
    detail_client.agents.get_gcp_agent_details.return_value = None

  with caplog.at_level(logging.ERROR):
    response = _fire_remote(dash_client)

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)["response"]

  assert body[_DETAIL.BTN_EDIT][CP.DISABLED] is True
  assert body[_DETAIL.BTN_DUPLICATE][CP.DISABLED] is False
  # no_update outputs are left out of the response, so a stale config Store
  # is not overwritten with an error. This absence is why Edit is disabled
  # above: the two go together.
  assert _DETAIL.STORE_GCP_CONFIG not in body
  assert _DETAIL.BTN_RUN_EVAL not in body

  rendered = str(body[_DETAIL.INSTRUCTION][CP.CHILDREN])
  assert expected in rendered
  # The GDA error carries the resource name it was building. That belongs in
  # the server log, not the page.
  assert "404 on projects" not in rendered

  # caplog, not ``callback_errors``. The error is the thing under test here,
  # so the gate that fails on any logged error is the wrong tool.
  if case == "raised":
    assert "404 on projects" in caplog.text


def test_the_eval_modal_lists_the_suites_and_describes_the_one_picked(
    dash_client, callback_errors, seeded
):
  """Opening the modal and picking a suite has to reach the database.

  Nothing here is mocked. Both callbacks read only local tables, so this is
  the real path from the button to the suite card.
  """
  deps = dash_http.dependencies(dash_client)
  pathname = f"/agents/view/{seeded.agent_id}"

  open_dep = _dep_on(deps, f"{_DETAIL.BTN_RUN_EVAL}.{CP.N_CLICKS}")
  pattern = next(i for i in open_dep["inputs"] if str(i["id"]).startswith("{"))
  response = dash_http.fire(
      dash_client,
      open_dep,
      {
          f"{_DETAIL.BTN_RUN_EVAL}.{CP.N_CLICKS}": 1,
          dash_http.address(pattern): [],
          "url.pathname": pathname,
      },
      changed=[f"{_DETAIL.BTN_RUN_EVAL}.{CP.N_CLICKS}"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]
  assert body[_EVAL_MODAL.ROOT]["opened"] is True
  assert {
      CP.LABEL: seeded.suite_name,
      CP.VALUE: str(seeded.suite_id),
  } in body[
      _EVAL_MODAL.SELECT_SUITE
  ][CP.DATA]
  # Cleared, so a second open does not inherit the last selection.
  assert body[_EVAL_MODAL.SELECT_SUITE][CP.VALUE] is None

  select_dep = dash_http.find(
      deps, f"{_EVAL_MODAL.SUITE_DETAILS}.{CP.CHILDREN}"
  )
  response = dash_http.fire(
      dash_client,
      select_dep,
      {
          f"{_EVAL_MODAL.SELECT_SUITE}.{CP.VALUE}": str(seeded.suite_id),
          "url.pathname": pathname,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]
  assert body[_EVAL_MODAL.BTN_START][CP.DISABLED] is False
  card = str(body[_EVAL_MODAL.SUITE_DETAILS][CP.CHILDREN])
  assert seeded.suite_name in card
  assert "1 test case" in card


def test_the_eval_modal_counts_only_the_questions_the_run_will_use(
    dash_client, callback_errors, db_session, seeded
):
  """A deleted question must not be counted or credited for its assertions.

  Deleting a question archives it, and ``SuiteDetail.examples`` was validated
  off the unfiltered backref, so the card counted the archived ones too. The
  run then takes a fresh snapshot, which skips them, and executes fewer trials
  than the modal promised. The coverage badge comes off the same list, so an
  archived question with an assertion made an uncovered suite read as partly
  covered.
  """
  example_repo = ExampleRepository(db_session)
  archived = example_repo.create(seeded.suite_id, "A deleted question")
  example_repo.add_assertion(
      archived.id,
      assertion_schemas.TextContains(value="gone", weight=1.0),
  )
  example_repo.archive(archived.id)
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  response = dash_http.fire(
      dash_client,
      dash_http.find(deps, f"{_EVAL_MODAL.SUITE_DETAILS}.{CP.CHILDREN}"),
      {
          f"{_EVAL_MODAL.SELECT_SUITE}.{CP.VALUE}": str(seeded.suite_id),
          "url.pathname": f"/agents/view/{seeded.agent_id}",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  card = str(body[_EVAL_MODAL.SUITE_DETAILS][CP.CHILDREN])
  assert "1 test case" in card
  assert "2 test cases" not in card
  assert "No Coverage" in card
  assert "Partial Coverage" not in card


def _start_eval(
    dash_client, agent_id: int, suite_id: str, concurrency: Any = 3
):
  """Fires the Start button with suggestions on and concurrency set."""
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_EVAL_MODAL.BTN_START}.{CP.N_CLICKS}")
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{_EVAL_MODAL.BTN_START}.{CP.N_CLICKS}": 1,
          "url.pathname": f"/agents/view/{agent_id}",
          f"{_EVAL_MODAL.SELECT_SUITE}.{CP.VALUE}": suite_id,
          f"{_EVAL_MODAL.TOGGLE_SUGGESTIONS}.checked": True,
          f"{_EVAL_MODAL.INPUT_CONCURRENCY}.{CP.VALUE}": concurrency,
      },
  )


def test_starting_an_evaluation_creates_the_run_and_goes_to_it(
    dash_client, callback_errors, detail_client
):
  """The two modal options have to reach ``create_run``, not just the ids.

  Both are States, so nothing fails if they are unwired: the run is created
  with the defaults and the user's choices are silently dropped.
  """
  detail_client.agents.get_agent.return_value = _agent()
  detail_client.runs.create_run.return_value = mock.MagicMock(id=99)

  response = _start_eval(dash_client, 7, "3")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  detail_client.runs.create_run.assert_called_once_with(
      agent_id=7,
      test_suite_id=3,
      generate_suggestions=True,
      concurrency=3,
  )
  body = dash_http.body(response)["response"]
  assert body[REDIRECT_HANDLER][CP.HREF] == "/evaluations/runs/99"


def test_an_evaluation_will_not_start_without_the_looker_credentials(
    dash_client, callback_errors, detail_client
):
  """The last gate before a run spends quota, and it must not be the button.

  ``handle_suite_selection`` disables Start, but the disabled state lives in
  the browser and the callback is reachable without it.
  """
  detail_client.agents.get_agent.return_value = _agent(
      datasource=_looker(), client_id=_CLIENT_ID, secret=None
  )

  response = _start_eval(dash_client, 7, "3")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert not detail_client.runs.create_run.called

  body = dash_http.body(response)["response"]
  assert REDIRECT_HANDLER not in body
  notification = body[NOTIFICATION_CONTAINER]["sendNotifications"][0]
  assert notification["title"] == "Cannot Start Evaluation"
  assert notification[CP.COLOR] == "red"


@pytest.mark.parametrize("cleared", ["", None])
def test_an_empty_concurrency_box_is_named_in_the_toast(
    dash_client, callback_errors, detail_client, cleared
):
  """A cleared NumberInput sends "", not the value it was rendered with.

  That went into create_run as the run's concurrency and failed at the insert.
  The user got "Could not start the evaluation. The details are in the server
  log." for a field they could see was empty, and the log held a database
  error about a column nothing on screen mentions.
  """
  detail_client.agents.get_agent.return_value = _agent()

  response = _start_eval(dash_client, 7, "3", concurrency=cleared)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert not detail_client.runs.create_run.called

  body = dash_http.body(response)["response"]
  assert REDIRECT_HANDLER not in body
  notification = body[NOTIFICATION_CONTAINER]["sendNotifications"][0]
  assert notification["title"] == "Cannot Start Evaluation"
  assert "Max Concurrency" in notification["message"]


def test_a_failed_start_keeps_the_exception_out_of_the_toast(
    dash_client, caplog, detail_client
):
  """``create_run`` reaches the agent and the datasource layer.

  What it raises from there carries resource names and instance URIs, and the
  toast echoed the exception text, so a failed start put them on the page. The
  message is fixed now and the cause stays in the server log.
  """
  detail_client.agents.get_agent.return_value = _agent()
  detail_client.runs.create_run.side_effect = RuntimeError(
      "403 on projects/a-project/locations/us-central1/dataAgents/agent-7"
  )

  with caplog.at_level(logging.ERROR):
    response = _start_eval(dash_client, 7, "3")

  assert response.status_code == 200, response.data[:2000]
  assert "403 on projects" in caplog.text
  # The whole body, not just the message, since the toast is one of two
  # outputs and the other one is what the browser navigates to.
  assert "403 on projects" not in response.data.decode()

  body = dash_http.body(response)["response"]
  assert REDIRECT_HANDLER not in body
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  assert len(notifications) == 1
  assert notifications[0]["title"] == "Failed to Start Evaluation"
  assert notifications[0]["message"] == (
      "Could not start the evaluation. The details are in the server log."
  )


def _subtree(tree: Any, component_id: str) -> Any:
  """The serialized component carrying ``component_id``, and its children."""
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      props = node.get("props")
      if isinstance(props, dict):
        if props.get("id") == component_id:
          return node
        stack.extend(props.values())
  raise AssertionError(f"{component_id} is not on the page")


def test_the_golden_query_editor_is_inside_the_looker_panel(dash_client):
  """Only a Looker agent can save golden queries.

  submit_edit writes them on the LookerConfig branch and nowhere else. The
  editor used to sit above the datasource section, outside both panels, so a
  BigQuery agent was offered a box whose contents were parsed, validated, and
  then dropped. The panel is hidden by open_edit_modal, so putting the editor
  inside it is what ties the two together.

  This reads the page layout, not a callback response: the modal is static and
  the callback only flips the style.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, "_pages_content.children")
  response = dash_http.fire_url(dash_client, dep, "/agents/view/7")

  assert response.status_code == 200, response.data[:2000]
  page = dash_http.body(response)["response"]["_pages_content"]["children"]
  looker = _subtree(page, _DETAIL.CONTAINER_EDIT_LOOKER_CONFIG)

  assert str(page).count(_DETAIL.INPUT_EDIT_GOLDEN_QUERIES) == 1
  assert _DETAIL.INPUT_EDIT_GOLDEN_QUERIES in str(looker)


def test_the_edit_modal_shows_one_datasource_panel_when_the_copies_disagree(
    dash_client, callback_errors, detail_client
):
  """The panel has to match the datasource the save will write.

  The form is filled from the local row and the instruction comes from the GCP
  config Store, because it is not stored locally. The Store used to set the
  Looker panel visible as well, without hiding the BigQuery one. An agent the
  two copies disagree about opened with both panels up and the Looker fields
  empty, since those are filled from the local row. submit_edit picks the
  datasource type off the local row too, so the Looker URI typed into the extra
  panel went nowhere.
  """
  detail_client.agents.get_agent.return_value = _agent(
      datasource=agent_schemas.BigQueryConfig(
          tables=["a-project.a_dataset.a_table"]
      )
  )
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_EDIT}.{CP.N_CLICKS}")

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{_DETAIL.BTN_EDIT}.{CP.N_CLICKS}": 1,
          f"{_DETAIL.STORE_GCP_CONFIG}.{CP.DATA}": {
              "system_instruction": "an instruction",
              "datasource": {"instance_uri": _URI},
          },
          "url.pathname": "/agents/view/7",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.MODAL_EDIT]["opened"] is True
  assert body[_DETAIL.CONTAINER_EDIT_BQ_CONFIG]["style"]["display"] == "block"
  assert body[_DETAIL.CONTAINER_EDIT_LOOKER_CONFIG]["style"]["display"] == (
      "none"
  )
  assert body[_DETAIL.INPUT_EDIT_BQ_TABLES][CP.VALUE] == (
      "a-project.a_dataset.a_table"
  )
  # Still the one thing the Store is read for.
  assert body[_DETAIL.TEXTAREA_EDIT_INSTRUCTION][CP.VALUE] == "an instruction"


def _submit_edit(
    dash_client,
    explores: str = "a_model.orders",
    golden_queries: str = "",
    name: str = "Remote Agent",
):
  """Fires the edit form for a Looker agent."""
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_EDIT_SUBMIT}.{CP.N_CLICKS}")
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{_DETAIL.BTN_EDIT_SUBMIT}.{CP.N_CLICKS}": 1,
          "url.pathname": "/agents/view/7",
          f"{_DETAIL.INPUT_EDIT_NAME}.{CP.VALUE}": name,
          f"{_DETAIL.TEXTAREA_EDIT_INSTRUCTION}.{CP.VALUE}": "a new one",
          f"{_DETAIL.INPUT_EDIT_LOOKER_URI}.{CP.VALUE}": _URI,
          f"{_DETAIL.INPUT_EDIT_LOOKER_EXPLORES}.{CP.VALUE}": explores,
          f"{_DETAIL.INPUT_EDIT_LOOKER_CLIENT_ID}.{CP.VALUE}": _CLIENT_ID,
          f"{_DETAIL.INPUT_EDIT_LOOKER_CLIENT_SECRET}.{CP.VALUE}": "",
          f"{_DETAIL.INPUT_EDIT_BQ_TABLES}.{CP.VALUE}": "",
          f"{_DETAIL.INPUT_EDIT_GOLDEN_QUERIES}.{CP.VALUE}": golden_queries,
      },
  )


def test_an_edit_replaces_the_explores_and_parses_the_golden_queries(
    dash_client, callback_errors, detail_client
):
  """The textareas are the whole new value, not something to merge into.

  Golden queries go in as JSON and have to come out as
  ``LookerGoldenQuery``. Passing the raw dicts through would save, then fail
  at read time in whatever reads them next.
  """
  detail_client.agents.get_agent.return_value = _agent(
      datasource=_looker(["a_model.orders"]),
      client_id=_CLIENT_ID,
      secret=_CLIENT_SECRET,
  )

  response = _submit_edit(
      dash_client,
      explores="a_model.users\na_model.products",
      golden_queries=json.dumps([_GOLDEN_QUERY]),
      name="A New Name",
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  detail_client.agents.update_agent.assert_called_once()
  kwargs = detail_client.agents.update_agent.call_args.kwargs
  assert kwargs["agent_id"] == 7
  assert kwargs["name"] == "A New Name"
  config = kwargs["config"]
  assert config.system_instruction == "a new one"
  assert config.datasource.explores == ["a_model.users", "a_model.products"]
  assert config.datasource.instance_uri == _URI
  golden = config.golden_queries
  assert [type(gq) for gq in golden] == [agent_schemas.LookerGoldenQuery]
  assert golden[0].looker_query.explore == "orders"

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.MODAL_EDIT]["opened"] is False
  assert body[_DETAIL.EDIT_LOADING_OVERLAY]["visible"] is False
  assert body[NOTIFICATION_CONTAINER]["sendNotifications"][0]["title"] == (
      "Success"
  )
  # Re-runs the local pass, so the page shows the new name without a reload.
  assert body[_DETAIL.STORE_REFRESH_TRIGGER][CP.DATA]


def test_emptying_the_golden_query_box_clears_the_stored_queries(
    dash_client, callback_errors, detail_client
):
  """Blank means none, and it is the only way to delete them from the UI.

  ``None`` would read as "leave them alone" in ``AgentRepository.update``, so
  the list has to be empty and present.
  """
  detail_client.agents.get_agent.return_value = _agent(
      datasource=_looker(),
      client_id=_CLIENT_ID,
      secret=_CLIENT_SECRET,
      golden_queries=[
          agent_schemas.LookerGoldenQuery.model_validate(_GOLDEN_QUERY)
      ],
  )

  response = _submit_edit(dash_client, golden_queries="")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  config = detail_client.agents.update_agent.call_args.kwargs["config"]
  assert config.golden_queries == []


@pytest.mark.parametrize(
    "explores,golden_queries,title,fragment",
    [
        (
            "a_model.orders\nnot_an_explore",
            "",
            "Validation Error",
            "Invalid Looker Explore: not_an_explore",
        ),
        (
            "a_model.orders",
            "{}",
            "Validation Error",
            "Golden Queries must be a list",
        ),
        (
            "a_model.orders",
            "[{",
            "Validation Error",
            "Golden Queries must be valid JSON",
        ),
        (
            "a_model.orders",
            '[{"nope": 1}]',
            "Golden Query Error",
            "Invalid Golden Query structure",
        ),
    ],
)
def test_a_bad_edit_names_the_problem_and_saves_nothing(
    dash_client,
    callback_errors,
    detail_client,
    explores,
    golden_queries,
    title,
    fragment,
):
  """A rejected edit has to say which field, and must not reach the agent.

  ``update_agent`` pushes the system instruction to GDA, so a half-validated
  save is a remote write. The loading overlay has to come down too: a
  clientside callback raises it on click and only the response lowers it.
  """
  detail_client.agents.get_agent.return_value = _agent(
      datasource=_looker(), client_id=_CLIENT_ID, secret=_CLIENT_SECRET
  )

  response = _submit_edit(
      dash_client, explores=explores, golden_queries=golden_queries
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert not detail_client.agents.update_agent.called

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.EDIT_LOADING_OVERLAY]["visible"] is False
  assert REDIRECT_HANDLER not in body
  notification = body[NOTIFICATION_CONTAINER]["sendNotifications"][0]
  assert notification["title"] == title
  assert fragment in notification["message"]


def test_the_duplicate_modal_prefills_a_copy_of_the_current_name(
    dash_client, callback_errors, seeded
):
  """The prefix is a hint, not a claim that the name is free.

  Nothing enforces a unique agent name. The column has no unique constraint,
  and ``create_agent`` sends no ``data_agent_id``, so GDA picks its own and
  the display name is free too. Duplicating twice writes two agents called
  "Copy of X" and both saves succeed. The old name said the name was not
  taken, which no production code checks.

  This reads the real agent, so it also covers the id being parsed out of the
  pathname.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_DUPLICATE}.{CP.N_CLICKS}")

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{_DETAIL.BTN_DUPLICATE}.{CP.N_CLICKS}": 1,
          "url.pathname": f"/agents/view/{seeded.agent_id}",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.MODAL_DUPLICATE]["opened"] is True
  assert body[_DETAIL.INPUT_DUPLICATE_NAME][CP.VALUE] == (
      f"Copy of {seeded.agent_name}"
  )


def test_the_duplicate_modal_still_opens_when_the_name_cannot_be_read(
    dash_client, caplog, detail_client
):
  """Losing the prefill is not worth blocking the duplicate.

  The read is wrapped, so the modal opens on a generic name and the user can
  type over it. The submit path takes the name from the field, so a blank
  prefill would have made the copy over an empty display name.
  """
  detail_client.agents.get_agent.side_effect = RuntimeError("boom")
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_DUPLICATE}.{CP.N_CLICKS}")

  with caplog.at_level(logging.ERROR):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{_DETAIL.BTN_DUPLICATE}.{CP.N_CLICKS}": 1,
            "url.pathname": "/agents/view/7",
        },
    )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)["response"]
  assert body[_DETAIL.MODAL_DUPLICATE]["opened"] is True
  assert body[_DETAIL.INPUT_DUPLICATE_NAME][CP.VALUE] == "Copy of Agent"
  # caplog, not callback_errors. The logged error is the point of the branch.
  assert "boom" in caplog.text


def _submit_duplicate(dash_client, name: str = "Copy of Remote Agent"):
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_DUPLICATE_SUBMIT}.{CP.N_CLICKS}")
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{_DETAIL.BTN_DUPLICATE_SUBMIT}.{CP.N_CLICKS}": 1,
          "url.pathname": "/agents/view/7",
          f"{_DETAIL.INPUT_DUPLICATE_NAME}.{CP.VALUE}": name,
      },
  )


def test_duplicating_an_agent_goes_to_the_copy(
    dash_client, callback_errors, detail_client
):
  """The redirect is how the user learns the copy exists and which one it is."""
  detail_client.agents.duplicate_agent.return_value = mock.MagicMock(id=42)

  response = _submit_duplicate(dash_client, "Copy of Remote Agent")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  detail_client.agents.duplicate_agent.assert_called_once_with(
      7, "Copy of Remote Agent"
  )

  body = dash_http.body(response)["response"]
  assert body[REDIRECT_HANDLER][CP.HREF] == "/agents/view/42"
  assert body[_DETAIL.MODAL_DUPLICATE]["opened"] is False
  assert body[_DETAIL.DUPLICATE_LOADING_OVERLAY]["visible"] is False


def test_a_failed_duplicate_says_so_and_keeps_the_typed_name(
    dash_client, caplog, detail_client
):
  """``duplicate_agent`` registers on GDA and then writes the local row.

  A failure can leave a remote agent with nothing pointing at it, so the user
  has to be told. The modal stays open on purpose, to keep the name they
  typed, which on its own reads as a dead button.
  """
  detail_client.agents.duplicate_agent.side_effect = RuntimeError("boom")

  with caplog.at_level(logging.ERROR):
    response = _submit_duplicate(dash_client)

  assert response.status_code == 200, response.data[:2000]
  assert "Failed to duplicate agent: boom" in caplog.text

  body = dash_http.body(response)["response"]
  assert REDIRECT_HANDLER not in body
  assert body[_DETAIL.MODAL_DUPLICATE]["opened"] is True
  assert body[_DETAIL.DUPLICATE_LOADING_OVERLAY]["visible"] is False

  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  assert len(notifications) == 1
  assert notifications[0]["color"] == "red"
  # Not the exception text: it names the GDA resource it was building.
  assert "boom" not in notifications[0]["message"]
  assert "server log" in notifications[0]["message"]


@pytest.mark.parametrize(
    "button,archived_before,archived_after,message",
    [
        (_DETAIL.BTN_ARCHIVE, False, True, "Agent archived successfully."),
        (_DETAIL.BTN_RESTORE, True, False, "Agent restored successfully."),
    ],
)
def test_archiving_and_restoring_write_the_row_and_say_which_happened(
    dash_client,
    callback_errors,
    db_session,
    button,
    archived_before,
    archived_after,
    message,
):
  """One callback serves both buttons and branches on which one fired.

  Nothing is mocked: both calls are local. The notification has to be a list,
  because ``NotificationContainer`` ignores a bare dict without complaining.
  """
  agent_id = _stored_looker_agent(
      db_session, client_id=_CLIENT_ID, archived=archived_before
  )

  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(
      deps,
      f"{_DETAIL.BTN_ARCHIVE}.{CP.N_CLICKS}",
      f"{_DETAIL.BTN_RESTORE}.{CP.N_CLICKS}",
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{button}.{CP.N_CLICKS}": 1,
          "url.pathname": f"/agents/view/{agent_id}",
      },
      changed=[f"{button}.{CP.N_CLICKS}"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  assert isinstance(notifications, list)
  assert notifications[0]["message"] == message
  assert notifications[0][CP.COLOR] == "green"
  # Re-runs the local pass so the Archive and Restore buttons swap over.
  assert body[_DETAIL.STORE_REFRESH_TRIGGER][CP.DATA]["ts"]

  db_session.expire_all()
  stored = AgentRepository(db_session).get_by_id(agent_id)
  assert stored.is_archived is archived_after


@pytest.mark.parametrize(
    "chart,select,days_str,days,unit,value",
    [
        (
            _DETAIL.CHART_EVAL_ACCURACY_ROOT,
            _DETAIL.SELECT_EVAL_ACCURACY_DAYS,
            "Last 7 Days",
            7,
            "%",
            50.0,
        ),
        (
            _DETAIL.CHART_EVAL_ACCURACY_ROOT,
            _DETAIL.SELECT_EVAL_ACCURACY_DAYS,
            "Last 30 Days",
            30,
            "%",
            50.0,
        ),
        (
            _DETAIL.CHART_DURATION_ROOT,
            _DETAIL.SELECT_DURATION_DAYS,
            "Last 7 Days",
            7,
            "ms",
            1200,
        ),
        (
            _DETAIL.CHART_DURATION_ROOT,
            _DETAIL.SELECT_DURATION_DAYS,
            "Last 30 Days",
            30,
            "ms",
            1200,
        ),
    ],
)
def test_the_range_dropdown_reaches_the_query_and_keeps_the_units(
    dash_client,
    callback_errors,
    detail_client,
    chart,
    select,
    days_str,
    days,
    unit,
    value,
):
  """Both charts re-query on the dropdown, and only one of them scales.

  Accuracy is stored as a fraction and shown as a percentage. Duration is
  already in milliseconds. Scaling the wrong one gives a chart that still
  renders, which is why the value is asserted and not just the unit.
  """
  detail_client.runs.get_agent_dashboard_stats.return_value = {
      "daily_accuracy": [{"date": "2026-01-01", "Seeded Suite": 0.5}],
      "daily_duration": [{"date": "2026-01-01", "Seeded Suite": 1200}],
      "suites": ["Seeded Suite"],
  }

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{chart}.{CP.CHILDREN}")
  response = dash_http.fire(
      dash_client,
      dep,
      {f"{select}.{CP.VALUE}": days_str, "url.pathname": "/agents/view/7"},
      changed=[f"{select}.{CP.VALUE}"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  # The client is a MagicMock, so this says the dropdown value reached the call
  # and nothing about what days does. That is
  # tests/repositories/test_run_repository_windows.py.
  detail_client.runs.get_agent_dashboard_stats.assert_called_once_with(
      7, days=days
  )

  props = dash_http.body(response)["response"][chart][CP.CHILDREN]["props"]
  assert props["unit"] == unit
  assert props["data"][0]["Seeded Suite"] == value


@pytest.mark.parametrize(
    "field,preview,good,bad,prefix",
    [
        (
            _DETAIL.INPUT_EDIT_BQ_TABLES,
            _DETAIL.INPUT_EDIT_BQ_TABLES_PREVIEW,
            "a-project.a_dataset.a_table",
            "a-project.a_dataset",
            "Invalid BQ paths:",
        ),
        (
            _DETAIL.INPUT_EDIT_LOOKER_EXPLORES,
            _DETAIL.INPUT_EDIT_LOOKER_EXPLORES_PREVIEW,
            "a_model.orders",
            "a_model.orders.extra",
            "Invalid Looker paths:",
        ),
    ],
)
def test_the_edit_path_preview_badges_the_line_that_is_wrong(
    dash_client, callback_errors, field, preview, good, bad, prefix
):
  """One badge per line, and the bad one turns red as it is typed.

  The preview is the only feedback before submit, and submit is where the
  remote write happens. Clearing the box has to clear both outputs, or a
  stale error sits under an empty field.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{preview}.{CP.CHILDREN}")

  response = dash_http.fire(
      dash_client, dep, {f"{field}.{CP.VALUE}": f"{good}\n{bad}"}
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]
  badges = body[preview][CP.CHILDREN]
  assert [b["props"][CP.CHILDREN] for b in badges] == [good, bad]
  assert [b["props"][CP.COLOR] for b in badges] == ["blue", "red"]
  error = body[field]["error"]
  assert error.startswith(prefix)
  assert bad in error

  response = dash_http.fire(dash_client, dep, {f"{field}.{CP.VALUE}": ""})

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]
  assert body[preview][CP.CHILDREN] == []
  assert body[field]["error"] is False


@pytest.mark.parametrize(
    "value,expected",
    [
        ("", ""),
        ("[]", ""),
        ('[{"a": 1}]', ""),
        ("{}", "Error: Must be a list of objects"),
        ("[{", "Invalid JSON:"),
    ],
)
def test_the_golden_query_box_reports_bad_json_as_it_is_typed(
    dash_client, callback_errors, value, expected
):
  """Shape first, structure at submit. This is the shape half."""
  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.INPUT_EDIT_GOLDEN_QUERIES}.{CP.VALUE}")

  response = dash_http.fire(
      dash_client,
      dep,
      {f"{_DETAIL.INPUT_EDIT_GOLDEN_QUERIES}.{CP.VALUE}": value},
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  error = dash_http.body(response)["response"][_DETAIL.ERROR_GOLDEN_QUERIES][
      CP.CHILDREN
  ]
  # startswith on the two bad rows, because the parser's own text follows the
  # prefix. Equality on the three good ones: startswith("") is true of every
  # string, so those rows asserted nothing at all.
  if expected:
    assert error.startswith(expected)
  else:
    assert error == ""


@pytest.mark.parametrize(
    "case,client_id,secret,result,message,color",
    [
        ("incomplete", "", "", None, "Incomplete credentials.", "orange"),
        (
            "stored secret",
            _CLIENT_ID,
            "",
            {"success": True, "message": "Connected."},
            "Connected.",
            "green",
        ),
        (
            "ok",
            _CLIENT_ID,
            _CLIENT_SECRET,
            {"success": True, "message": "Connected."},
            "Connected.",
            "green",
        ),
        (
            "rejected",
            _CLIENT_ID,
            _CLIENT_SECRET,
            {"success": False, "message": "Bad credentials."},
            "Bad credentials.",
            "red",
        ),
        (
            "raised",
            _CLIENT_ID,
            _CLIENT_SECRET,
            RuntimeError("no route"),
            "Could not reach the Looker instance.",
            "red",
        ),
    ],
)
def test_the_looker_test_button_reports_what_the_service_said(
    dash_client,
    callback_errors,
    detail_client,
    case,
    client_id,
    secret,
    result,
    message,
    color,
):
  """Green only on success, and the alert says which it was.

  The result dict is read with ``result["success"]``, so a service that stops
  returning that key raises inside the try and reads as a failed connection
  rather than a bug. The incomplete case must not call out at all. A blank
  secret is not incomplete: the edit modal never renders the stored one, so
  blank means test what the agent already has. The raised case must not quote
  the exception: it carries the instance URI.
  """
  if isinstance(result, Exception):
    detail_client.agents.test_looker_credentials.side_effect = result
  else:
    detail_client.agents.test_looker_credentials.return_value = result

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{_DETAIL.ALERT_LOOKER_TEST}.{CP.CHILDREN}")
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{_DETAIL.BTN_TEST_LOOKER}.{CP.N_CLICKS}": 1,
          f"{_DETAIL.INPUT_EDIT_LOOKER_URI}.{CP.VALUE}": _URI,
          f"{_DETAIL.INPUT_EDIT_LOOKER_CLIENT_ID}.{CP.VALUE}": client_id,
          f"{_DETAIL.INPUT_EDIT_LOOKER_CLIENT_SECRET}.{CP.VALUE}": secret,
      },
  )

  assert response.status_code == 200, response.data[:2000]
  if case == "raised":
    # The callback logs the exception itself. Consuming that record and
    # leaving the gate empty is what proves handle_errors did not have to step
    # in on top of it.
    callback_errors.assert_logged("Looker connection test failed")
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.ALERT_LOOKER_TEST][CP.CHILDREN].startswith(message)
  assert body[_DETAIL.ALERT_LOOKER_TEST][CP.COLOR] == color
  assert body[_DETAIL.ALERT_LOOKER_TEST][CP.HIDE] is False
  # The spinner is Dash's running= now, so it is not in the response body.
  assert _DETAIL.BTN_TEST_LOOKER not in body

  assert detail_client.agents.test_looker_credentials.called is (
      case != "incomplete"
  )
  assert _CLIENT_SECRET not in response.data.decode()


def test_the_ai_fix_rewrites_the_golden_query_box(
    dash_client, callback_errors, detail_client
):
  """The fixed JSON has to come back into the field, and clear the error."""
  fixed = json.dumps([_GOLDEN_QUERY])
  detail_client.agents.format_golden_queries_with_ai.return_value = fixed

  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_FIX_GOLDEN_QUERIES_AI}.{CP.N_CLICKS}")
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{_DETAIL.BTN_FIX_GOLDEN_QUERIES_AI}.{CP.N_CLICKS}": 1,
          f"{_DETAIL.INPUT_EDIT_GOLDEN_QUERIES}.{CP.VALUE}": "[{",
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  detail_client.agents.format_golden_queries_with_ai.assert_called_once_with(
      "[{"
  )

  body = dash_http.body(response)["response"]
  assert body[_DETAIL.INPUT_EDIT_GOLDEN_QUERIES][CP.VALUE] == fixed
  assert body[_DETAIL.ERROR_GOLDEN_QUERIES][CP.CHILDREN] == ""


def test_a_failed_ai_fix_leaves_what_was_typed_alone(
    dash_client, caplog, detail_client
):
  """Overwriting the box on failure would lose the text the user was fixing."""
  detail_client.agents.format_golden_queries_with_ai.side_effect = RuntimeError(
      "model unavailable"
  )

  deps = dash_http.dependencies(dash_client)
  dep = _dep_on(deps, f"{_DETAIL.BTN_FIX_GOLDEN_QUERIES_AI}.{CP.N_CLICKS}")
  with caplog.at_level(logging.ERROR):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{_DETAIL.BTN_FIX_GOLDEN_QUERIES_AI}.{CP.N_CLICKS}": 1,
            f"{_DETAIL.INPUT_EDIT_GOLDEN_QUERIES}.{CP.VALUE}": "[{",
        },
    )

  assert response.status_code == 200, response.data[:2000]
  assert "model unavailable" in caplog.text

  body = dash_http.body(response)["response"]
  assert _DETAIL.INPUT_EDIT_GOLDEN_QUERIES not in body
  error = body[_DETAIL.ERROR_GOLDEN_QUERIES][CP.CHILDREN]
  assert error.startswith("AI fix failed")
  # Not the exception text. It renders under the textarea.
  assert "model unavailable" not in error
