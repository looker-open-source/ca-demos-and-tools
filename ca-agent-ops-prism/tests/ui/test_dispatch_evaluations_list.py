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

"""The /evaluations list: its filters, its archive switch and its modals.

Everything on this page is a server round trip. The filters write a query
string, the query string drives one callback that returns a table, and the
compare modal returns two lists of option dicts. A browser would add only the
portal animation, so the POST body is the whole contract.

``dash_http.find`` cannot address several of these, because three callbacks
write ``url.search`` and two write ``modal-compare-runs.opened``. They are
selected by the control that drives them instead.
"""

from __future__ import annotations
import dataclasses
import datetime
import json
import re
from typing import Any
from unittest import mock
from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
import pytest
from tests.ui import dash_http

_UTC = datetime.timezone.utc


def _by_input(deps: list[dict[str, Any]], address: str) -> dict[str, Any]:
  """Returns the one callback taking ``"<id>.<property>"`` as an input.

  ``dash_http.find`` addresses a callback by what it writes, and on this page
  that is ambiguous. The control that drives each one is not.
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


def _components(node: Any, type_name: str) -> list[dict[str, Any]]:
  """Every component of ``type_name`` in a serialized component tree."""
  found = []
  if isinstance(node, dict):
    if node.get("type") == type_name:
      found.append(node)
    for value in node.values():
      found.extend(_components(value, type_name))
  elif isinstance(node, list):
    for item in node:
      found.extend(_components(item, type_name))
  return found


def _run_rows(body: dict[str, Any]) -> dict[int, dict[str, Any]]:
  """The rendered table, keyed by the run each row links to.

  The "View Report" href is the only thing in a row that names its run, and
  the header row does not have one, so this drops it without special casing.
  """
  container = body["response"][EvaluationIds.RUN_LIST_CONTAINER]["children"]
  rows = {}
  for row in _components(container, "Tr"):
    ids = set(re.findall(r"/evaluations/runs/(\d+)", json.dumps(row)))
    if len(ids) == 1:
      rows[int(ids.pop())] = row
  return rows


def _list_runs(dash_client, search: str) -> dict[int, dict[str, Any]]:
  """Loads /evaluations with ``search`` and returns the rows it rendered."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.RUN_LIST_CONTAINER}.children")
  response = dash_http.fire_url(dash_client, dep, "/evaluations", search)
  assert response.status_code == 200, response.data[:2000]
  return _run_rows(dash_http.body(response))


@dataclasses.dataclass
class Extra:
  """A second agent and suite, plus a second run of the seeded suite."""

  agent_id: int
  agent_name: str
  suite_id: int
  suite_name: str
  run_id: int
  sibling_run_id: int


@pytest.fixture(name="extra")
def _extra(db_session, seeded) -> Extra:
  """Rows that a working filter has to leave out.

  ``seeded`` has one of everything, so any filter it is given matches it and a
  filter that does nothing at all still looks right. ``sibling_run_id`` is a
  second run of the seeded suite taken from a second snapshot of it, because
  the suite filter joins on ``original_suite_id`` while the run row carries
  ``test_suite_snapshot_id``. With one snapshot the two ids coincide.
  """
  agent_repo = AgentRepository(db_session)
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot_service = SnapshotService(db_session, suite_repo, example_repo)
  run_repo = RunRepository(db_session)

  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = agent_repo.create(name="Other Agent", config=config)
  suite = suite_repo.create(name="Other Suite")
  example_repo.create(suite.id, "How many other orders are there?")
  snapshot = snapshot_service.create_snapshot(suite.id)
  run = run_repo.create(snapshot.id, agent.id)
  run.status = RunStatus.COMPLETED

  sibling_snapshot = snapshot_service.create_snapshot(seeded.suite_id)
  sibling = run_repo.create(sibling_snapshot.id, agent.id)
  db_session.commit()

  return Extra(
      agent_id=agent.id,
      agent_name=agent.name,
      suite_id=suite.id,
      suite_name=suite.name,
      run_id=run.id,
      sibling_run_id=sibling.id,
  )


def _archive(db_session, run_id: int) -> None:
  """Archives a run, finishing it first.

  ``seeded`` leaves its run PENDING, and ``RunRepository.archive`` refuses
  that: an archived run drops out of every worker query, so archiving one
  mid-flight abandoned it. The page these tests read only ever shows a run that
  has already stopped.
  """
  db_session.get(Run, run_id).status = RunStatus.COMPLETED
  db_session.commit()
  RunRepository(db_session).archive(run_id)


def test_an_archived_run_leaves_the_list_and_comes_back_with_the_switch(
    dash_client, callback_errors, db_session, seeded, extra
):
  """Archiving is the only way to get a run off this page, and it must reverse.

  ``include_archived`` comes off ``?archived=true`` and nothing else, so a
  dropped parameter either hides the archived run for good or shows every
  archived run on the default view. The badge is the only thing telling the
  two lists apart once both runs are on screen.
  """
  _archive(db_session, seeded.run_id)
  callback_errors.assert_none()

  default = _list_runs(dash_client, "")
  assert seeded.run_id not in default
  assert extra.run_id in default

  archived = _list_runs(dash_client, "?archived=true")
  assert set(archived) >= {seeded.run_id, extra.run_id}
  assert "Archived" in json.dumps(archived[seeded.run_id])
  assert "Archived" not in json.dumps(archived[extra.run_id])
  callback_errors.assert_none()

  # The switch sends its own state, not a toggle, so an unchecked switch has
  # to take the parameter back out.
  assert _list_runs(dash_client, "?archived=false") == default


def _filter_cases(seeded, extra) -> list[tuple[str, set[int]]]:
  """Each filter's query string, and the runs it should leave on screen."""
  return [
      (f"?agent_id={seeded.agent_id}", {seeded.run_id}),
      (f"?suite_id={extra.suite_id}", {extra.run_id}),
      ("?status=COMPLETED", {extra.run_id}),
      (
          f"?suite_id={seeded.suite_id}",
          {seeded.run_id, extra.sibling_run_id},
      ),
  ]


@pytest.mark.parametrize("case", [0, 1, 2, 3])
def test_each_filter_narrows_the_list_to_the_runs_it_names(
    dash_client, callback_errors, seeded, extra, case
):
  """The filters are the only way to find a run once there are more than a page.

  ``render_run_list`` parses the query string itself and coerces the ids with
  ``int()`` and the status with ``RunStatus()``, so a renamed parameter is not
  an error. It is a filter that quietly matches everything. The last case is
  the suite one, which joins through the snapshot, and it names two runs taken
  from two different snapshots of the one suite.
  """
  search, expected = _filter_cases(seeded, extra)[case]

  rows = _list_runs(dash_client, search)

  callback_errors.assert_none(f"on {search}")
  assert set(rows) == expected, search


def test_the_suite_filter_offers_values_the_list_can_read_back(
    dash_client, callback_errors, seeded, extra
):
  """The options and the query string are built by two different callbacks.

  ``populate_eval_filter_options`` labels each suite by its
  ``original_suite_id`` and ``update_eval_url_from_filters`` writes whatever
  value it is handed straight into ``?suite_id=``. If either side changes which
  id it means, every suite filter silently returns nothing.
  """
  deps = dash_http.dependencies(dash_client)
  options = dash_http.body(
      dash_http.fire_url(
          dash_client,
          dash_http.find(deps, f"{EvaluationIds.FILTER_SUITE}.data"),
          "/evaluations",
      )
  )["response"]

  agents = options[EvaluationIds.FILTER_AGENT]["data"]
  assert {a["label"] for a in agents} == {seeded.agent_name, extra.agent_name}
  suites = {
      s["label"]: s["value"]
      for s in options[EvaluationIds.FILTER_SUITE]["data"]
  }
  assert set(suites) == {seeded.suite_name, extra.suite_name}

  search = dash_http.body(
      dash_http.fire(
          dash_client,
          _by_input(deps, f"{EvaluationIds.FILTER_SUITE}.value"),
          {
              f"{EvaluationIds.FILTER_SUITE}.value": suites[seeded.suite_name],
              "url.search": "",
          },
          changed=[f"{EvaluationIds.FILTER_SUITE}.value"],
      )
  )["response"]["url"]["search"]

  callback_errors.assert_none()
  assert search == f"?suite_id={seeded.suite_id}"
  assert set(_list_runs(dash_client, search)) == {
      seeded.run_id,
      extra.sibling_run_id,
  }


def test_changing_one_filter_keeps_the_rest_of_the_query_string(
    dash_client, callback_errors, seeded
):
  """The two writers of url.search each rebuild it from scratch.

  Both parse the current search, change their own keys and re-encode, so a
  writer that forgets to carry the rest drops the other's filter on every
  interaction. ``sync_eval_filters_to_url`` reads the same string back into the
  controls, and it is what makes a deep link show the filters it applied.
  """
  deps = dash_http.dependencies(dash_client)
  filters = _by_input(deps, f"{EvaluationIds.FILTER_AGENT}.value")
  switch = _by_input(deps, f"{EvaluationIds.SWITCH_ARCHIVED}.checked")

  with_archived = dash_http.body(
      dash_http.fire(
          dash_client,
          filters,
          {
              f"{EvaluationIds.FILTER_AGENT}.value": str(seeded.agent_id),
              "url.search": "?archived=true",
          },
          changed=[f"{EvaluationIds.FILTER_AGENT}.value"],
      )
  )["response"]["url"]["search"]
  assert f"agent_id={seeded.agent_id}" in with_archived
  assert "archived=true" in with_archived

  # Turning the switch off takes archived out and leaves the filter alone.
  without = dash_http.body(
      dash_http.fire(
          dash_client,
          switch,
          {
              f"{EvaluationIds.SWITCH_ARCHIVED}.checked": False,
              "url.search": with_archived,
          },
          changed=[f"{EvaluationIds.SWITCH_ARCHIVED}.checked"],
      )
  )["response"]["url"]["search"]
  assert without == f"?agent_id={seeded.agent_id}"

  # Clearing a filter has to remove its key, not write an empty one, or
  # render_run_list coerces "" and filters on nothing.
  cleared = dash_http.body(
      dash_http.fire(
          dash_client,
          filters,
          {
              f"{EvaluationIds.FILTER_AGENT}.value": None,
              "url.search": with_archived,
          },
          changed=[f"{EvaluationIds.FILTER_AGENT}.value"],
      )
  )["response"]["url"]["search"]
  assert cleared == "?archived=true"

  restored = dash_http.body(
      dash_http.fire(
          dash_client,
          dash_http.find(deps, f"{EvaluationIds.FILTER_AGENT}.value"),
          {"url.search": with_archived},
      )
  )["response"]
  callback_errors.assert_none()
  assert restored[EvaluationIds.FILTER_AGENT]["value"] == str(seeded.agent_id)
  assert restored[EvaluationIds.SWITCH_ARCHIVED]["checked"] is True


def test_restoring_a_run_unarchives_it_and_says_restored(
    dash_client, callback_errors, db_session, seeded
):
  """Restore and Archive are one callback that branches on which button fired.

  Over HTTP that branch is chosen by ``changedPropIds``, the same way a click
  chooses it. The else branch calls a different client method and builds a
  different message, and nothing else in the app can unarchive a run, so a
  mis-routed trigger archives the run again and reports success.
  """
  _archive(db_session, seeded.run_id)
  deps = dash_http.dependencies(dash_client)
  restore = _by_input(deps, f"{EvaluationIds.BTN_RESTORE}.n_clicks")

  response = dash_http.fire(
      dash_client,
      restore,
      {
          f"{EvaluationIds.BTN_RESTORE}.n_clicks": 1,
          "url.pathname": f"/evaluations/runs/{seeded.run_id}",
      },
      changed=[f"{EvaluationIds.BTN_RESTORE}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  # NotificationContainer takes a list of actions and drops a bare dict.
  assert isinstance(notifications, list), notifications
  assert notifications[0]["color"] == "green"
  assert notifications[0]["message"] == "Evaluation run restored successfully."

  # redirect-handler is refresh=True, so an href here would reload the page and
  # throw the toast away. The signal is what re-renders in place.
  assert REDIRECT_HANDLER not in body
  assert body[EvaluationIds.RUN_UPDATE_SIGNAL]["data"]["ts"] > 0

  db_session.expire_all()
  assert not db_session.get(Run, seeded.run_id).is_archived


def test_archiving_a_running_run_is_refused_in_words_the_reader_can_act_on(
    dash_client, callback_errors, db_session, seeded
):
  """A refusal the user can clear must not read like a crash.

  ``RunRepository.archive`` rejects a run that has not stopped, and the way out
  is the Cancel button next to Archive. The callback used to fold every
  exception into "Could not archive this run. The details are in the server
  log.", so the one failure with an answer looked like a bug and the run stayed
  on the list.
  """
  deps = dash_http.dependencies(dash_client)
  archive = _by_input(deps, f"{EvaluationIds.BTN_ARCHIVE}.n_clicks")

  response = dash_http.fire(
      dash_client,
      archive,
      {
          f"{EvaluationIds.BTN_ARCHIVE}.n_clicks": 1,
          "url.pathname": f"/evaluations/runs/{seeded.run_id}",
      },
      changed=[f"{EvaluationIds.BTN_ARCHIVE}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  # The refusal is a return value, not a raise, so handle_errors never sees it
  # and the generic toast never fires.
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  notification = body[NOTIFICATION_CONTAINER]["sendNotifications"][0]
  assert notification["color"] == "red"
  assert "Cancel it first" in notification["message"]
  assert "server log" not in notification["message"]

  db_session.expire_all()
  assert not db_session.get(Run, seeded.run_id).is_archived


def _run_schema(
    run_id: int,
    status: RunStatus,
    accuracy: float | None,
    duration_ms: int | None = None,
):
  """One row for the list table, carrying nothing but the score."""
  return RunSchema(
      id=run_id,
      test_suite_snapshot_id=1,
      agent_id=1,
      agent_name="Banded Agent",
      suite_name="Banded Suite",
      status=status,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=_UTC),
      accuracy=accuracy,
      duration_ms=duration_ms,
  )


_ACCURACY_ROWS = [
    # The bands are >= 90 green and >= 70 yellow, so both boundaries need the
    # value on each side of them.
    _run_schema(1, RunStatus.COMPLETED, 0.9),
    _run_schema(2, RunStatus.COMPLETED, 0.899),
    _run_schema(3, RunStatus.COMPLETED, 0.7),
    _run_schema(4, RunStatus.COMPLETED, 0.699),
    _run_schema(5, RunStatus.RUNNING, None),
    _run_schema(6, RunStatus.PENDING, 0.95),
    _run_schema(7, RunStatus.COMPLETED, None),
]


def test_the_accuracy_cell_reads_by_status_and_bands_the_bar(
    dash_client, callback_errors, monkeypatch
):
  """The accuracy cell is the one number anyone reads off this page.

  Three branches produce three different component types, and only the
  COMPLETED one carries a bar. A run still going has no accuracy to report yet,
  so reading its running average as a result is worse than saying nothing.
  Run 6 is the trap: it carries an accuracy but has not started, and its cell
  must stay N/A.

  The rows come from a stub client. Accuracy on a real run is an average over
  assertion result scores, and seeding four runs either side of two band
  boundaries through that says more about the seeding than about the cell.
  """
  client = mock.Mock()
  client.runs.list_runs.return_value = _ACCURACY_ROWS
  monkeypatch.setattr(evaluation_callbacks, "get_client", lambda: client)

  rows = _list_runs(dash_client, "")
  callback_errors.assert_none()
  assert set(rows) == {r.id for r in _ACCURACY_ROWS}

  bands = {}
  for run_id, row in rows.items():
    bars = _components(row, "Progress")
    bands[run_id] = bars[0]["props"]["color"] if bars else None

  assert bands == {
      1: "green",
      2: "yellow",
      3: "yellow",
      4: "red",
      5: None,
      6: None,
      7: None,
  }

  percentages = {
      run_id: re.findall(r"\d+\.\d%", json.dumps(row))
      for run_id, row in rows.items()
  }
  assert percentages[1] == ["90.0%"]
  assert percentages[2] == ["89.9%"]
  assert percentages[3] == ["70.0%"]
  assert percentages[4] == ["69.9%"]

  assert "Calculating..." in json.dumps(rows[5])
  for run_id in (6, 7):
    assert "N/A" in json.dumps(rows[run_id]), run_id
    assert "Calculating..." not in json.dumps(rows[run_id]), run_id


def _duration_cell(row: dict[str, Any]) -> str:
  """The text in a row's DURATION column.

  The cells carry no ids, so this goes by position. DURATION is the sixth of
  the eight the row renders, between ACCURACY and STARTED.
  """
  cells = row["props"]["children"]
  assert len(cells) == 8, f"the row has {len(cells)} cells, not 8"
  return cells[5]["props"]["children"]["props"]["children"]


_DURATION_ROWS = [
    _run_schema(11, RunStatus.PAUSED, None),
    _run_schema(12, RunStatus.PENDING, None),
    _run_schema(13, RunStatus.CANCELLED, None),
    _run_schema(14, RunStatus.RUNNING, None),
    _run_schema(15, RunStatus.COMPLETED, None, duration_ms=95_000),
]


def test_the_duration_cell_says_what_a_run_with_no_duration_is_doing(
    dash_client, callback_errors, monkeypatch
):
  """A run with no duration yet has to read as its status, not as "--".

  ``duration_ms`` stays None until ``completed_at`` is set, so a paused run, a
  queued run and a cancelled run all landed on the same dead "--". That is the
  cell people scan to tell a stuck run from a finished one. RUNNING keeps its
  own wording because it is the one case where work is in flight.
  """
  client = mock.Mock()
  client.runs.list_runs.return_value = _DURATION_ROWS
  monkeypatch.setattr(evaluation_callbacks, "get_client", lambda: client)

  rows = _list_runs(dash_client, "")
  callback_errors.assert_none()

  assert {run_id: _duration_cell(row) for run_id, row in rows.items()} == {
      11: "Paused",
      12: "Pending",
      13: "Cancelled",
      14: "Running...",
      15: "1m 35s",
  }


def test_the_list_admits_it_stopped_at_fifty(
    dash_client, callback_errors, monkeypatch
):
  """Past the cap the page has to say the list is cut, or the rest vanish.

  ``render_run_list`` asks for one row more than it draws and uses the extra
  only to decide whether to say so. Without the notice the 51st run reads as a
  run that does not exist, and the filters are the only way to reach it.
  """
  client = mock.Mock()
  client.runs.list_runs.return_value = [
      _run_schema(i, RunStatus.COMPLETED, 1.0) for i in range(1, 52)
  ]
  monkeypatch.setattr(evaluation_callbacks, "get_client", lambda: client)

  rows = _list_runs(dash_client, "")
  callback_errors.assert_none()

  assert client.runs.list_runs.call_args.kwargs["limit"] == 51
  assert len(rows) == 50
  assert 51 not in rows

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.RUN_LIST_CONTAINER}.children")
  rendered = json.dumps(
      dash_http.body(dash_http.fire_url(dash_client, dep, "/evaluations", ""))
  )
  assert "Showing the 50 most recent runs" in rendered

  # One row short of the cap is the whole list, and saying otherwise there
  # would send people filtering for runs that are already on screen.
  client.runs.list_runs.return_value = [
      _run_schema(i, RunStatus.COMPLETED, 1.0) for i in range(1, 51)
  ]
  exact = json.dumps(
      dash_http.body(dash_http.fire_url(dash_client, dep, "/evaluations", ""))
  )
  assert "Showing the 50 most recent runs" not in exact


def test_the_status_filter_offers_every_status_a_run_can_reach(
    dash_client, callback_errors, db_session, seeded, extra
):
  """The filter was a hand-written list of five and it had drifted.

  PAUSED was missing, so a paused run could not be filtered for and the
  "Running" option left it out without saying so. The options are built from
  RunStatus now, less the two that only a trial ever carries. Filtering for
  PAUSED is fired as well, because an option whose value the list cannot parse
  is the same bug one layer down.
  """
  deps = dash_http.dependencies(dash_client)
  page = dash_http.body(
      dash_http.fire_url(
          dash_client,
          dash_http.find(deps, "_pages_content.children"),
          "/evaluations",
      )
  )["response"]["_pages_content"]["children"]
  options = _select_data(page, EvaluationIds.FILTER_STATUS)

  assert {o["value"] for o in options} == {
      s.value
      for s in RunStatus
      if s not in (RunStatus.EXECUTING, RunStatus.EVALUATING)
  }
  # Spelled out, option by option, because the labels are the ones the status
  # badge draws and the filter and the column it filters cannot disagree about
  # what a status is called. Rederiving the labels from the options' own values
  # would compare the page against itself and hold under any pairing.
  assert options == [
      {"label": "Pending", "value": "PENDING"},
      {"label": "In Progress", "value": "RUNNING"},
      {"label": "Completed", "value": "COMPLETED"},
      {"label": "Failed", "value": "FAILED"},
      {"label": "Cancelled", "value": "CANCELLED"},
      {"label": "Paused", "value": "PAUSED"},
  ]

  db_session.get(Run, seeded.run_id).status = RunStatus.PAUSED
  db_session.commit()

  assert set(_list_runs(dash_client, "?status=PAUSED")) == {seeded.run_id}
  assert extra.run_id not in _list_runs(dash_client, "?status=PAUSED")
  callback_errors.assert_none()


def _select_data(tree: Any, component_id: str) -> list[dict[str, str]]:
  """The options of the one Select carrying ``component_id``."""
  found = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      if node.get("props", {}).get("id") == component_id:
        found.append(node)
      stack.extend(node.values())
  assert len(found) == 1, f"{component_id} appears {len(found)} times"
  return found[0]["props"]["data"]


def _option_ids(options: list[dict[str, str]]) -> set[int]:
  """The run ids behind a list of Select options."""
  return {int(o["value"]) for o in options}


def test_the_compare_modal_offers_only_runs_of_the_same_suite(
    dash_client, callback_errors, seeded, extra
):
  """Comparing two runs of different suites compares two different questions.

  The suite filter is the only thing stopping that, and it is applied twice:
  once when the modal opens from a run's own button, and again when the base
  select changes. The preselect matters too, because the button sits on the
  run being compared and that run has to arrive as the challenger.
  """
  deps = dash_http.dependencies(dash_client)
  toggle = _by_input(deps, f"{EvaluationIds.BTN_CANCEL_COMPARE}.n_clicks")
  pattern = next(
      i
      for i in toggle["inputs"]
      if EvaluationIds.BTN_OPEN_COMPARE_MODAL in dash_http.address(i)
  )

  response = dash_http.fire(
      dash_client,
      toggle,
      {dash_http.address(pattern): [(seeded.run_id, 1)]},
      changed=[dash_http.pattern_address(pattern, seeded.run_id)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  opened = dash_http.body(response)["response"]
  assert opened[EvaluationIds.MODAL_COMPARE_RUNS]["opened"] is True
  offered = _option_ids(opened[EvaluationIds.COMPARE_BASE_SELECT]["data"])
  assert offered == {seeded.run_id, extra.sibling_run_id}
  assert extra.run_id not in offered
  assert opened[EvaluationIds.COMPARE_CHALLENGE_SELECT]["value"] == str(
      seeded.run_id
  )
  assert opened[EvaluationIds.COMPARE_BASE_SELECT]["value"] is None

  # Picking a base from the other suite has to re-narrow the challengers, or
  # the list still holds the runs the modal opened with.
  narrowed = dash_http.body(
      dash_http.fire(
          dash_client,
          _by_input(deps, f"{EvaluationIds.COMPARE_BASE_SELECT}.value"),
          {f"{EvaluationIds.COMPARE_BASE_SELECT}.value": str(extra.run_id)},
      )
  )["response"]
  callback_errors.assert_none()
  assert _option_ids(
      narrowed[EvaluationIds.COMPARE_CHALLENGE_SELECT]["data"]
  ) == {extra.run_id}


def test_swap_and_compare_send_the_two_runs_in_the_order_on_screen(
    dash_client, callback_errors, seeded, extra
):
  """Base and challenger are not interchangeable on the comparison page.

  The page reads ``base_run_id`` as the thing being improved on, so a swap that
  does not swap, or an href built the wrong way round, reports every regression
  as a gain. Compare also closes the modal, and it must refuse to navigate with
  only one run picked.
  """
  deps = dash_http.dependencies(dash_client)
  swap = _by_input(deps, f"{EvaluationIds.BTN_SWAP_COMPARE_MODAL}.n_clicks")
  go = _by_input(deps, f"{EvaluationIds.BTN_GO_COMPARE}.n_clicks")

  swapped = dash_http.body(
      dash_http.fire(
          dash_client,
          swap,
          {
              f"{EvaluationIds.BTN_SWAP_COMPARE_MODAL}.n_clicks": 1,
              f"{EvaluationIds.COMPARE_BASE_SELECT}.value": str(seeded.run_id),
              f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.value": str(
                  extra.sibling_run_id
              ),
          },
          changed=[f"{EvaluationIds.BTN_SWAP_COMPARE_MODAL}.n_clicks"],
      )
  )["response"]
  assert swapped[EvaluationIds.COMPARE_BASE_SELECT]["value"] == str(
      extra.sibling_run_id
  )
  assert swapped[EvaluationIds.COMPARE_CHALLENGE_SELECT]["value"] == str(
      seeded.run_id
  )

  # Both outputs come back no_update, which Dash answers 200 with an empty
  # response rather than 204, so the refusal is only visible as a missing href.
  half_picked = dash_http.fire(
      dash_client,
      go,
      {
          f"{EvaluationIds.BTN_GO_COMPARE}.n_clicks": 1,
          f"{EvaluationIds.COMPARE_BASE_SELECT}.value": str(seeded.run_id),
      },
      changed=[f"{EvaluationIds.BTN_GO_COMPARE}.n_clicks"],
  )
  assert half_picked.status_code == 200, half_picked.data[:2000]
  assert dash_http.body(half_picked)["response"] == {}

  response = dash_http.fire(
      dash_client,
      go,
      {
          f"{EvaluationIds.BTN_GO_COMPARE}.n_clicks": 1,
          f"{EvaluationIds.COMPARE_BASE_SELECT}.value": str(
              extra.sibling_run_id
          ),
          f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.value": str(seeded.run_id),
      },
      changed=[f"{EvaluationIds.BTN_GO_COMPARE}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[REDIRECT_HANDLER]["href"] == (
      f"/compare?base_run_id={extra.sibling_run_id}"
      f"&challenger_run_id={seeded.run_id}"
  )
  assert body[EvaluationIds.MODAL_COMPARE_RUNS]["opened"] is False
