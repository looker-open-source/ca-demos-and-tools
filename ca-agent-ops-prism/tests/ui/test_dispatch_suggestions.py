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

"""Suggested assertions, from both places the app offers them.

The playground suggests them off a simulation and the trial page suggests them
off a finished run. They arrive as loose dicts in a store, and accepting one
turns it into a row in the assertions table. The interesting part is what has
to be stripped on the way, so these tests follow a suggestion all the way to
the database.

The simulation itself talks to an agent, so ``get_client`` is patched in the
callback module for the two tests that run one. Everything else is real.
"""

from __future__ import annotations

import json
import types
from typing import Any

from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.assertion import TextContains
from prism.server.models.assertion import Assertion
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.example import Example
from prism.server.models.run import Trial
from prism.server.repositories.example_repository import ExampleRepository
# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.callbacks import test_suite_questions_callbacks
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import EvaluationIds as Ev
from prism.ui.ids import TestSuiteIds as Ids
import pytest
from tests.ui import dash_http


def _callback(
    deps: list[dict[str, Any]], output: str, *inputs: str
) -> dict[str, Any]:
  """The one callback with this output and these Inputs, in order.

  Three callbacks write the trial suggestion signal and two write the builder
  store, all with allow_duplicate, so ``dash_http.find`` cannot address them by
  output. The Input side can.
  """
  matches = [
      dep
      for dep in deps
      if output in dep["output"]
      and len(dep["inputs"]) == len(inputs)
      and all(
          want in str(got["id"]) for want, got in zip(inputs, dep["inputs"])
      )
  ]
  assert len(matches) == 1, (
      f"expected one callback writing {output} from {list(inputs)}, found"
      f" {len(matches)}"
  )
  return matches[0]


def _values(response) -> dict[str, Any]:
  """The property values a 200 carries, keyed by ``<id>.<property>``.

  An output the callback returned no_update for is left out, so a missing key
  is the assertion that nothing was written.
  """
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def _example(db_session, suite_id: int) -> Example:
  """The one example the ``seeded`` fixture put in the suite."""
  return db_session.query(Example).filter_by(test_suite_id=suite_id).one()


def _trial(db_session, run_id: int) -> Trial:
  """The completed trial from the seeded run."""
  return (
      db_session.query(Trial).filter_by(run_id=run_id).order_by(Trial.id).all()
  )[-1]


def _suggest(db_session, trial_id: int, value: str, **extra) -> int:
  """One row in suggested_assertions, and its id.

  ``extra`` takes ``id`` so a test can force the collision with the assertions
  table, which has its own sequence.
  """
  row = SuggestedAssertion(
      trial_id=trial_id,
      type=AssertionType("text-contains"),
      weight=1.0,
      params={"value": value, "mode": "contains"},
      reasoning=f"the answer should mention {value}",
      **extra,
  )
  db_session.add(row)
  db_session.commit()
  return row.id


def _fake_client(monkeypatch, module, **attributes):
  """Points ``get_client`` in one callback module at a stub.

  tests/ui runs with PRISM_AGENT_BACKEND unset, so a real simulation would call
  the live agent.
  """
  client = types.SimpleNamespace(**attributes)
  monkeypatch.setattr(module, "get_client", lambda: client)


_RESULT = {
    "passed": False,
    "score": 0.5,
    "duration_ms": 1234,
    "response_text": "There are 9 seeded orders.",
    "error": None,
    "assertion_results": [
        {
            "passed": True,
            "score": 1.0,
            "reasoning": "found it",
            "assertion": {"type": "text-contains", "weight": 1.0},
        },
        {
            "passed": False,
            "score": 0.0,
            "reasoning": "missing",
            "assertion": {"type": "text-contains", "weight": 1.0},
        },
    ],
}

_SUGGESTIONS = [{
    "type": "text-contains",
    "value": "9",
    "weight": 1.0,
    "_checked": False,
    "_backend_index": 0,
}]


def test_a_finished_simulation_fills_the_result_and_suggestion_stores(
    dash_client, callback_errors, db_session, monkeypatch, seeded
):
  """Both stores are written by this one callback and by nothing else.

  The result store is what the assertion cards read their pass or fail marks
  from, and the suggestion store is what the Accept buttons act on. Leaving
  either at no_update shows a finished run with the previous run's marks still
  on it.
  """
  example = _example(db_session, seeded.suite_id)
  calls = []

  def run_simulation(agent_id, example_id):
    calls.append((agent_id, example_id))
    return types.SimpleNamespace(
        result_summary=_RESULT, suggestions_ui=_SUGGESTIONS
    )

  _fake_client(
      monkeypatch,
      test_suite_questions_callbacks,
      playground=types.SimpleNamespace(run_simulation=run_simulation),
  )

  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_SUGGESTIONS}.data", Ids.STORE_START_RUN)
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.STORE_START_RUN}.data": {"ts": 1},
          f"{Ids.STORE_BUILDER}.data": [
              {"id": example.id, "question": seeded.question, "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.TC_AGENT_SELECT}.value": str(seeded.agent_id),
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  # The agent comes off a dropdown as a string, and the client wants an int.
  assert calls == [(seeded.agent_id, example.id)]
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] == _RESULT
  assert values[f"{Ids.STORE_SUGGESTIONS}.data"] == _SUGGESTIONS
  assert values[f"{Ids.TC_RUN_BTN}.loading"] is False

  summary = str(values[f"{Ids.SIM_CONTEXT_CONTAINER}.children"])
  assert "1 of 2 assertions passed" in summary
  assert "1234ms" in summary
  assert "Accuracy: 50.0%" in summary


def test_a_failed_simulation_says_so_and_releases_the_run_button(
    dash_client, caplog, db_session, monkeypatch, seeded
):
  """The Run button spins until this callback answers, whatever it answers.

  Leaving loading set on the failure path locks the page: the button stays in
  its spinner and there is no second way to start a run. Both stores are
  cleared, so the previous run's badges and the suggestion skeleton do not sit
  under the error.

  caplog, not ``callback_errors``: the callback catches the failure itself and
  logs it with a bare ``logging.exception``, so it lands on the root logger and
  the "prism" handler never sees it.
  """
  example = _example(db_session, seeded.suite_id)

  def run_simulation(agent_id, example_id):
    del agent_id, example_id
    raise RuntimeError("seeded failure")

  _fake_client(
      monkeypatch,
      test_suite_questions_callbacks,
      playground=types.SimpleNamespace(run_simulation=run_simulation),
  )

  deps = dash_http.dependencies(dash_client)
  dep = _callback(deps, f"{Ids.STORE_SUGGESTIONS}.data", Ids.STORE_START_RUN)
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.STORE_START_RUN}.data": {"ts": 1},
          f"{Ids.STORE_BUILDER}.data": [
              {"id": example.id, "question": seeded.question, "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          f"{Ids.TC_AGENT_SELECT}.value": str(seeded.agent_id),
      },
  )

  assert response.status_code == 200, response.data[:2000]
  values = _values(response)

  alert = values[f"{Ids.SIM_CONTEXT_CONTAINER}.children"]
  assert alert["props"]["title"] == "Simulation Error"
  assert alert["props"]["color"] == "red"
  assert values[f"{Ids.TC_RUN_BTN}.loading"] is False
  assert values[f"{Ids.STORE_PLAYGROUND_RESULT}.data"] is None
  assert values[f"{Ids.STORE_SUGGESTIONS}.data"] is None

  assert any("Simulation failed" in r.getMessage() for r in caplog.records)


def _inline_state(example: Example, suite_id: int, suggestions, asserts=None):
  """The stores ``handle_inline_suggestion`` reads."""
  return {
      f"{Ids.STORE_SUGGESTIONS}.data": suggestions,
      f"{Ids.STORE_BUILDER}.data": [
          {"id": example.id, "question": "q", "asserts": asserts or []}
      ],
      f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      "url.pathname": f"/test_suites/edit/{suite_id}",
  }


def test_accepting_a_suggestion_writes_it_and_rejecting_only_drops_it(
    dash_client, callback_errors, db_session, seeded
):
  """Accept and Reject are one callback told apart by the id of the button.

  Accept has to reach the database. Reject must not, and both have to take the
  suggestion out of the store so the card disappears either way. Get the branch
  wrong and Reject writes the assertion the user just turned down.
  """
  example = _example(db_session, seeded.suite_id)
  suggestions = [
      {"type": "text-contains", "value": "accepted", "_checked": False},
      {"type": "text-contains", "value": "rejected", "_checked": False},
  ]

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.STORE_SUGGESTIONS}.data",
      Ids.INLINE_SUG_ADD_BTN,
      Ids.INLINE_SUG_REJECT_BTN,
  )
  accept_buttons, reject_buttons = dep["inputs"]

  def click(buttons, index, current):
    response = dash_http.fire(
        dash_client,
        dep,
        dict(
            _inline_state(example, seeded.suite_id, current),
            **{
                dash_http.address(accept_buttons): [
                    (i, 1 if buttons is accept_buttons and i == index else None)
                    for i in range(len(current))
                ],
                dash_http.address(reject_buttons): [
                    (i, 1 if buttons is reject_buttons and i == index else None)
                    for i in range(len(current))
                ],
            },
        ),
        changed=[dash_http.pattern_address(buttons, index)],
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  accepted = click(accept_buttons, 0, suggestions)
  assert [s["value"] for s in accepted[f"{Ids.STORE_SUGGESTIONS}.data"]] == [
      "rejected"
  ]
  saved = accepted[f"{Ids.STORE_BUILDER}.data"][0]["asserts"]
  assert [a["value"] for a in saved] == ["accepted"]
  # A suggestion is a suggestion, so accepting one means it counts.
  assert saved[0]["weight"] == 1

  db_session.expire_all()
  written = db_session.query(Assertion).filter_by(example_id=example.id).all()
  assert [a.params["value"] for a in written] == ["accepted"]

  rejected = click(reject_buttons, 0, [suggestions[1]])
  assert rejected[f"{Ids.STORE_SUGGESTIONS}.data"] == []
  assert f"{Ids.STORE_BUILDER}.data" not in rejected

  db_session.expire_all()
  written = db_session.query(Assertion).filter_by(example_id=example.id).all()
  assert [a.params["value"] for a in written] == ["accepted"]

  callback_errors.assert_none()


def test_an_accept_that_cannot_reach_a_test_case_leaves_the_card_alone(
    dash_client, callback_errors, db_session, seeded
):
  """An Accept that saved nothing still has to leave the card on screen.

  The drop from the suggestion store ran outside the accept branch, so an
  Accept with the selected index past the end of the builder store took the
  card off the page without writing the assertion. The suggestion was gone from
  the store and absent from the database, with nothing on screen to say so.
  Reject drops the card on its own, which the test above covers.
  """
  example = _example(db_session, seeded.suite_id)
  suggestion = {
      "type": "text-contains",
      "value": "stranded",
      "_checked": False,
  }

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.STORE_SUGGESTIONS}.data",
      Ids.INLINE_SUG_ADD_BTN,
      Ids.INLINE_SUG_REJECT_BTN,
  )
  accept_buttons, reject_buttons = dep["inputs"]

  response = dash_http.fire(
      dash_client,
      dep,
      dict(
          _inline_state(example, seeded.suite_id, [suggestion]),
          **{
              # One test case in the store, so row 3 is not there.
              f"{Ids.STORE_SELECTED_INDEX}.data": 3,
              dash_http.address(accept_buttons): [(0, 1)],
              dash_http.address(reject_buttons): [(0, None)],
          },
      ),
      changed=[dash_http.pattern_address(accept_buttons, 0)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)
  assert f"{Ids.STORE_SUGGESTIONS}.data" not in values, "dropped the card"
  assert f"{Ids.STORE_BUILDER}.data" not in values

  db_session.expire_all()
  assert not db_session.query(Assertion).filter_by(example_id=example.id).all()


def test_accepting_a_suggestion_drops_its_ui_only_fields(
    dash_client, callback_errors, db_session, seeded
):
  """The suggestion stores carry display metadata the schema will not take.

  ``_checked`` is the card's checkbox, ``_group_label`` is the run it came
  from. The assertion schemas set extra="forbid", so leaving one on turns
  Accept into a validation error and the suggestion is lost.
  """
  example = _example(db_session, seeded.suite_id)
  suggestion = {
      "type": "text-contains",
      "value": "orders",
      "mode": "contains",
      "_checked": True,
      "_backend_index": 0,
      "_trial_id": 7,
      "_group_label": "2026-01-01 - Seeded Agent (Run 1 Trial 7)",
  }

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ids.STORE_SUGGESTIONS}.data",
      Ids.INLINE_SUG_ADD_BTN,
      Ids.INLINE_SUG_REJECT_BTN,
  )
  accept_buttons, reject_buttons = dep["inputs"]

  response = dash_http.fire(
      dash_client,
      dep,
      dict(
          _inline_state(example, seeded.suite_id, [suggestion]),
          **{
              dash_http.address(accept_buttons): [(0, 1)],
              dash_http.address(reject_buttons): [(0, None)],
          },
      ),
      changed=[dash_http.pattern_address(accept_buttons, 0)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  saved = _values(response)[f"{Ids.STORE_BUILDER}.data"][0]["asserts"]
  assert [k for k in saved[0] if k.startswith("_")] == []
  assert saved[0]["value"] == "orders"

  db_session.expire_all()
  written = db_session.query(Assertion).filter_by(example_id=example.id).one()
  assert written.params["value"] == "orders"


def test_a_suggestion_from_history_is_added_next_to_the_assertions_there_are(
    dash_client, callback_errors, db_session, seeded
):
  """Suggestion ids and assertion ids come from different sequences.

  A suggested_assertions row id means nothing in the assertions table, and
  ``sync_suite`` updates by id. Carry the suggestion's id into the store and
  accepting it overwrites whatever assertion happens to sit at that id, so the
  user loses an assertion they wrote and gains nothing. This test forces the
  collision: the suggestion is given the id of the assertion already on the
  question.
  """
  example = _example(db_session, seeded.suite_id)
  repo = ExampleRepository(db_session)
  existing = repo.add_assertion(
      example.id, TextContains(type="text-contains", value="already here")
  )
  db_session.commit()
  trial = _trial(db_session, seeded.run_id)
  _suggest(db_session, trial.id, "suggested", id=existing.id)

  deps = dash_http.dependencies(dash_client)
  history = _callback(
      deps, f"{Ids.VAL_MSG}.children", Ids.TC_HISTORY_SUGGESTIONS_BTN
  )
  response = dash_http.fire(
      dash_client,
      history,
      {
          f"{Ids.TC_HISTORY_SUGGESTIONS_BTN}.n_clicks": 1,
          f"{Ids.STORE_BUILDER}.data": [
              {"id": example.id, "question": seeded.question, "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
      },
  )
  assert response.status_code == 200, response.data[:2000]
  values = _values(response)
  assert values[f"{Ids.VAL_MSG}.children"] == "", "the modal reported an error"

  offered = values[f"{Ids.STORE_HISTORY_SUGGESTIONS}.data"]
  assert [s["value"] for s in offered] == ["suggested"]
  assert "id" not in offered[0]
  assert "original_assertion_id" not in offered[0]
  assert offered[0]["_trial_id"] == trial.id

  dep = _callback(
      deps,
      f"{Ids.STORE_SUGGESTIONS}.data",
      Ids.INLINE_SUG_ADD_BTN,
      Ids.INLINE_SUG_REJECT_BTN,
  )
  accept_buttons, reject_buttons = dep["inputs"]
  accepted = dash_http.fire(
      dash_client,
      dep,
      dict(
          _inline_state(
              example,
              seeded.suite_id,
              offered,
              asserts=[{
                  "id": existing.id,
                  "type": "text-contains",
                  "value": "already here",
                  "weight": 1.0,
              }],
          ),
          **{
              dash_http.address(accept_buttons): [(0, 1)],
              dash_http.address(reject_buttons): [(0, None)],
          },
      ),
      changed=[dash_http.pattern_address(accept_buttons, 0)],
  )

  assert accepted.status_code == 200, accepted.data[:2000]
  callback_errors.assert_none()
  saved = _values(accepted)[f"{Ids.STORE_BUILDER}.data"][0]["asserts"]
  assert sorted(a["value"] for a in saved) == ["already here", "suggested"]

  db_session.expire_all()
  written = db_session.query(Assertion).filter_by(example_id=example.id).all()
  assert sorted(a.params["value"] for a in written) == [
      "already here",
      "suggested",
  ]


def test_a_failed_write_of_the_checked_suggestions_toasts_and_saves_nothing(
    dash_client, callback_errors, db_session, monkeypatch, seeded
):
  """A modal that closes is the user's only sign the suggestions were kept.

  ``confirm_suggestions`` wrapped its whole body in an except that logged and
  returned two no_updates. That ran before ``@handle_errors`` saw the
  ``_sync_suite`` raise, so a failed write closed the modal with nothing saved
  and no toast. The raise has to reach the decorator: the response carries the
  toast and neither output is written, which leaves the modal open.
  """
  example = _example(db_session, seeded.suite_id)
  suggestion = {"type": "text-contains", "value": "unsaved", "_checked": True}

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(test_suite_questions_callbacks, "get_client", boom)

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ids.SUGGESTION_MODAL}.opened", Ids.SUGGESTION_ADD_BTN
  )
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ids.SUGGESTION_ADD_BTN}.n_clicks": 1,
          f"{Ids.SUGGESTION_LIST}-group.value": [json.dumps(suggestion)],
          f"{Ids.STORE_BUILDER}.data": [
              {"id": example.id, "question": seeded.question, "asserts": []}
          ],
          f"{Ids.STORE_SELECTED_INDEX}.data": 0,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[f"{Ids.SUGGESTION_ADD_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  assert "sideUpdate" in dash_http.body(response), "the failure raised no toast"
  values = _values(response)
  assert f"{Ids.STORE_BUILDER}.data" not in values
  assert f"{Ids.SUGGESTION_MODAL}.opened" not in values, "closed on a failure"
  assert any("seeded failure" in m for m in callback_errors.messages)
  callback_errors.clear()

  db_session.expire_all()
  assert not db_session.query(Assertion).filter_by(example_id=example.id).all()


@pytest.mark.parametrize(
    "button,action,survives",
    [
        (Ev.INLINE_SUG_ADD_BTN, "accept", True),
        (Ev.INLINE_SUG_REJECT_BTN, "reject", False),
    ],
)
def test_curating_a_trial_suggestion_keeps_it_or_drops_it(
    dash_client,
    callback_errors,
    db_session,
    seeded,
    button,
    action,
    survives,
):
  """The trial page's Accept and Reject are one callback, split on the id.

  Both delete the suggestion, so the only difference visible afterwards is the
  assertion on the question. Reading the branch off the wrong key would reject
  what the user accepted, and the suggestion is gone either way.
  """
  example = _example(db_session, seeded.suite_id)
  trial = _trial(db_session, seeded.run_id)
  sug_id = _suggest(db_session, trial.id, "curated")

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data",
      Ev.INLINE_SUG_ADD_BTN,
      Ev.INLINE_SUG_REJECT_BTN,
  )
  accept_buttons, reject_buttons = dep["inputs"]
  fired = accept_buttons if button == Ev.INLINE_SUG_ADD_BTN else reject_buttons

  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(accept_buttons): [
              (sug_id, 1 if fired is accept_buttons else None)
          ],
          dash_http.address(reject_buttons): [
              (sug_id, 1 if fired is reject_buttons else None)
          ],
      },
      changed=[dash_http.pattern_address(fired, sug_id)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  notification = values[f"{NOTIFICATION_CONTAINER}.sendNotifications"][0]
  assert notification["message"] == f"The suggested assertion was {action}ed."
  # The signal is what makes the accordion reload without the suggestion.
  assert values[f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data"]

  db_session.expire_all()
  assert db_session.get(SuggestedAssertion, sug_id) is None
  written = db_session.query(Assertion).filter_by(example_id=example.id).all()
  assert [a.params["value"] for a in written] == (
      ["curated"] if survives else []
  )


def test_asking_for_new_suggestions_starts_the_poll_and_spins_the_button(
    dash_client, callback_errors, db_session, monkeypatch, seeded
):
  """Generation runs in a thread, so the page only learns about it by polling.

  The four outputs are the whole handshake: a signal, the button spinners, the
  loading flag and the interval. Leave the interval disabled and the page waits
  for a result that never arrives on its own.
  """
  trial_id = _trial(db_session, seeded.run_id).id
  calls = []
  _fake_client(
      monkeypatch,
      evaluation_callbacks,
      runs=types.SimpleNamespace(
          regenerate_suggestions_async=lambda tid, flask_app: calls.append(tid)
      ),
  )

  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data", Ev.SUGGEST_BTN_TYPE
  )
  buttons = dep["inputs"][0]
  loading = dash_http.address({
      "id": {"type": Ev.SUGGEST_BTN_TYPE, "index": ["ALL"]},
      "property": "loading",
  })

  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(buttons): [(0, 1)],
          "url.pathname": f"/evaluations/trials/{trial_id}",
      },
      changed=[dash_http.pattern_address(buttons, 0)],
      rendered={loading: [0]},
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  assert calls == [trial_id]
  assert values[f'{{"index":0,"type":"{Ev.SUGGEST_BTN_TYPE}"}}.loading'] is True
  assert values[f"{Ev.TRIAL_SUG_LOADING_STORE}.data"] is True
  assert values[f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.disabled"] is False
  assert values[f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.n_intervals"] == 0
  assert values[f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data"]


def test_the_suggestion_poll_stops_on_arrival_and_on_the_timeout(
    dash_client, callback_errors, db_session, seeded
):
  """Nothing else turns the interval off, so both exits have to do it.

  A poll that never stops keeps hitting the database every three seconds for
  as long as the tab is open. One that stops early leaves the button spinning
  over suggestions that did arrive.
  """
  trial = _trial(db_session, seeded.run_id)
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data", Ev.TRIAL_SUG_POLLING_INTERVAL
  )
  buttons = dep["state"][1]
  loading = dash_http.address({
      "id": {"type": Ev.SUGGEST_BTN_TYPE, "index": ["ALL"]},
      "property": "loading",
  })
  spinner = f'{{"index":0,"type":"{Ev.SUGGEST_BTN_TYPE}"}}.loading'

  def poll(n_intervals):
    response = dash_http.fire(
        dash_client,
        dep,
        {
            f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.n_intervals": n_intervals,
            "url.pathname": f"/evaluations/trials/{trial.id}",
            dash_http.address(buttons): [
                (0, {"type": Ev.SUGGEST_BTN_TYPE, "index": 0})
            ],
        },
        rendered={loading: [0]},
    )
    assert response.status_code == 200, response.data[:2000]
    return _values(response)

  waiting = poll(3)
  assert waiting == {}, "stopped polling before the suggestions arrived"

  timed_out = poll(20)
  assert timed_out[f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.disabled"] is True
  assert timed_out[spinner] is False
  assert timed_out[f"{Ev.TRIAL_SUG_LOADING_STORE}.data"] is False
  # The signal fires on the timeout too. render_trial_detail takes it as an
  # Input, so without it the skeleton the poll put up stayed on the page and
  # the panel read as still working.
  assert timed_out[f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data"]

  _suggest(db_session, trial.id, "arrived")
  arrived = poll(3)
  assert arrived[f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.disabled"] is True
  assert arrived[spinner] is False
  assert arrived[f"{Ev.TRIAL_SUG_LOADING_STORE}.data"] is False
  assert arrived[f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data"]

  callback_errors.assert_none()
