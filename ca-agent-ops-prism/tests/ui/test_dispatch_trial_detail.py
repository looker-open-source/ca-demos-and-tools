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

"""The Trial Detail page, driven through Dash's HTTP dispatch route.

``render_trial_detail`` is fired by the URL and a store, so ``url_only`` keeps
it out of the sweep in ``test_callback_dispatch.py``, and the path Dash
registers for the page is ``/evaluations/trials/none``. Nothing below the
browser tier had ever loaded the page with a real trial id, which is where the
whole component tree gets built and serialized.

The page has five outputs (breadcrumbs, title, description, actions,
container) and the response names each one, so these read the slot they care
about rather than the whole body where that distinction matters.
"""

from __future__ import annotations
import datetime
from typing import Any
from unittest import mock
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.example import Example
from prism.server.models.run import Trial
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import EvaluationIds
from prism.ui.utils import run_status_display
import pytest
from tests.ui import dash_http


def _trials(db_session, run_id: int) -> list[Trial]:
  """The three trials the ``seeded`` fixture creates, in id order."""
  return (
      db_session.query(Trial).filter_by(run_id=run_id).order_by(Trial.id).all()
  )


def _add_result(
    db_session,
    trial: Trial,
    a_type: AssertionType,
    value: str,
    passed: bool,
    weight: float,
) -> None:
  """Gives ``trial`` one evaluated assertion.

  The snapshot hangs off the trial's example snapshot, because that is what
  ``AssertionResult.assertion`` resolves to and what the page renders from.
  """
  snapshot = AssertionSnapshot(
      example_snapshot_id=trial.example_snapshot_id,
      type=a_type,
      weight=weight,
      params={"value": value, "mode": "contains"},
  )
  db_session.add(snapshot)
  db_session.flush()
  db_session.add(
      AssertionResult(
          trial_id=trial.id,
          assertion_snapshot_id=snapshot.id,
          passed=passed,
          score=1.0 if passed else 0.0,
      )
  )
  db_session.commit()


def _render(
    dash_client,
    trial_id: int,
    search: str = "",
    sug_loading: bool = False,
):
  """Fires the trial page for ``trial_id`` and returns the response."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.TRIAL_DETAIL_CONTAINER}.children")
  return dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": f"/evaluations/trials/{trial_id}",
          "url.search": search,
          f"{EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL}.data": 0,
          f"{EvaluationIds.TRIAL_SUG_LOADING_STORE}.data": sug_loading,
      },
  )


def _slots(response) -> dict[str, Any]:
  """The output slots the response carries, keyed by component id."""
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"]


def _detail(response) -> Any:
  """The children of the trial detail container."""
  return _slots(response)[EvaluationIds.TRIAL_DETAIL_CONTAINER]["children"]


def _component(tree: Any, component_id: Any) -> dict[str, Any]:
  """The one serialized component in ``tree`` carrying ``component_id``.

  Searching the repr of the tree for an id or a style matches whatever else
  happens to share it, and this page has several hidden components.
  """
  found = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      props = node.get("props")
      if isinstance(props, dict) and props.get("id") == component_id:
        found.append(node)
      stack.extend(node.values())
  assert len(found) == 1, f"{component_id} appears {len(found)} times"
  return found[0]


def _card_icon(tree: Any, heading: str) -> dict[str, Any]:
  """The ThemeIcon of the stats card headed ``heading``.

  The cards carry no ids, and the icon alone does not tell them apart either:
  bi:activity is the Status card's and the Diagnostic metric card's. The
  heading sits beside the icon in one Group, so the pair is what finds it.

  Headings are not unique across the page, so ``tree`` is the caller's to
  narrow. "Accuracy" heads both a stats card and an assertion summary card.
  """
  found = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      if node.get("type") == "Group":
        children = node.get("props", {}).get("children")
        if isinstance(children, list) and any(
            isinstance(c, dict)
            and c.get("type") == "Text"
            and c.get("props", {}).get("children") == heading
            for c in children
        ):
          found += [
              c
              for c in children
              if isinstance(c, dict) and c.get("type") == "ThemeIcon"
          ]
      stack.extend(node.values())
  assert len(found) == 1, f"the {heading} card has {len(found)} icons"
  return found[0]


def _card_value(tree: Any, heading: str) -> Any:
  """The value the stats card headed ``heading`` prints.

  Same problem as ``_card_icon``: the cards carry no ids. The value is the
  Paper's second child, straight after the Group ``_card_icon`` finds, so the
  icon is what locates it. Searching the repr of the page for the value instead
  says nothing about which card printed it, and passes just as well when the
  card is not on screen at all.
  """
  icon = _card_icon(tree, heading)
  found = []
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      children = node.get("props", {}).get("children")
      if node.get("type") == "Paper" and isinstance(children, list):
        group = children[0]
        if isinstance(group, dict) and any(
            child is icon
            for child in group.get("props", {}).get("children", [])
        ):
          found.append(children[1]["props"]["children"])
      stack.extend(node.values())
  assert len(found) == 1, f"{heading} names {len(found)} cards"
  return found[0]


def _curate_callback(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """The callback behind the accept and reject buttons on a suggestion."""
  matches = [
      dep
      for dep in deps
      if EvaluationIds.INLINE_SUG_ADD_BTN in str(dep["inputs"])
  ]
  assert len(matches) == 1, f"expected one curate callback, got {len(matches)}"
  return matches[0]


def _polling_callback(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """The callback fired by the suggestion polling interval."""
  matches = [
      dep
      for dep in deps
      if any(
          i["id"] == EvaluationIds.TRIAL_SUG_POLLING_INTERVAL
          for i in dep["inputs"]
      )
  ]
  assert len(matches) == 1, f"expected one poller, got {len(matches)}"
  return matches[0]


def _polling_values(
    dep: dict[str, Any], trial_id: int, n_intervals: int
) -> dict[str, Any]:
  """One poll's worth of inputs, with the button the empty state renders."""
  return {
      f"{EvaluationIds.TRIAL_SUG_POLLING_INTERVAL}.n_intervals": n_intervals,
      "url.pathname": f"/evaluations/trials/{trial_id}",
      dash_http.address(dep["state"][1]): [("empty", None)],
  }


def _trigger_callback(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """The server-side callback behind the Suggest Assertions button.

  The same button drives a clientside callback that spins it before the server
  answers, and that one is not reachable from here.
  """
  matches = [
      dep
      for dep in deps
      if EvaluationIds.SUGGEST_BTN_TYPE in str(dep["inputs"])
      and EvaluationIds.TRIAL_SUG_POLLING_INTERVAL in dep["output"]
  ]
  assert len(matches) == 1, f"expected one trigger, got {len(matches)}"
  return matches[0]


def _filter_sync_callback(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """The callback writing the three assertion filters back into the URL."""
  matches = [
      dep
      for dep in deps
      if any(
          i["id"] == EvaluationIds.ASSERT_FILTER_CATEGORY for i in dep["inputs"]
      )
  ]
  assert len(matches) == 1, f"expected one filter sync, got {len(matches)}"
  return matches[0]


def _rendered_suggest_buttons(dep: dict[str, Any]) -> dict[str, list[Any]]:
  """Names the one Suggest button the empty state puts on screen.

  Both suggestion callbacks declare an ALL output over that button, and Dash
  counts the values they return against the components named here.
  """
  outputs = dash_http.outputs_grouping(dep["output"])
  wildcard = [o for o in outputs if isinstance(o["id"], dict)]
  assert len(wildcard) == 1, wildcard
  return {dash_http.address(wildcard[0]): ["empty"]}


def test_the_trial_page_fills_every_slot_over_http(
    dash_client, callback_errors, db_session, seeded
):
  """A real trial id has to produce a whole page, not a 500.

  The page path Dash registers is ``/evaluations/trials/none``, so every sweep
  above this stops at the id guard and the component tree below it has never
  been built or serialized outside a browser. All five outputs are checked
  because the callback returns them as one list, and a misordered return puts
  the wrong thing in each slot.
  """
  trial = _trials(db_session, seeded.run_id)[2]

  response = _render(dash_client, trial.id)
  slots = _slots(response)

  assert slots[EvaluationIds.TRIAL_TITLE]["children"] == f"Trial #{trial.id}"
  breadcrumbs = str(slots[EvaluationIds.TRIAL_BREADCRUMBS_CONTAINER])
  assert f"Run #{trial.run_id}" in breadcrumbs
  assert f"/evaluations/runs/{trial.run_id}" in breadcrumbs
  description = str(slots[EvaluationIds.TRIAL_DESCRIPTION])
  assert seeded.agent_name in description
  assert seeded.suite_name in description
  actions = str(slots[EvaluationIds.TRIAL_ACTIONS])
  assert f"/evaluations/trials/{trial.id}/trace" in actions
  detail = str(_detail(response))
  assert seeded.question in detail
  # The display label, not the raw enum name. The Status card used to print
  # the enum name for every status the old two-branch map did not know.
  assert run_status_display(trial.status)[1] in detail

  callback_errors.assert_none()


@pytest.mark.parametrize(
    "status,color,label",
    [
        (RunStatus.RUNNING, "blue", "In Progress"),
        (RunStatus.PAUSED, "yellow", "Paused"),
        (RunStatus.CANCELLED, "gray", "Cancelled"),
        (RunStatus.PENDING, "gray", "Pending"),
    ],
)
def test_the_status_card_names_every_status_it_can_be_given(
    dash_client, callback_errors, db_session, seeded, status, color, label
):
  """The Status card has to draw the four statuses the old map missed.

  It branched on COMPLETED and FAILED and let everything else fall through to
  grey with the raw enum name beside it, so a running trial got the colour
  that means nothing is happening. The card is the only thing on the page that
  says what state the trial is in.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  trial.status = status
  db_session.commit()

  children = _detail(_render(dash_client, trial.id))
  detail = str(children)

  assert _card_icon(children, "Status")["props"]["color"] == color
  assert label in detail
  assert status.value not in detail

  callback_errors.assert_none()


def test_an_unscored_trial_reads_as_na_not_zero(
    dash_client, callback_errors, db_session, seeded
):
  """A trial nothing scored must not report 0.0% accuracy.

  The seeded trials have no assertion results, so ``score`` is None and the
  card says N/A. Formatting the None as a percentage would read as a trial
  that ran and got everything wrong. Duration and TTFR are the same shape:
  both are None until the trial has timestamps, and both fall back to "-".
  """
  trial = _trials(db_session, seeded.run_id)[2]
  assert trial.score is None
  assert trial.duration_ms is None

  children = _detail(_render(dash_client, trial.id))

  stats = _component(children, EvaluationIds.TRIAL_DETAIL_STATS)
  assert _card_value(stats, "Accuracy") == "N/A"
  assert _card_value(stats, "Duration") == "-"
  assert _card_value(stats, "TTFR") == "-"

  callback_errors.assert_none()


def test_trial_stats_cards_format_duration_and_ttfr(
    dash_client, callback_errors, db_session, seeded
):
  """Duration matches the run list format and TTFR is in tenths of seconds."""
  trial = _trials(db_session, seeded.run_id)[2]
  start = datetime.datetime(2026, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
  trial.started_at = start
  trial.completed_at = start + datetime.timedelta(seconds=13, milliseconds=751)
  trial.trace_results = [
      {"timestamp": (start + datetime.timedelta(milliseconds=2713)).isoformat()}
  ]
  db_session.commit()

  children = _detail(_render(dash_client, trial.id))

  stats = _component(children, EvaluationIds.TRIAL_DETAIL_STATS)
  assert _card_value(stats, "Duration") == "0m 13s"
  assert _card_value(stats, "TTFR") == "2.7s"

  callback_errors.assert_none()


def test_a_failed_trial_says_why_instead_of_showing_assertions(
    dash_client, callback_errors, db_session, seeded
):
  """A FAILED trial reports the failure and suppresses the assertion UI.

  Nothing evaluated the assertions, so showing the table would report every
  one of them as not passed. The page instead names the stage it died at,
  renders the error card, badges the section Not Evaluated and hides the
  suggestions accordion, since there is no trace to suggest anything from.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  _add_result(
      db_session, trial, AssertionType.TEXT_CONTAINS, "never-run", True, 1.0
  )
  trial.status = RunStatus.FAILED
  trial.failed_stage = "execution"
  trial.error_message = "the agent returned nothing"
  trial.error_traceback = "Traceback (most recent call last):\n  seeded"
  db_session.commit()

  children = _detail(_render(dash_client, trial.id))
  detail = str(children)

  assert "Failed at: execution" in detail
  assert "the agent returned nothing" in detail
  assert "Assertions were not evaluated because the trial failed." in detail
  assert "Not Evaluated" in detail
  # The one assertion on the trial must not reach the table.
  assert "never-run" not in detail
  # The accordion stays in the tree, hidden, so the callbacks that write to it
  # keep their component.
  accordion = _component(children, EvaluationIds.TRIAL_SUG_ACCORDION)
  assert accordion["props"]["style"] == {"display": "none"}

  callback_errors.assert_none()


@pytest.mark.parametrize(
    "search,kept,dropped",
    [
        ("?assertion_status=failed", "beta-needle", "alpha-needle"),
        ("?assertion_status=passed", "alpha-needle", "beta-needle"),
        ("?assertion_category=accuracy", "alpha-needle", "beta-needle"),
        ("?assertion_category=diagnostic", "beta-needle", "alpha-needle"),
        ("?assertion_type=query-contains", "beta-needle", "alpha-needle"),
    ],
)
def test_the_assertion_filters_narrow_the_table(
    dash_client, callback_errors, db_session, seeded, search, kept, dropped
):
  """Each query-string filter has to drop the rows it excludes.

  The page reads its filter state only from the URL, so this is the whole
  filter. Two assertions go in that differ on all three axes at once: the
  accuracy one passed and is a text-contains, the diagnostic one failed and is
  a query-contains. A filter that ignored its parameter would keep both.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  _add_result(
      db_session, trial, AssertionType.TEXT_CONTAINS, "alpha-needle", True, 1.0
  )
  _add_result(
      db_session,
      trial,
      AssertionType.QUERY_CONTAINS,
      "beta-needle",
      False,
      0.0,
  )

  children = _detail(_render(dash_client, trial.id, search=search))
  detail = str(children)

  assert kept in detail
  assert dropped not in detail
  # The Selects echo the URL back, otherwise the controls read as unset while
  # the table is filtered.
  name, value = search.lstrip("?").split("=")
  select = {
      "assertion_status": EvaluationIds.ASSERT_FILTER_STATUS,
      "assertion_category": EvaluationIds.ASSERT_FILTER_CATEGORY,
      "assertion_type": EvaluationIds.ASSERT_FILTER_TYPE,
  }[name]
  assert _component(children, select)["props"]["value"] == value

  callback_errors.assert_none()


def test_the_empty_suggestions_state_still_carries_the_generate_button(
    dash_client, callback_errors, db_session, seeded
):
  """With no suggestions the accordion has to offer to generate some.

  The Suggest Assertions button exists only inside the empty state, so losing
  that branch removes the only way to ask for suggestions. Its id is
  pattern-matching, and the callbacks behind it address it by type and index.
  """
  trial = _trials(db_session, seeded.run_id)[2]

  children = _detail(_render(dash_client, trial.id))

  assert "No suggested assertions." in str(children)
  button = _component(
      children, {"type": EvaluationIds.SUGGEST_BTN_TYPE, "index": "empty"}
  )
  assert button["props"]["children"] == "Suggest Assertions"

  callback_errors.assert_none()


def test_the_loading_store_swaps_the_suggestions_for_skeletons(
    dash_client, callback_errors, db_session, seeded
):
  """While generation is in flight the section shows skeletons.

  ``trial-sug-loading-store`` is a State, so the only thing that reads it is a
  re-render of the page. If the branch stopped firing, clicking Generate would
  leave the empty state and its button on screen with nothing saying work had
  started.
  """
  trial = _trials(db_session, seeded.run_id)[2]

  detail = str(_detail(_render(dash_client, trial.id, sug_loading=True)))

  assert "Skeleton" in detail
  assert "Suggest Assertions" not in detail

  callback_errors.assert_none()


@pytest.mark.parametrize(
    "button,action,written",
    [
        (EvaluationIds.INLINE_SUG_ADD_BTN, "accept", 1),
        (EvaluationIds.INLINE_SUG_REJECT_BTN, "reject", 0),
    ],
)
def test_curating_a_suggestion_over_http_writes_and_notifies(
    dash_client,
    callback_errors,
    db_session,
    seeded,
    button,
    action,
    written,
):
  """Accept and reject share one callback and differ only by trigger.

  Which action runs comes out of the trigger's ``type`` and the suggestion id
  out of its ``index``, so both buttons go in as ALL inputs and only one is
  named as having changed. Reading the value lists instead would curate the
  first suggestion on the page whichever button was clicked. Both branches
  drop the suggestion; only accept writes an assertion onto the live example.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  suggestion = SuggestedAssertion(
      trial_id=trial.id,
      type=AssertionType.TEXT_CONTAINS,
      weight=1.0,
      params={"value": "suggested-needle", "mode": "contains"},
  )
  db_session.add(suggestion)
  db_session.commit()
  suggestion_id = suggestion.id
  example = (
      db_session.query(Example).filter_by(test_suite_id=seeded.suite_id).one()
  )
  assert not example.asserts

  deps = dash_http.dependencies(dash_client)
  dep = _curate_callback(deps)
  accept, reject = dep["inputs"]
  fired = accept if button == EvaluationIds.INLINE_SUG_ADD_BTN else reject

  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(accept): [(suggestion_id, 1)],
          dash_http.address(reject): [(suggestion_id, 1)],
      },
      changed=[dash_http.pattern_address(fired, suggestion_id)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  # NotificationContainer takes a list of actions and silently drops a bare
  # dict, so the toast only appears if this is a list.
  assert isinstance(notifications, list), notifications
  assert notifications[0]["title"] == "Suggestion Updated"
  assert f"was {action}ed" in notifications[0]["message"]
  # The signal is what re-renders the page without the suggestion.
  assert body[EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL]["data"]

  db_session.expire_all()
  assert db_session.get(SuggestedAssertion, suggestion_id) is None
  assert len(example.asserts) == written


def test_polling_stops_and_refreshes_once_the_suggestions_land(
    dash_client, callback_errors, db_session, seeded
):
  """The poll has to turn itself off when the work it waits on finishes.

  Nothing else disables the interval, so a poll that kept returning no_update
  would query the trial every three seconds for the life of the tab. The
  signal it returns is what re-renders the page with the new cards.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  db_session.add(
      SuggestedAssertion(
          trial_id=trial.id,
          type=AssertionType.TEXT_CONTAINS,
          weight=1.0,
          params={"value": "arrived", "mode": "contains"},
      )
  )
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = _polling_callback(deps)
  response = dash_http.fire(
      dash_client,
      dep,
      _polling_values(dep, trial.id, n_intervals=1),
      rendered=_rendered_suggest_buttons(dep),
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert body[EvaluationIds.TRIAL_SUG_POLLING_INTERVAL]["disabled"] is True
  assert body[EvaluationIds.TRIAL_SUG_UPDATE_SIGNAL]["data"]
  assert body[EvaluationIds.TRIAL_SUG_LOADING_STORE]["data"] is False


def test_polling_gives_up_rather_than_running_forever(
    dash_client, callback_errors, db_session, seeded
):
  """No suggestions after 20 ticks stops the poll and clears the skeletons.

  Generation runs in a worker thread that can die with nothing to report, so
  there is no signal the page could wait on. Without the cap the skeletons
  stay on screen and the poll runs until the tab closes. Tick 19 goes in too,
  because a cap that fired on every tick would also pass the assertion below.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  assert not trial.suggested_asserts

  deps = dash_http.dependencies(dash_client)
  dep = _polling_callback(deps)
  rendered = _rendered_suggest_buttons(dep)
  early = dash_http.fire(
      dash_client,
      dep,
      _polling_values(dep, trial.id, n_intervals=19),
      rendered=rendered,
  )
  timed_out = dash_http.fire(
      dash_client,
      dep,
      _polling_values(dep, trial.id, n_intervals=20),
      rendered=rendered,
  )

  # Every output is no_update while the poll keeps going. Dash still answers
  # 200, with nothing in the response map, so the count is what to assert on.
  assert early.status_code == 200, early.data[:2000]
  assert dash_http.body(early)["response"] == {}
  body = dash_http.body(timed_out)["response"]
  assert body[EvaluationIds.TRIAL_SUG_POLLING_INTERVAL]["disabled"] is True
  assert body[EvaluationIds.TRIAL_SUG_LOADING_STORE]["data"] is False

  callback_errors.assert_none()


def test_a_poll_that_cannot_read_the_trial_stops_polling(
    dash_client, callback_errors, db_session, seeded, monkeypatch
):
  """A failing poll must not keep failing every three seconds.

  ``get_trial`` raising is the case where the loop would otherwise log a
  traceback per tick forever. The callback catches it and disables the
  interval, so the page settles instead.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  client = mock.MagicMock()
  client.runs.get_trial.side_effect = RuntimeError("seeded failure")
  monkeypatch.setattr(evaluation_callbacks, "get_client", lambda: client)

  deps = dash_http.dependencies(dash_client)
  dep = _polling_callback(deps)
  response = dash_http.fire(
      dash_client,
      dep,
      _polling_values(dep, trial.id, n_intervals=1),
      rendered=_rendered_suggest_buttons(dep),
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)["response"]
  assert body[EvaluationIds.TRIAL_SUG_POLLING_INTERVAL]["disabled"] is True
  assert body[EvaluationIds.TRIAL_SUG_LOADING_STORE]["data"] is False
  # The callback catches the exception and logs it itself. Consume that one,
  # then require the gate to be empty: anything left means handle_errors caught
  # something the callback should have.
  callback_errors.assert_logged("Polling failed for trial")
  callback_errors.assert_none()


def test_clicking_generate_starts_the_poll(
    dash_client, callback_errors, db_session, seeded, monkeypatch
):
  """The button has to enable the interval, or nothing collects the result.

  Generation itself runs in a thread that builds a real GenAI client, so the
  client is replaced here. What is under test is the four values the callback
  returns, not the generation.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  client = mock.MagicMock()
  monkeypatch.setattr(evaluation_callbacks, "get_client", lambda: client)

  deps = dash_http.dependencies(dash_client)
  dep = _trigger_callback(deps)
  buttons = dep["inputs"][0]
  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(buttons): [("empty", 1)],
          "url.pathname": f"/evaluations/trials/{trial.id}",
      },
      changed=[dash_http.pattern_address(buttons, "empty")],
      rendered=_rendered_suggest_buttons(dep),
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  assert client.runs.regenerate_suggestions_async.call_args[0][0] == trial.id
  assert body[EvaluationIds.TRIAL_SUG_POLLING_INTERVAL]["disabled"] is False
  assert body[EvaluationIds.TRIAL_SUG_LOADING_STORE]["data"] is True


def test_a_trial_with_a_chart_renders_the_chart_section(
    dash_client, callback_errors, db_session, seeded
):
  """A vega-lite event in the trace has to reach the page as a chart.

  ``render_chart_carousel`` swallows a per-slide exception and returns None
  when no slide survives, so a spec it cannot build degrades to a section that
  is missing rather than to an error. Nothing above this looks for it.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  trial.trace_results = [{
      "timestamp": "2026-01-01T00:00:00Z",
      "system_message": {
          "chart": {
              "result": {
                  "vega_config": {
                      "mark": {"type": "bar"},
                      "description": "seeded-chart",
                  }
              }
          }
      },
  }]
  db_session.commit()

  detail = str(_detail(_render(dash_client, trial.id)))

  assert "GENERATED CHARTS" in detail
  assert "seeded-chart" in detail
  assert "dash_vega_components" in detail

  callback_errors.assert_none()


def test_a_trial_with_no_trace_says_there_is_no_profiling_data(
    dash_client, callback_errors, db_session, seeded
):
  """The profiling card has an empty state, and it has to render.

  ``tool_timings`` is derived from the trace, so a trial that never produced
  one has nothing to profile. Returning nothing there leaves a bare gap
  between the trial card and the assertions.
  """
  trial = _trials(db_session, seeded.run_id)[2]
  assert not trial.trace_results

  detail = str(_detail(_render(dash_client, trial.id)))

  assert "No profiling data available" in detail
  assert "GENERATED CHARTS" not in detail

  callback_errors.assert_none()


def test_changing_a_filter_writes_it_into_the_url_once(
    dash_client, callback_errors
):
  """The Selects write the URL, and rewriting the same URL would loop.

  ``render_trial_detail`` reads filter state only from the URL, so without
  this write the Selects look inert. The callback also writes ``url.search``,
  which is where its own inputs are rendered from, so it has to answer
  no_update once the three values already match, which comes back as a 200
  with nothing in it.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _filter_sync_callback(deps)
  values = {
      f"{EvaluationIds.ASSERT_FILTER_CATEGORY}.value": "accuracy",
      f"{EvaluationIds.ASSERT_FILTER_TYPE}.value": "all",
      f"{EvaluationIds.ASSERT_FILTER_STATUS}.value": "failed",
      "url.search": "",
  }

  response = dash_http.fire(dash_client, dep, values)
  assert response.status_code == 200, response.data[:2000]
  search = dash_http.body(response)["response"]["url"]["search"]
  assert "assertion_category=accuracy" in search
  assert "assertion_status=failed" in search
  assert "assertion_type=all" in search

  again = dash_http.fire(
      dash_client, dep, dict(values, **{"url.search": search})
  )

  assert again.status_code == 200, again.data[:2000]
  assert dash_http.body(again)["response"] == {}
  callback_errors.assert_none()
