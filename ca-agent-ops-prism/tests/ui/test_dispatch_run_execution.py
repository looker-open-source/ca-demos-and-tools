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

"""Starting, controlling and reporting on a run, over the dispatch route.

Three pages can start a run and they do it through three different callbacks.
The run detail page then shows a set of controls whose visibility is a tuple of
style dicts, and a polling interval whose ``disabled`` is a bare bool. All of
it is data on the wire, so the POST is the whole story.

None of these tests may reach the agent API. tests/ui runs with
``PRISM_AGENT_BACKEND`` unset, which is live, and ``create_run`` reads the
agent's datasource and its published context off the service before it writes
anything. ``offline_gda`` below is what stops that, and it stops it without
mocking the client away, so the run rows these tests assert on are real.
"""

from __future__ import annotations
import datetime
from typing import Any
from unittest import mock
from prism.client import dependencies
from prism.common.schemas import agent as agent_schemas
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.config import settings
from prism.server.models.run import Run
from prism.server.repositories.agent_repository import AgentRepository
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
from prism.ui.models.ui_state import RunDetailPageState
from prism.ui.pages.agent_ids import AgentIds
import pytest
from tests.ui import dash_http


def _by_input(deps: list[dict[str, Any]], address: str) -> dict[str, Any]:
  """Returns the one callback taking ``"<id>.<property>"`` as an input.

  ``dash_http.find`` addresses a callback by what it writes, which does not
  work for the ones here: three callbacks write ``url.search`` and four write
  ``redirect-handler.href``. The button that drives them is unique.
  """
  matches = [
      dep
      for dep in deps
      if any(dash_http.address(i) == address for i in dep["inputs"])
  ]
  assert len(matches) == 1, (
      f"expected exactly one callback driven by {address!r}, found"
      f" {len(matches)}"
  )
  return matches[0]


class _OfflineGda(GeminiDataAnalyticsClient):
  """A GDA client with no transport, answering the two reads create_run does.

  A subclass rather than a Mock because fast_depends type-checks the injected
  dependency, and a Mock is not an instance of it. Anything not overridden
  here still runs the real method, which fails on the null transport instead
  of reaching the API.
  """

  def __init__(self):  # pylint: disable=super-init-not-called
    self.project = ""
    self.location = "global"
    self.chat_client = None
    self.agent_client = None
    self.calls: list[tuple[str, str]] = []

  def get_datasource_kind(self, agent_name: str) -> str:
    self.calls.append(("get_datasource_kind", agent_name))
    return "bq"

  def get_agent_context(
      self, agent_name: str, context_target: str
  ) -> dict[str, Any]:
    del context_target
    self.calls.append(("get_agent_context", agent_name))
    return {"system_instruction": "stub"}


@pytest.fixture(name="offline_gda")
def _offline_gda(monkeypatch) -> _OfflineGda:
  """Stubs the cached GDA client, so ``create_run`` cannot leave the process.

  The stub goes in at the dependency cache rather than at ``get_client`` in
  the callback module, because the point of these tests is the row
  ``create_run`` writes. Mocking the Prism client away would take the write
  with it. Everything between the callback and the agent API is still real.
  """
  gda = _OfflineGda()
  monkeypatch.setattr(dependencies, "_GDA_CLIENT", gda)
  return gda


@pytest.fixture(name="no_bigquery")
def _no_bigquery():
  """Pins the export off, so the run detail render asks BigQuery nothing."""
  with mock.patch.object(settings, "bigquery_export_enabled", False):
    yield


@pytest.fixture(name="looker_agent_id")
def _looker_agent_id(db_session) -> int:
  """A Looker agent saved with no client id and no secret."""
  config = agent_schemas.AgentConfig(
      project_id="p",
      location="l",
      agent_resource_id="r",
      datasource=agent_schemas.LookerConfig(
          instance_uri="https://looker.example", explores=["orders"]
      ),
  )
  return AgentRepository(db_session).create(name="Creds Free", config=config).id


def _run_store(status: RunStatus, is_archived: bool = False) -> dict[str, Any]:
  """The RUN_DATA_STORE payload for a run in the given status."""
  run = RunSchema(
      id=99,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=status,
      is_archived=is_archived,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
  )
  return RunDetailPageState(run=run, trials=[]).model_dump(mode="json")


def _render_run_detail(dash_client, store: dict[str, Any]):
  """POSTs a run-detail store payload and returns the decoded body."""
  deps = dash_http.dependencies(dash_client)
  dep = _by_input(deps, f"{EvaluationIds.RUN_DATA_STORE}.data")
  response = dash_http.fire(
      dash_client, dep, {f"{EvaluationIds.RUN_DATA_STORE}.data": store}
  )
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"]


_BLOCK = {"display": "block"}
_NONE = {"display": "none"}


@pytest.mark.parametrize(
    "status,pause,resume,cancel,poll_off",
    [
        (RunStatus.PENDING, _BLOCK, _NONE, _BLOCK, False),
        (RunStatus.RUNNING, _BLOCK, _NONE, _BLOCK, False),
        (RunStatus.EXECUTING, _BLOCK, _NONE, _BLOCK, False),
        (RunStatus.EVALUATING, _BLOCK, _NONE, _BLOCK, False),
        (RunStatus.PAUSED, _NONE, _BLOCK, _BLOCK, False),
        (RunStatus.COMPLETED, _NONE, _NONE, _NONE, True),
        (RunStatus.FAILED, _NONE, _NONE, _NONE, True),
        (RunStatus.CANCELLED, _NONE, _NONE, _NONE, True),
    ],
)
def test_the_run_controls_and_the_poll_follow_the_run_status(
    dash_client,
    callback_errors,
    no_bigquery,
    status,
    pause,
    resume,
    cancel,
    poll_off,
):
  """Which buttons are on screen, and whether the page keeps asking.

  A RUNNING run with no Cancel button cannot be stopped from the UI, and there
  is no other stop control. A poll left disabled freezes the progress page at
  zero trials for the length of the run, and the BigQuery restraint documented
  at the badge depends on the poll being off once the run is COMPLETED, so the
  two rules are one rule.
  """
  rendered = _render_run_detail(dash_client, _run_store(status))

  callback_errors.assert_none()
  assert rendered[EvaluationIds.BTN_PAUSE_RUN]["style"] == pause
  assert rendered[EvaluationIds.BTN_RESUME_RUN]["style"] == resume
  assert rendered[EvaluationIds.BTN_CANCEL_RUN_EXEC]["style"] == cancel
  assert rendered[EvaluationIds.RUN_POLLING_INTERVAL]["disabled"] is poll_off


@pytest.mark.parametrize(
    "status,label,color",
    [
        (RunStatus.RUNNING, "In Progress", "blue"),
        (RunStatus.PAUSED, "Paused", "yellow"),
    ],
)
def test_the_run_status_badge_says_what_the_rest_of_the_app_says(
    dash_client, callback_errors, no_bigquery, status, label, color
):
  """One status reads the same on the run page as in the run list.

  This badge held its own colour map and rendered ``run.status.value``, so the
  run the list called "In Progress" called itself "RUNNING" on its own page,
  and a PAUSED run was orange here and yellow everywhere else.
  """
  rendered = _render_run_detail(dash_client, _run_store(status))

  callback_errors.assert_none()
  assert rendered[EvaluationIds.RUN_STATUS_BADGE]["children"] == label
  assert rendered[EvaluationIds.RUN_STATUS_BADGE]["color"] == color


def test_an_archived_run_offers_restore_instead_of_archive(
    dash_client, callback_errors, no_bigquery
):
  """Archive and Restore share a slot, and only one of them is ever right.

  Without this branch the Restore button is never displayed, and an archived
  run cannot be brought back from the page it is on.
  """
  active = _render_run_detail(dash_client, _run_store(RunStatus.COMPLETED))
  archived = _render_run_detail(
      dash_client, _run_store(RunStatus.COMPLETED, is_archived=True)
  )

  callback_errors.assert_none()
  assert active[EvaluationIds.BTN_ARCHIVE]["style"] == _BLOCK
  assert active[EvaluationIds.BTN_RESTORE]["style"] == _NONE
  assert archived[EvaluationIds.BTN_ARCHIVE]["style"] == _NONE
  assert archived[EvaluationIds.BTN_RESTORE]["style"] == _BLOCK


def test_pause_resume_and_cancel_route_to_their_own_client_calls(
    dash_client, callback_errors, db_session, seeded
):
  """One callback, three buttons, and it reports success either way.

  ``handle_run_controls`` returns a fresh timestamp whatever happened, so a
  trigger routed to the wrong branch, or to none of them, still re-renders the
  page and reads as a working click. The run status is the only evidence.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _by_input(deps, f"{EvaluationIds.BTN_PAUSE_RUN}.n_clicks")
  pathname = f"/evaluations/runs/{seeded.run_id}"

  run = db_session.get(Run, seeded.run_id)
  run.status = RunStatus.RUNNING
  db_session.commit()

  for button, expected in (
      (EvaluationIds.BTN_PAUSE_RUN, RunStatus.PAUSED),
      (EvaluationIds.BTN_RESUME_RUN, RunStatus.RUNNING),
      (EvaluationIds.BTN_CANCEL_RUN_EXEC, RunStatus.CANCELLED),
  ):
    response = dash_http.fire(
        dash_client,
        dep,
        {f"{button}.n_clicks": 1, "url.pathname": pathname},
        changed=[f"{button}.n_clicks"],
    )

    assert response.status_code == 200, response.data[:2000]
    callback_errors.assert_none(f"on {button}")
    signal = dash_http.body(response)["response"][
        EvaluationIds.RUN_UPDATE_SIGNAL
    ]["data"]
    assert isinstance(signal, float), signal

    db_session.expire_all()
    assert db_session.get(Run, seeded.run_id).status == expected, button


def test_the_new_evaluation_modal_populates_its_selects_and_starts_a_run(
    dash_client, callback_errors, db_session, seeded, offline_gda
):
  """The only way to start a run without going to a specific suite first.

  Both guard paths in ``start_new_eval`` return a bare ``dash.no_update``, and
  the ``running=`` guard means Dash answers that 200 with an empty response
  rather than 204. So a modal that came up with empty selects would start
  nothing and say nothing. The run has to be real, which is why the row is read
  back rather than the call counted.
  """
  deps = dash_http.dependencies(dash_client)
  toggle = _by_input(deps, f"{EvaluationIds.BTN_NEW_EVAL}.n_clicks")
  start = _by_input(deps, f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks")

  opened = dash_http.body(
      dash_http.fire(
          dash_client,
          toggle,
          {f"{EvaluationIds.BTN_NEW_EVAL}.n_clicks": 1},
          changed=[f"{EvaluationIds.BTN_NEW_EVAL}.n_clicks"],
      )
  )["response"]
  assert opened[EvaluationIds.MODAL_NEW_EVAL]["opened"] is True
  assert opened[EvaluationIds.NEW_EVAL_AGENT_SELECT]["data"] == [
      {"label": seeded.agent_name, "value": str(seeded.agent_id)}
  ]
  assert opened[EvaluationIds.NEW_EVAL_SUITE_SELECT]["data"] == [
      {"label": seeded.suite_name, "value": str(seeded.suite_id)}
  ]

  # Nothing picked yet, so the guard has to refuse rather than create a run
  # against agent None. The refusal writes nothing, so the run count is the
  # only thing that can tell a guard from a silent failure.
  before = db_session.query(Run).count()
  refused = dash_http.fire(
      dash_client,
      start,
      {f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks": 1},
      changed=[f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks"],
  )
  assert refused.status_code == 200, refused.data[:2000]
  assert dash_http.body(refused)["response"] == {}
  callback_errors.assert_none("on the empty-select guard")
  db_session.expire_all()
  assert db_session.query(Run).count() == before

  response = dash_http.fire(
      dash_client,
      start,
      {
          f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks": 1,
          f"{EvaluationIds.NEW_EVAL_AGENT_SELECT}.value": str(seeded.agent_id),
          f"{EvaluationIds.NEW_EVAL_SUITE_SELECT}.value": str(seeded.suite_id),
          f"{EvaluationIds.TOGGLE_SUGGESTIONS}.checked": False,
          f"{EvaluationIds.NEW_EVAL_INPUT_CONCURRENCY}.value": 3,
      },
      changed=[f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert offline_gda.calls, "the stub was not the client create_run used"

  href = dash_http.body(response)["response"][REDIRECT_HANDLER]["href"]
  run_id = int(href.rsplit("/", 1)[-1])
  assert href == f"/evaluations/runs/{run_id}"
  assert run_id != seeded.run_id

  db_session.expire_all()
  run = db_session.get(Run, run_id)
  assert run.agent_id == seeded.agent_id
  assert run.concurrency == 3


def test_starting_a_run_from_the_agent_page_enables_start_and_creates_the_run(
    dash_client, callback_errors, db_session, seeded, offline_gda
):
  """The agent detail start path, from opening the modal to the new run.

  Start is disabled until a suite is picked, and ``handle_suite_selection`` is
  the only thing that enables it, so a wrong bool there makes the button
  permanently dead. This is also the one start path that never calls
  ``execute_run_async``, so the run it writes has to come out PENDING for the
  worker to promote it.
  """
  deps = dash_http.dependencies(dash_client)
  pathname = f"/agents/view/{seeded.agent_id}"
  modal = AgentIds.Detail.EvalModal

  opened = dash_http.body(
      dash_http.fire(
          dash_client,
          _by_input(deps, f"{AgentIds.Detail.BTN_RUN_EVAL}.n_clicks"),
          {
              f"{AgentIds.Detail.BTN_RUN_EVAL}.n_clicks": 1,
              "url.pathname": pathname,
          },
          changed=[f"{AgentIds.Detail.BTN_RUN_EVAL}.n_clicks"],
      )
  )["response"]
  assert opened[modal.ROOT]["opened"] is True
  assert opened[modal.SELECT_SUITE]["data"] == [
      {"label": seeded.suite_name, "value": str(seeded.suite_id)}
  ]

  select = _by_input(deps, f"{modal.SELECT_SUITE}.value")
  nothing_picked = dash_http.body(
      dash_http.fire(dash_client, select, {f"{modal.SELECT_SUITE}.value": None})
  )["response"]
  assert nothing_picked[modal.BTN_START]["disabled"] is True

  picked = dash_http.body(
      dash_http.fire(
          dash_client,
          select,
          {
              f"{modal.SELECT_SUITE}.value": str(seeded.suite_id),
              "url.pathname": pathname,
          },
      )
  )["response"]
  assert picked[modal.BTN_START]["disabled"] is False
  assert seeded.suite_name in str(picked[modal.SUITE_DETAILS]["children"])

  response = dash_http.fire(
      dash_client,
      _by_input(deps, f"{modal.BTN_START}.n_clicks"),
      {
          f"{modal.BTN_START}.n_clicks": 1,
          "url.pathname": pathname,
          f"{modal.SELECT_SUITE}.value": str(seeded.suite_id),
          f"{modal.TOGGLE_SUGGESTIONS}.checked": False,
          f"{modal.INPUT_CONCURRENCY}.value": 2,
      },
      changed=[f"{modal.BTN_START}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert offline_gda.calls, "the stub was not the client create_run used"

  href = dash_http.body(response)["response"][REDIRECT_HANDLER]["href"]
  run_id = int(href.rsplit("/", 1)[-1])
  db_session.expire_all()
  run = db_session.get(Run, run_id)
  assert run.agent_id == seeded.agent_id
  assert run.status == RunStatus.PENDING


def _looker_refusal_cases(seeded, looker_agent_id: int) -> dict[str, Any]:
  """The three start paths, keyed by the button that drives each one."""
  modal = AgentIds.Detail.EvalModal
  return {
      f"{EvaluationIds.BTN_START_RUN}.n_clicks": {
          f"{EvaluationIds.BTN_START_RUN}.n_clicks": 1,
          f"{EvaluationIds.AGENT_SELECT}.value": str(looker_agent_id),
          "url.pathname": f"/test_suites/view/{seeded.suite_id}",
      },
      f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks": {
          f"{EvaluationIds.BTN_START_NEW_EVAL}.n_clicks": 1,
          f"{EvaluationIds.NEW_EVAL_AGENT_SELECT}.value": str(looker_agent_id),
          f"{EvaluationIds.NEW_EVAL_SUITE_SELECT}.value": str(seeded.suite_id),
      },
      f"{modal.BTN_START}.n_clicks": {
          f"{modal.BTN_START}.n_clicks": 1,
          "url.pathname": f"/agents/view/{looker_agent_id}",
          f"{modal.SELECT_SUITE}.value": str(seeded.suite_id),
          # The value the modal renders. Left out, it arrives as None and the
          # empty-field guard above the credential check answers instead.
          f"{modal.INPUT_CONCURRENCY}.value": 2,
      },
  }


@pytest.mark.parametrize("case", [0, 1, 2])
def test_a_looker_agent_without_credentials_is_refused_before_a_run_is_created(
    dash_client,
    callback_errors,
    db_session,
    seeded,
    looker_agent_id,
    offline_gda,
    case,
):
  """Three start paths each carry their own copy of the same refusal.

  ``create_run`` raises for the same agent, so the unique value of the UI
  branch is the message, which names the agent and says where to fix it, and
  not creating the run at all. ``offline_gda`` is here as a backstop: if a
  branch regresses, the test must not be what discovers it by calling the
  agent API.
  """
  deps = dash_http.dependencies(dash_client)
  button, values = list(_looker_refusal_cases(seeded, looker_agent_id).items())[
      case
  ]
  before = db_session.query(Run).count()

  response = dash_http.fire(
      dash_client, _by_input(deps, button), values, changed=[button]
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  notifications = dash_http.body(response)["response"][NOTIFICATION_CONTAINER][
      "sendNotifications"
  ]
  # NotificationContainer takes a list of actions and drops a bare dict.
  assert isinstance(notifications, list), notifications
  assert notifications[0]["title"] == "Cannot Start Evaluation"
  assert "Creds Free" in notifications[0]["message"]

  db_session.expire_all()
  assert db_session.query(Run).count() == before
  assert not offline_gda.calls, offline_gda.calls
