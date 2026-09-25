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

"""The comparison page's callbacks, driven through Dash's HTTP route.

Everything the compare page shows is derived text: a delta formatted into a
string, a badge color picked from a sign, a row built out of two runs' trials.
All of it comes back in the POST body, so none of it needs a browser.
``tests/e2e/test_run_comparison.py`` loads the page and asserts the trial list
text; the formatting, the counts and the picker wiring are pinned here.

The seeding helpers below build a suite snapshot and two runs over it. They
belong in ``tests/ui/conftest.py`` once a second file wants them.
"""

from __future__ import annotations
import dataclasses
import datetime
import json
from typing import Any, Iterator
import urllib.parse
import plotly.utils
from prism.client.comparison_client import ComparisonClient
from prism.common.schemas.assertion import AssertionType
from prism.common.schemas.execution import RunStatus

# By the module, because TestSuite carries no __test__ = False and importing
# the name into a test module makes pytest try to collect it.
from prism.server.models import suite as suite_models
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import ExampleSnapshot
from prism.server.models.snapshot import TestSuiteSnapshot
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import ComparisonIds
from prism.ui.pages import run_comparison
import pydantic
import pytest
from sqlalchemy import orm
from tests.ui import dash_http

# Every seeded timestamp is derived from this, so "newest first" is a fact
# about the rows and not about how fast the test ran.
_T0 = datetime.datetime(2026, 3, 1, 12, 0, tzinfo=datetime.timezone.utc)

_TEXT = AssertionType.TEXT_CONTAINS
_ROWS = AssertionType.DATA_CHECK_ROW_COUNT
_JUDGE = AssertionType.AI_JUDGE

# Each assertion type validates its own params, so a snapshot cannot be seeded
# with an empty one.
_PARAMS = {
    _TEXT: {"value": "orders"},
    _ROWS: {"value": 3},
    _JUDGE: {"value": "The answer names the row count."},
}


@dataclasses.dataclass
class _Side:
  """One run's half of a comparison case."""

  scores: dict[AssertionType, float]
  duration_ms: int = 1000
  status: RunStatus = RunStatus.COMPLETED
  error_message: str | None = None


@dataclasses.dataclass
class _Case:
  """One test case, as the two runs saw it.

  ``base`` or ``challenger`` is None for a case only one of the runs has a
  trial for, which is the shape a comparison across a suite edit takes.
  """

  logical_id: str
  base: _Side | None
  challenger: _Side | None

  @property
  def question(self) -> str:
    return f"How many {self.logical_id} orders are there?"


@dataclasses.dataclass
class _Comparison:
  """The ids the seeded comparison is addressed by."""

  suite_id: int
  base_run_id: int
  challenger_run_id: int
  base_trials: dict[str, int]
  challenger_trials: dict[str, int]

  def search(self, **extra: Any) -> str:
    """The compare URL's query string for these two runs."""
    params = {
        ComparisonIds.URL_BASE_RUN_ID: self.base_run_id,
        ComparisonIds.URL_CHALLENGER_RUN_ID: self.challenger_run_id,
    }
    params.update(extra)
    return "?" + urllib.parse.urlencode(params)


def _seed_agent(session: orm.Session, name: str = "Compare Agent") -> Agent:
  """An agent for runs to belong to."""
  agent = Agent(name=name, project_id="p", location="l", agent_resource_id="r")
  session.add(agent)
  session.flush()
  return agent


def _seed_snapshot(session: orm.Session, name: str) -> TestSuiteSnapshot:
  """A suite and a frozen copy of it, the way starting a run does."""
  suite = suite_models.TestSuite(name=name, description="Seeded.", tags={})
  session.add(suite)
  session.flush()

  snapshot = TestSuiteSnapshot(
      name=name,
      description="Seeded.",
      tags={},
      original_suite_id=suite.id,
  )
  session.add(snapshot)
  session.flush()
  return snapshot


def _seed_run(
    session: orm.Session,
    agent: Agent,
    snapshot: TestSuiteSnapshot,
    *,
    created_at: datetime.datetime = _T0,
    context: dict[str, Any] | None = None,
) -> Run:
  """One completed run of the snapshot."""
  run = Run(
      agent_id=agent.id,
      test_suite_snapshot_id=snapshot.id,
      status=RunStatus.COMPLETED,
      agent_context_snapshot=context,
      created_at=created_at,
  )
  session.add(run)
  session.flush()
  return run


def _seed_trial(
    session: orm.Session,
    run: Run,
    example: ExampleSnapshot,
    asserts: dict[AssertionType, AssertionSnapshot],
    side: _Side,
) -> Trial:
  """One trial, with an assertion result per score the side carries."""
  trial = Trial(
      run_id=run.id,
      example_snapshot_id=example.id,
      status=side.status,
      output_text=f"{run.id} answered {example.logical_id}.",
      error_message=side.error_message,
      started_at=_T0,
      completed_at=_T0 + datetime.timedelta(milliseconds=side.duration_ms),
  )
  session.add(trial)
  session.flush()

  for assertion_type, score in side.scores.items():
    session.add(
        AssertionResult(
            trial_id=trial.id,
            assertion_snapshot_id=asserts[assertion_type].id,
            passed=score >= 0.5,
            score=score,
            reasoning=f"{assertion_type.value} scored {score}.",
        )
    )
  session.flush()
  return trial


def _seed_comparison(
    session: orm.Session,
    cases: list[_Case],
    *,
    suite_name: str = "Comparison Suite",
    base_context: dict[str, Any] | None = None,
    challenger_context: dict[str, Any] | None = None,
) -> _Comparison:
  """Seeds two runs over one snapshot and returns what addresses them.

  Both runs share the snapshot, so the assertions align by content and a case
  is NEW or REMOVED exactly when one side has no trial for it.
  """
  agent = _seed_agent(session)
  snapshot = _seed_snapshot(session, suite_name)
  base_run = _seed_run(
      session, agent, snapshot, created_at=_T0, context=base_context
  )
  challenger_run = _seed_run(
      session,
      agent,
      snapshot,
      created_at=_T0 + datetime.timedelta(hours=1),
      context=challenger_context,
  )

  base_trials: dict[str, int] = {}
  challenger_trials: dict[str, int] = {}
  for case in cases:
    example = ExampleSnapshot(
        snapshot_suite_id=snapshot.id,
        question=case.question,
        logical_id=case.logical_id,
    )
    session.add(example)
    session.flush()

    asserts = {}
    for side in (case.base, case.challenger):
      for assertion_type in side.scores if side else {}:
        if assertion_type in asserts:
          continue
        assertion = AssertionSnapshot(
            example_snapshot_id=example.id,
            type=assertion_type,
            weight=1.0,
            params=_PARAMS[assertion_type],
        )
        session.add(assertion)
        session.flush()
        asserts[assertion_type] = assertion

    if case.base:
      trial = _seed_trial(session, base_run, example, asserts, case.base)
      base_trials[case.logical_id] = trial.id
    if case.challenger:
      trial = _seed_trial(
          session, challenger_run, example, asserts, case.challenger
      )
      challenger_trials[case.logical_id] = trial.id

  session.commit()
  return _Comparison(
      suite_id=snapshot.original_suite_id,
      base_run_id=base_run.id,
      challenger_run_id=challenger_run.id,
      base_trials=base_trials,
      challenger_trials=challenger_trials,
  )


# The four cases the render tests share. The numbers are chosen so every
# metric on the page is a round string: accuracy +12.5%, latency -50ms, one
# regression, one improvement, two unchanged.
_RENDERED_CASES = [
    _Case(
        "stable",
        base=_Side({_TEXT: 1.0, _ROWS: 1.0}),
        challenger=_Side({_TEXT: 1.0, _ROWS: 1.0}, duration_ms=950),
    ),
    # The regression is on text-contains, not on the row count. The
    # diagnostic table sorts regressions first and then by the alignment key,
    # and a snapshot carrying no original_assertion_id falls back to
    # "content-<type>-<value>" for that key. "data-check-row-count" sorts
    # ahead of "text-contains" there, so regressing the row count would come
    # out first with the regression term dropped as well as with it.
    _Case(
        "regressed",
        base=_Side({_TEXT: 1.0, _ROWS: 1.0}),
        challenger=_Side({_TEXT: 0.0, _ROWS: 1.0}, duration_ms=950),
    ),
    _Case(
        "improved",
        base=_Side({_TEXT: 0.0, _ROWS: 0.0}),
        challenger=_Side({_TEXT: 1.0, _ROWS: 1.0}, duration_ms=950),
    ),
    _Case(
        "untouched",
        base=_Side({_TEXT: 1.0, _ROWS: 0.0}),
        # The AI judge runs only on the candidate, and scores halfway, so the
        # case's own score is unmoved.
        challenger=_Side({_TEXT: 1.0, _ROWS: 0.0, _JUDGE: 0.5}, 950),
    ),
]


@pytest.fixture(name="compared")
def _compared(db_session: orm.Session) -> _Comparison:
  """Two runs of one suite, with a case in each comparison bucket."""
  return _seed_comparison(db_session, _RENDERED_CASES)


def _walk(fragment: Any) -> Iterator[dict[str, Any]]:
  """Every serialized component in a response fragment, in document order."""
  if isinstance(fragment, list):
    for item in fragment:
      yield from _walk(item)
  elif isinstance(fragment, dict):
    if "type" in fragment and "props" in fragment:
      yield fragment
      yield from _walk(fragment["props"])
    else:
      for value in fragment.values():
        yield from _walk(value)


def _of_type(fragment: Any, type_name: str) -> list[dict[str, Any]]:
  """The components of one type, in document order."""
  return [c for c in _walk(fragment) if c["type"] == type_name]


def _labels(fragment: Any, type_name: str) -> list[str]:
  """The text of each component of one type that renders a bare string."""
  return [
      c["props"]["children"]
      for c in _of_type(fragment, type_name)
      if isinstance(c["props"].get("children"), str)
  ]


def _compare_page(client, search: str = "") -> dict[str, Any]:
  """Loads /compare and returns the response keyed by component id."""
  deps = dash_http.dependencies(client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  response = dash_http.fire_url(client, dep, "/compare", search)
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"]


def _picker(client, search: str = "", suite_value: str | None = None):
  """Fires the dropdown-populating callback and returns the response."""
  deps = dash_http.dependencies(client)
  dep = dash_http.find(deps, f"{ComparisonIds.SUITE_SELECT}.data")
  return dash_http.fire(
      client,
      dep,
      {
          f"{ComparisonIds.LOC_URL}.pathname": "/compare",
          f"{ComparisonIds.LOC_URL}.search": search,
          f"{ComparisonIds.SUITE_SELECT}.value": suite_value,
      },
  )


def _modal(client, button: str, values: dict[str, Any]):
  """Fires the select-runs modal callback as if ``button`` was clicked."""
  deps = dash_http.dependencies(client)
  dep = dash_http.find(deps, f"{ComparisonIds.SELECT_RUNS_MODAL}.opened")
  return dash_http.fire(
      client,
      dep,
      dict(values, **{f"{button}.n_clicks": 1}),
      changed=[f"{button}.n_clicks"],
  )


def _row_for(rows: list[Any], question: str) -> dict[str, Any]:
  """The rendered comparison row for one case, found by its question."""
  matches = [row for row in rows if question in json.dumps(row)]
  assert len(matches) == 1, f"{len(matches)} rows mention {question!r}"
  return matches[0]


def _arrows(row: Any) -> list[dict[str, Any]]:
  """The before-and-after arrows in a comparison row's accuracy column."""
  return [
      icon
      for icon in _of_type(row, "DashIconify")
      if icon["props"]["icon"] == "material-symbols:arrow-right-alt"
  ]


def _headline(row: Any, column: str) -> list[str]:
  """The text under one of a comparison row's two right-hand labels.

  The accuracy and latency columns are Stacks of the same shape, each headed
  by its own label, so the label is what tells them apart.
  """
  for stack in _of_type(row, "Stack"):
    labels = _labels(stack, "Text")
    if labels and labels[0] == column:
      return labels[1:]
  raise AssertionError(f"the row has no {column!r} column")


def _bar_heights(chart: Any) -> list[str]:
  """The height of each bar in the performance delta chart, left to right.

  The bars are the only boxes in the chart carrying a marginTop, which is what
  keeps a zero-delta bar centred on the midline.
  """
  return [
      box["props"]["style"]["height"]
      for box in _of_type(chart, "Box")
      if "marginTop" in (box["props"].get("style") or {})
  ]


def test_the_picker_offers_every_run_of_the_suite_newest_first(
    dash_client, callback_errors, db_session
):
  """The two run dropdowns list the chosen suite's runs, most recent first.

  Both dropdowns are filled from the same list, so a base run and a challenger
  run are always drawn from the same suite. Ordering is the whole usefulness of
  the list: the run someone wants to compare against is nearly always the last
  one.
  """
  agent = _seed_agent(db_session)
  wanted = _seed_snapshot(db_session, "Wanted Suite")
  other = _seed_snapshot(db_session, "Other Suite")
  runs = [
      _seed_run(
          db_session,
          agent,
          wanted,
          created_at=_T0 + datetime.timedelta(hours=hour),
      )
      for hour in range(3)
  ]
  decoy = _seed_run(db_session, agent, other)
  db_session.commit()

  response = _picker(dash_client, suite_value=str(wanted.original_suite_id))
  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]

  suites = body[ComparisonIds.SUITE_SELECT]["data"]
  assert {s["label"] for s in suites} == {"Wanted Suite", "Other Suite"}

  base = body[ComparisonIds.BASE_RUN_SELECT]["data"]
  assert [o["value"] for o in base] == [str(r.id) for r in reversed(runs)]
  assert str(decoy.id) not in {o["value"] for o in base}
  assert body[ComparisonIds.CHALLENGE_RUN_SELECT]["data"] == base


def test_a_run_the_list_leaves_out_is_offered_when_the_url_names_it(
    dash_client, callback_errors, db_session
):
  """A URL naming a run the dropdown omits must not open onto a list without it.

  Two runs are left out here. One is older than the 50 the list is capped at.
  The other is archived, which drops it from the listing whatever its date.
  The callback looks each named run up and appends it, so both are offered
  only because the URL asked for them.

  The archived one is the newest run of the suite, and that is what makes the
  re-sort visible. It is appended at the end and sorted back to the top. A run
  below the window belongs at the end either way, so pinning one of those on
  its own says nothing about the sort.
  """
  agent = _seed_agent(db_session)
  snapshot = _seed_snapshot(db_session, "Busy Suite")
  runs = [
      _seed_run(
          db_session,
          agent,
          snapshot,
          created_at=_T0 + datetime.timedelta(hours=hour),
      )
      for hour in range(51)
  ]
  archived = _seed_run(
      db_session,
      agent,
      snapshot,
      created_at=_T0 + datetime.timedelta(hours=100),
  )
  archived.is_archived = True
  db_session.commit()
  oldest = runs[0]

  capped = dash_http.body(
      _picker(dash_client, suite_value=str(snapshot.original_suite_id))
  )["response"][ComparisonIds.BASE_RUN_SELECT]["data"]
  assert len(capped) == 50, "the window moved; the rest of this test assumes 50"
  offered = {o["value"] for o in capped}
  assert str(oldest.id) not in offered
  assert str(archived.id) not in offered

  pinned = dash_http.body(
      _picker(
          dash_client,
          search=(
              f"?{ComparisonIds.URL_BASE_RUN_ID}={oldest.id}"
              f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}={archived.id}"
          ),
          suite_value=str(snapshot.original_suite_id),
      )
  )["response"][ComparisonIds.BASE_RUN_SELECT]["data"]

  callback_errors.assert_none()
  assert [o["value"] for o in pinned] == [str(archived.id)] + [
      str(r.id) for r in reversed(runs)
  ]


def test_the_picker_infers_the_suite_from_the_runs_in_the_url(
    dash_client, callback_errors, db_session
):
  """A compare link carries no suite id, so the picker has to work it out.

  ``evaluation_callbacks`` builds /compare?base_run_id=..&challenger_run_id=..
  and nothing else, so without the inference the dropdowns open empty on every
  link the product itself hands out.
  """
  agent = _seed_agent(db_session)
  wanted = _seed_snapshot(db_session, "Wanted Suite")
  other = _seed_snapshot(db_session, "Other Suite")
  base = _seed_run(db_session, agent, wanted)
  challenger = _seed_run(
      db_session, agent, wanted, created_at=_T0 + datetime.timedelta(hours=1)
  )
  decoy = _seed_run(db_session, agent, other)
  db_session.commit()

  search = (
      f"?{ComparisonIds.URL_BASE_RUN_ID}={base.id}"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}={challenger.id}"
  )
  body = dash_http.body(_picker(dash_client, search=search))["response"]

  callback_errors.assert_none()
  offered = {o["value"] for o in body[ComparisonIds.BASE_RUN_SELECT]["data"]}
  assert offered == {str(base.id), str(challenger.id)}
  assert str(decoy.id) not in offered


def test_opening_the_modal_infers_the_suite_from_the_runs_in_the_url(
    dash_client, callback_errors, db_session
):
  """The modal pre-selects what the URL is already showing.

  Same inference as the picker above and a separate copy of it, on the other
  side of the modal. Opening the modal on a comparison and finding the suite
  blank is how someone loses the two runs they were looking at.
  """
  agent = _seed_agent(db_session)
  snapshot = _seed_snapshot(db_session, "Modal Suite")
  base = _seed_run(db_session, agent, snapshot)
  challenger = _seed_run(
      db_session, agent, snapshot, created_at=_T0 + datetime.timedelta(hours=1)
  )
  db_session.commit()

  search = (
      f"?{ComparisonIds.URL_BASE_RUN_ID}={base.id}"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}={challenger.id}"
  )
  response = _modal(
      dash_client,
      ComparisonIds.BTN_OPEN_SELECT_RUNS,
      {f"{ComparisonIds.LOC_URL}.search": search},
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]
  assert body[ComparisonIds.SELECT_RUNS_MODAL]["opened"] is True
  assert body[ComparisonIds.SUITE_SELECT]["value"] == str(
      snapshot.original_suite_id
  )
  assert body[ComparisonIds.BASE_RUN_SELECT]["value"] == str(base.id)
  assert body[ComparisonIds.CHALLENGE_RUN_SELECT]["value"] == str(challenger.id)


def test_opening_the_modal_keeps_the_two_runs_it_just_pre_filled(
    dash_client, callback_errors, db_session
):
  """The pre-fill above, and then what Dash does with it.

  Writing SUITE_SELECT.value fires ``populate_run_selects``, which reads a
  suite it did not write as the user having picked another suite and cleared
  both run values. So the modal opened on a comparison, showed the two runs
  for one frame, and then emptied itself. The test above fires the one
  callback and cannot see it. This one carries the first response into the
  second call, the way the browser does.
  """
  agent = _seed_agent(db_session)
  snapshot = _seed_snapshot(db_session, "Chained Suite")
  base = _seed_run(db_session, agent, snapshot)
  challenger = _seed_run(
      db_session, agent, snapshot, created_at=_T0 + datetime.timedelta(hours=1)
  )
  db_session.commit()

  search = (
      f"?{ComparisonIds.URL_BASE_RUN_ID}={base.id}"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}={challenger.id}"
  )
  opened = dash_http.body(
      _modal(
          dash_client,
          ComparisonIds.BTN_OPEN_SELECT_RUNS,
          {f"{ComparisonIds.LOC_URL}.search": search},
      )
  )["response"]

  deps = dash_http.dependencies(dash_client)
  chained = dash_http.fire(
      dash_client,
      dash_http.find(deps, f"{ComparisonIds.SUITE_SELECT}.data"),
      {
          f"{ComparisonIds.LOC_URL}.pathname": "/compare",
          f"{ComparisonIds.LOC_URL}.search": search,
          f"{ComparisonIds.SUITE_SELECT}.value": opened[
              ComparisonIds.SUITE_SELECT
          ]["value"],
          f"{ComparisonIds.BASE_RUN_SELECT}.value": opened[
              ComparisonIds.BASE_RUN_SELECT
          ]["value"],
          f"{ComparisonIds.CHALLENGE_RUN_SELECT}.value": opened[
              ComparisonIds.CHALLENGE_RUN_SELECT
          ]["value"],
      },
      changed=[f"{ComparisonIds.SUITE_SELECT}.value"],
  )

  assert chained.status_code == 200, chained.data[:2000]
  callback_errors.assert_none()
  written = dash_http.body(chained)["response"]
  # An output left at no_update is absent, and the field keeps the value the
  # modal put in it.
  assert "value" not in written[ComparisonIds.BASE_RUN_SELECT], written[
      ComparisonIds.BASE_RUN_SELECT
  ]["value"]
  assert "value" not in written[ComparisonIds.CHALLENGE_RUN_SELECT]
  offered = {o["value"] for o in written[ComparisonIds.BASE_RUN_SELECT]["data"]}
  assert offered == {str(base.id), str(challenger.id)}


def test_apply_builds_the_comparison_url_and_cancel_leaves_it_alone(
    dash_client, callback_errors
):
  """Apply is the only thing that writes the comparison into the URL.

  The URL is the page's whole state, so what Apply puts in LOC_URL.search is
  what the comparison is. Cancel shares the callback and must close the modal
  without writing anything, which over HTTP means no entry for LOC_URL at all.
  """
  selected = {
      f"{ComparisonIds.SUITE_SELECT}.value": "7",
      f"{ComparisonIds.BASE_RUN_SELECT}.value": "11",
      f"{ComparisonIds.CHALLENGE_RUN_SELECT}.value": "12",
  }

  applied = _modal(dash_client, ComparisonIds.BTN_APPLY_SELECT_RUNS, selected)
  assert applied.status_code == 200, applied.data[:2000]
  body = dash_http.body(applied)["response"]
  assert body[ComparisonIds.SELECT_RUNS_MODAL]["opened"] is False
  assert urllib.parse.parse_qs(
      body[ComparisonIds.LOC_URL]["search"].lstrip("?")
  ) == {
      ComparisonIds.URL_SUITE_ID: ["7"],
      ComparisonIds.URL_BASE_RUN_ID: ["11"],
      ComparisonIds.URL_CHALLENGER_RUN_ID: ["12"],
  }

  cancelled = _modal(dash_client, ComparisonIds.BTN_CLOSE_SELECT_RUNS, selected)
  assert cancelled.status_code == 200, cancelled.data[:2000]
  body = dash_http.body(cancelled)["response"]
  assert body[ComparisonIds.SELECT_RUNS_MODAL]["opened"] is False
  assert ComparisonIds.LOC_URL not in body

  callback_errors.assert_none()


@pytest.mark.parametrize(
    "missing",
    [ComparisonIds.BASE_RUN_SELECT, ComparisonIds.CHALLENGE_RUN_SELECT],
)
def test_apply_with_one_run_unchosen_does_nothing(
    dash_client, callback_errors, missing
):
  """Half a comparison is not a comparison, so Apply declines.

  One bare ``no_update`` covers all five outputs, so the modal stays open, the
  URL is untouched and nothing is said. That is the behavior: a silent no-op,
  not an error and not a message.
  """
  selected = {
      f"{ComparisonIds.SUITE_SELECT}.value": "7",
      f"{ComparisonIds.BASE_RUN_SELECT}.value": "11",
      f"{ComparisonIds.CHALLENGE_RUN_SELECT}.value": "12",
  }
  selected[f"{missing}.value"] = None

  response = _modal(dash_client, ComparisonIds.BTN_APPLY_SELECT_RUNS, selected)

  assert response.status_code == 200, response.data[:2000]
  assert dash_http.body(response)["response"] == {}
  callback_errors.assert_none()


def test_the_first_visit_shows_the_call_to_action(dash_client, callback_errors):
  """With no runs in the URL the page is the empty state and nothing else.

  The layout ships EMPTY_STATE hidden, so this callback is the only thing that
  reveals it, and the two sections it hides are the ones that would otherwise
  render blank cards over the invitation to pick two runs.
  """
  body = _compare_page(dash_client)

  callback_errors.assert_none()
  assert body[ComparisonIds.EMPTY_STATE]["style"] == {"display": "block"}
  assert body[ComparisonIds.SUMMARY_SECTION]["style"] == {"display": "none"}
  assert body[ComparisonIds.CONTEXT_DIFF_ACCORDION]["style"] == {
      "display": "none"
  }
  assert body[ComparisonIds.METRICS_CARDS]["children"] == []
  assert body[ComparisonIds.COMPARISON_LIST]["children"] == []
  assert body[ComparisonIds.CONTEXT_DIFF_BADGE]["children"] == "CONTEXT DIFF"
  assert body[ComparisonIds.CONTEXT_DIFF_BADGE]["color"] == "gray"
  assert _labels(
      body[ComparisonIds.CONTEXT_DIFF_CONTENT]["children"], "Text"
  ) == ["Select two runs to compare their configurations."]


def test_the_empty_state_icon_asks_for_a_color_the_browser_knows():
  """DashIconify hands its color prop straight to the SVG.

  It resolves no Mantine token, so c="dimmed" spelled as color="dimmed" named
  no color at all. The 80px glyph over "No runs selected" inherited the body
  text's black and read as the loudest thing on an empty page.
  """
  layout = json.loads(
      json.dumps(run_comparison.layout(), cls=plotly.utils.PlotlyJSONEncoder)
  )

  icons = [
      icon
      for icon in _of_type(layout, "DashIconify")
      if icon["props"]["icon"] == "material-symbols:compare"
  ]
  assert len(icons) == 1, "the empty state icon is gone"
  color = icons[0]["props"]["color"]
  assert color.startswith("var(--") or color.startswith("#"), color


def test_the_metric_cards_report_the_comparison(
    dash_client, callback_errors, compared
):
  """The four headline numbers, their signs and the words beside them.

  The service computes the deltas and is unit-tested on them. What is here is
  the formatting and the sign-driven color: a latency delta rendered with the
  wrong sign or captioned "Faster" while it went up is a card that reads as the
  opposite of the truth.
  """
  body = _compare_page(dash_client, compared.search())

  callback_errors.assert_none()
  cards = body[ComparisonIds.METRICS_CARDS]["children"]
  reported = {}
  for card in cards:
    title, value, caption = _labels(card, "Text")[:3]
    reported[title] = (value, caption, _of_type(card, "ThemeIcon")[0])

  assert reported["Accuracy Delta"][:2] == ("+12.5%", "Accuracy Gain")
  assert reported["Accuracy Delta"][2]["props"]["color"] == "green"
  assert reported["Avg Latency Delta"][:2] == ("-50ms", "Faster")
  assert reported["Avg Latency Delta"][2]["props"]["color"] == "green"
  assert reported["Regressions"][:2] == ("1", "Cases impacted")
  assert reported["Regressions"][2]["props"]["color"] == "red"
  assert reported["Improvements"][:2] == ("1", "Cases improved")
  assert reported["Improvements"][2]["props"]["color"] == "green"


def test_two_runs_that_scored_the_same_report_no_change(
    dash_client, callback_errors, db_session
):
  """Zero is neither direction, and the two signed cards used to fold it in.

  Re-running an agent nobody touched is the commonest comparison there is. The
  accuracy card took its >= 0 branch and the latency card its else, so the
  headline read "+0.0% Accuracy Gain" in green over "+0ms Faster" in green: a
  page reporting an improvement to somebody checking that nothing had moved.
  """
  comparison = _seed_comparison(
      db_session,
      [
          _Case(
              "first", base=_Side({_TEXT: 1.0}), challenger=_Side({_TEXT: 1.0})
          ),
          _Case(
              "second", base=_Side({_TEXT: 0.0}), challenger=_Side({_TEXT: 0.0})
          ),
      ],
  )

  body = _compare_page(dash_client, comparison.search())

  callback_errors.assert_none()
  reported = {}
  for card in body[ComparisonIds.METRICS_CARDS]["children"]:
    title, value, caption = _labels(card, "Text")[:3]
    reported[title] = (value, caption, _of_type(card, "ThemeIcon")[0])

  assert reported["Accuracy Delta"][:2] == ("+0.0%", "No change")
  assert reported["Accuracy Delta"][2]["props"]["color"] == "gray"
  assert reported["Avg Latency Delta"][:2] == ("+0ms", "No change")
  assert reported["Avg Latency Delta"][2]["props"]["color"] == "gray"


def test_the_excluded_trials_note_sits_beside_the_header_not_inside_it(
    dash_client, callback_errors, db_session
):
  """The note is a block under the header, not a third item in its row.

  The header is a flex dmc.Group of run pills. Appending the Alert to its
  children laid the note out alongside them, on one line and squeezed into
  whatever width was left, with its mt="md" between columns doing nothing.
  """
  ok = _Side({_TEXT: 1.0})
  comparison = _seed_comparison(
      db_session,
      [
          _Case("shared", base=ok, challenger=ok),
          _Case(
              "broken",
              base=ok,
              challenger=_Side({_TEXT: 1.0}, error_message="agent timed out"),
          ),
      ],
  )

  subtitle = _compare_page(dash_client, comparison.search())[
      ComparisonIds.SUBTITLE_TEXT
  ]["children"]

  callback_errors.assert_none()
  assert [child["type"] for child in subtitle] == ["Group", "Alert"]
  header, alert = subtitle
  assert not _of_type(header["props"]["children"], "Alert")
  assert "excluded from latency" in alert["props"]["children"]


def test_the_filter_bar_counts_each_bucket_and_marks_the_active_one(
    dash_client, callback_errors, db_session
):
  """Five near-identical buttons, each of which has to count its own cases.

  The chips are one renderer called five times, so the failure mode is a chip
  carrying its neighbor's count or staying unlit when its filter is the active
  one. Seeded with a different number of cases in every bucket, so two counts
  swapped is two wrong numbers rather than none. The counts also have to agree
  with the list below them, which is why the filtered row is asserted here too.

  The added case is what the Other chip is for. Regressed, Improved and
  Unchanged name three statuses out of seven, and the four chips used to add
  up to less than the number on All with no chip selecting the difference.
  """
  comparison = _seed_comparison(
      db_session,
      [
          _Case(
              "regressed",
              base=_Side({_TEXT: 1.0}),
              challenger=_Side({_TEXT: 0.0}),
          ),
          _Case(
              "improved-one",
              base=_Side({_TEXT: 0.0}),
              challenger=_Side({_TEXT: 1.0}),
          ),
          _Case(
              "improved-two",
              base=_Side({_TEXT: 0.0}),
              challenger=_Side({_TEXT: 1.0}),
          ),
          _Case(
              "stable-one",
              base=_Side({_TEXT: 1.0}),
              challenger=_Side({_TEXT: 1.0}),
          ),
          _Case(
              "stable-two",
              base=_Side({_TEXT: 1.0}),
              challenger=_Side({_TEXT: 1.0}),
          ),
          _Case(
              "stable-three",
              base=_Side({_TEXT: 1.0}),
              challenger=_Side({_TEXT: 1.0}),
          ),
          _Case("added", base=None, challenger=_Side({_TEXT: 1.0})),
      ],
  )

  body = _compare_page(dash_client, comparison.search())
  counted = {
      button["props"]["id"]: _labels(button, "Badge")[0]
      for button in _of_type(
          body[ComparisonIds.FILTER_BAR]["children"], "Button"
      )
  }

  callback_errors.assert_none()
  assert counted == {
      ComparisonIds.FILTER_ALL: "7",
      ComparisonIds.FILTER_REGRESSIONS: "1",
      ComparisonIds.FILTER_IMPROVEMENTS: "2",
      ComparisonIds.FILTER_UNCHANGED: "3",
      ComparisonIds.FILTER_OTHER: "1",
  }
  # The four read as a breakdown of the number on All, so they have to add up
  # to it. Anything they leave out is reachable under All and nowhere else.
  assert sum(
      int(counted[chip])
      for chip in (
          ComparisonIds.FILTER_REGRESSIONS,
          ComparisonIds.FILTER_IMPROVEMENTS,
          ComparisonIds.FILTER_UNCHANGED,
          ComparisonIds.FILTER_OTHER,
      )
  ) == int(counted[ComparisonIds.FILTER_ALL])

  other = _compare_page(
      dash_client, comparison.search(**{ComparisonIds.URL_FILTER: "OTHER"})
  )
  rows = other[ComparisonIds.COMPARISON_LIST]["children"]
  assert len(rows) == 1, rows
  assert "How many added orders are there?" in json.dumps(rows[0])

  filtered = _compare_page(
      dash_client, comparison.search(**{ComparisonIds.URL_FILTER: "REGRESSION"})
  )
  variants = {
      button["props"]["id"]: button["props"]["variant"]
      for button in _of_type(
          filtered[ComparisonIds.FILTER_BAR]["children"], "Button"
      )
  }
  assert variants[ComparisonIds.FILTER_REGRESSIONS] == "filled"
  assert variants[ComparisonIds.FILTER_ALL] == "subtle"
  # By the row, not by the count. A filter that matches nothing renders one
  # "No cases found matching filters." line, which is also a list of length
  # one.
  rows = filtered[ComparisonIds.COMPARISON_LIST]["children"]
  assert len(rows) == 1, rows
  assert "How many regressed orders are there?" in json.dumps(rows[0])


@pytest.mark.parametrize(
    "button,expected",
    [
        (ComparisonIds.FILTER_REGRESSIONS, "REGRESSION"),
        (ComparisonIds.FILTER_IMPROVEMENTS, "IMPROVED"),
        (ComparisonIds.FILTER_UNCHANGED, "STABLE"),
        (ComparisonIds.FILTER_OTHER, "OTHER"),
        (ComparisonIds.FILTER_ALL, None),
    ],
)
def test_each_filter_button_writes_its_own_status(
    dash_client, callback_errors, button, expected
):
  """Clicking a filter rewrites the URL, keeping the two runs in it.

  The filter lives in the URL so the view can be linked to, which means every
  chip has to carry the run ids through. All clears the filter rather than
  naming one, and OTHER is no case's status: it selects everything the three
  named buckets leave out. The page starts on STABLE here so no chip can pass
  by leaving the search string alone.
  """
  deps = dash_http.dependencies(dash_client)
  synchronize = [
      dep
      for dep in deps
      if any(i["id"] == ComparisonIds.FILTER_UNCHANGED for i in dep["inputs"])
  ]
  assert len(synchronize) == 1, f"expected one filter callback, {synchronize}"

  current = (
      f"?{ComparisonIds.URL_SUITE_ID}=7"
      f"&{ComparisonIds.URL_BASE_RUN_ID}=11"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}=12"
      f"&{ComparisonIds.URL_FILTER}=STABLE"
  )
  response = dash_http.fire(
      dash_client,
      synchronize[0],
      {
          f"{ComparisonIds.LOC_URL}.search": current,
          f"{button}.n_clicks": 1,
      },
      changed=[f"{button}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  written = dash_http.body(response)["response"][ComparisonIds.LOC_URL][
      "search"
  ]
  wanted = {
      ComparisonIds.URL_SUITE_ID: ["7"],
      ComparisonIds.URL_BASE_RUN_ID: ["11"],
      ComparisonIds.URL_CHALLENGER_RUN_ID: ["12"],
  }
  if expected:
    wanted[ComparisonIds.URL_FILTER] = [expected]
  assert urllib.parse.parse_qs(written.lstrip("?")) == wanted


@pytest.mark.parametrize("changed", [True, False])
def test_the_context_diff_badge_reports_whether_the_config_moved(
    dash_client, callback_errors, db_session, changed
):
  """The badge is the only summary of whether the agent was reconfigured.

  A comparison is only about the agent if its context held still, so the badge
  is what says which kind of comparison this is. The diff underneath has to be
  base against challenger in that order: the other way round and every addition
  reads as a removal.
  """
  comparison = _seed_comparison(
      db_session,
      [_Case("only", base=_Side({_TEXT: 1.0}), challenger=_Side({_TEXT: 1.0}))],
      base_context={"model": "gemini-1.5"},
      challenger_context={"model": "gemini-2.0" if changed else "gemini-1.5"},
  )

  body = _compare_page(dash_client, comparison.search())

  callback_errors.assert_none()
  badge = body[ComparisonIds.CONTEXT_DIFF_BADGE]
  if not changed:
    assert (badge["children"], badge["color"]) == (
        "No changes detected",
        "gray",
    )
    return

  assert (badge["children"], badge["color"]) == ("Changes detected", "orange")
  diff = body[ComparisonIds.CONTEXT_DIFF_CONTENT]["children"]
  removed = [
      row
      for row in _of_type(diff, "Tr")
      if "gemini-1.5" in json.dumps(row["props"]["children"])
  ]
  assert len(removed) == 1, "the baseline's context is not on the removed side"
  assert "-" in _labels(removed[0], "Td")


@pytest.mark.parametrize(
    "only,badge,absent",
    [("challenger", "ADDED", "base"), ("base", "REMOVED", "challenger")],
)
def test_a_case_only_one_run_ran_reads_as_added_or_removed(
    dash_client, callback_errors, db_session, only, badge, absent
):
  """A case with no counterpart has no delta, and the row must say so.

  Editing a suite between two runs produces these. There is no before-and-after
  to show, so the accuracy column reads N/A and the missing run's column reads
  N/A instead of rendering an empty answer card that looks like the agent said
  nothing.
  """
  side = _Side({_TEXT: 1.0})
  comparison = _seed_comparison(
      db_session,
      [
          _Case("shared", base=side, challenger=side),
          _Case(
              "lopsided",
              base=side if only == "base" else None,
              challenger=side if only == "challenger" else None,
          ),
      ],
  )

  rows = _compare_page(dash_client, comparison.search())[
      ComparisonIds.COMPARISON_LIST
  ]["children"]
  row = _row_for(rows, "How many lopsided orders are there?")

  callback_errors.assert_none()
  assert _labels(row, "Badge")[0] == badge
  columns = dict(zip(("base", "challenger"), _of_type(row, "GridCol")))
  assert "N/A" in _labels(columns[absent], "Text")
  assert not _of_type(columns[absent], "Markdown")
  assert _of_type(columns[only], "Markdown"), "the run that ran has no answer"
  # The before-and-after scores are joined by an arrow, so the arrow is what
  # says the accuracy column is showing a change at all.
  assert not _arrows(row), "a one-sided case still shows a score change"
  assert _arrows(_row_for(rows, "How many shared orders are there?"))


def test_a_case_only_one_run_ran_reports_no_latency_either(
    dash_client, callback_errors, db_session
):
  """The latency column has the same nothing to report as the accuracy one.

  duration_delta is None for a case with one trial, and ``or 0`` turned that
  into "+0ms" in the neutral gray the small deltas use. A question added to
  the suite between the two runs therefore claimed the two runs had taken the
  same time over it, next to an accuracy column already reading N/A.
  """
  side = _Side({_TEXT: 1.0})
  comparison = _seed_comparison(
      db_session,
      [
          _Case("shared", base=side, challenger=side),
          _Case("added", base=None, challenger=side),
      ],
  )

  rows = _compare_page(dash_client, comparison.search())[
      ComparisonIds.COMPARISON_LIST
  ]["children"]

  callback_errors.assert_none()
  added = _row_for(rows, "How many added orders are there?")
  assert _headline(added, "LATENCY") == ["N/A"]
  assert _headline(added, "Accuracy Change") == ["N/A"]
  # The shared case still reports one, so this is the one-sided branch and not
  # the column having stopped rendering.
  assert _headline(
      _row_for(rows, "How many shared orders are there?"), "LATENCY"
  ) == ["+0ms"]


def test_the_diagnostic_accordion_puts_the_regressed_assertion_first(
    dash_client, callback_errors, compared
):
  """Per-case assertion diagnostics: the count, and what is at the top.

  The table is sorted so a regressed assertion is the first thing in it, which
  is the only reason to open the accordion. The badge on the control is how
  many there are, and it is absent when there are none, so the row does not
  claim 0 regressions.
  """
  body = _compare_page(dash_client, compared.search())
  rows = body[ComparisonIds.COMPARISON_LIST]["children"]

  callback_errors.assert_none()
  regressed = _of_type(
      _row_for(rows, "How many regressed orders are there?"), "Accordion"
  )[0]
  assert regressed["props"]["id"] == {
      "type": ComparisonIds.TrialDiagnostic.ACCORDION,
      "index": "regressed",
  }
  assert "1 Regressions" in _labels(regressed, "Badge")

  # Text Contains is the one that regressed, and it is the one that sorts
  # second on the fallback alignment key, so this order is the regressions
  # first term and nothing else.
  table = _of_type(regressed, "Tbody")[0]["props"]["children"]
  assert [
      (_labels(tr, "Text")[0], _labels(tr, "Badge")[0]) for tr in table
  ] == [
      ("Text Contains", "REGRESSED"),
      ("Data Check Row Count", "STABLE"),
  ]

  stable = _of_type(
      _row_for(rows, "How many stable orders are there?"), "Accordion"
  )[0]
  assert not [b for b in _labels(stable, "Badge") if "Regressions" in b]


@pytest.mark.parametrize(
    "status,linked",
    [
        (RunStatus.COMPLETED, True),
        (RunStatus.FAILED, True),
        (RunStatus.CANCELLED, True),
        (RunStatus.RUNNING, False),
        (RunStatus.PENDING, False),
    ],
)
def test_only_a_finished_trial_offers_links_to_itself(
    dash_client, callback_errors, db_session, status, linked
):
  """A trial page for a trial that has not run yet has nothing on it.

  The gate is the trial's status, not the run's, because a comparison can be
  opened while the candidate is still going. The baseline side is finished in
  every case here, so an anchor appearing on both sides or neither would show
  up as the gate being ignored.
  """
  comparison = _seed_comparison(
      db_session,
      [
          _Case(
              "watched",
              base=_Side({_TEXT: 1.0}),
              challenger=_Side({_TEXT: 1.0}, status=status),
          )
      ],
  )

  body = _compare_page(dash_client, comparison.search())
  row = body[ComparisonIds.COMPARISON_LIST]["children"][0]
  base_column, challenger_column = _of_type(row, "GridCol")

  callback_errors.assert_none()
  base_id = comparison.base_trials["watched"]
  assert [
      (a["props"]["children"], a["props"]["href"])
      for a in _of_type(base_column, "Anchor")
  ] == [
      ("View Trial", f"/evaluations/trials/{base_id}"),
      ("View Trace", f"/evaluations/trials/{base_id}/trace"),
  ]

  challenger_id = comparison.challenger_trials["watched"]
  expected = (
      [
          ("View Trial", f"/evaluations/trials/{challenger_id}"),
          ("View Trace", f"/evaluations/trials/{challenger_id}/trace"),
      ]
      if linked
      else []
  )
  assert [
      (a["props"]["children"], a["props"]["href"])
      for a in _of_type(challenger_column, "Anchor")
  ] == expected


def test_the_assertion_type_panel_averages_only_the_shared_types(
    dash_client, callback_errors, compared
):
  """Per-type averages, over the cases where both runs ran that assertion.

  The aggregation is in the callback, not the service, so nothing else covers
  it. A type the baseline never scored has nothing to be a delta from, and
  averaging it against an implicit zero would report the candidate's new AI
  judge as a 50% gain that nothing did.
  """
  body = _compare_page(dash_client, compared.search())
  panel = {}
  for entry in _of_type(
      body[ComparisonIds.ASSERTION_DELTA_CHART]["children"], "Stack"
  ):
    label, value = _labels(entry, "Text")
    panel[label] = value

  callback_errors.assert_none()
  assert panel == {"Text Contains": "+0.0%", "Data Check Row Count": "+25.0%"}


def test_the_delta_chart_scales_to_the_largest_case(
    dash_client, callback_errors, db_session
):
  """Bar heights are a percentage of the biggest delta, with a visible floor.

  The axis is rounded up to a multiple of 5% so the labels are readable. A case
  that barely moved still gets a 2% bar, because a bar of zero height is
  indistinguishable from a case that did not run. The chart is built from every
  case, not the filtered ones, so the shape of the run does not change as
  filters are clicked.
  """
  comparison = _seed_comparison(
      db_session,
      [
          _Case(
              "big",
              base=_Side({_TEXT: 1.0}),
              challenger=_Side({_TEXT: 0.5}),
          ),
          _Case(
              "tiny",
              base=_Side({_TEXT: 0.0}),
              challenger=_Side({_TEXT: 0.005}),
          ),
      ],
  )

  body = _compare_page(dash_client, comparison.search())
  chart = body[ComparisonIds.PERFORMANCE_DELTA_CHART]["children"]

  callback_errors.assert_none()
  assert _labels(chart, "Text") == ["+50%", "0%", "-50%"]
  assert _bar_heights(chart) == ["50.00%", "2.00%"]

  filtered = _compare_page(
      dash_client, comparison.search(**{ComparisonIds.URL_FILTER: "REGRESSION"})
  )
  # By the row, not by the count. A filter that matches nothing renders one
  # "No cases found matching filters." line, which is also a list of length
  # one, and a chart built off an empty list is what this is guarding.
  rows = filtered[ComparisonIds.COMPARISON_LIST]["children"]
  assert len(rows) == 1, rows
  assert "How many big orders are there?" in json.dumps(rows[0])
  assert _bar_heights(
      filtered[ComparisonIds.PERFORMANCE_DELTA_CHART]["children"]
  ) == ["50.00%", "2.00%"]


def test_the_delta_chart_keeps_its_axis_when_nothing_moved(
    dash_client, callback_errors, db_session
):
  """Every delta zero is a division waiting to happen, and a real result.

  Two runs of an unchanged agent are the common case. The scale falls back to
  5% so the axis still has numbers on it, and the bars are drawn as a flat 2px
  line on the midline rather than disappearing.
  """
  comparison = _seed_comparison(
      db_session,
      [
          _Case(
              "first", base=_Side({_TEXT: 1.0}), challenger=_Side({_TEXT: 1.0})
          ),
          _Case(
              "second", base=_Side({_TEXT: 0.0}), challenger=_Side({_TEXT: 0.0})
          ),
      ],
  )

  body = _compare_page(dash_client, comparison.search())
  chart = body[ComparisonIds.PERFORMANCE_DELTA_CHART]["children"]

  callback_errors.assert_none()
  assert _labels(chart, "Text") == ["+5%", "0%", "-5%"]
  assert _bar_heights(chart) == ["2px", "2px"]


def test_a_compare_link_to_a_run_that_is_gone_says_so(
    dash_client, callback_errors, db_session
):
  """A deleted or mistyped run id has to reach the page as an explanation.

  The service raises and the callback turns it into an alert. It goes in
  COMPARISON_LIST, because METRICS_CARDS sits inside SUMMARY_SECTION and the
  same return hides that, so the alert used to render in a hidden subtree and
  the page fell back to the empty state. Without the branch at all the page
  renders four cards of zeroes, which reads as two identical runs.
  """
  comparison = _seed_comparison(
      db_session,
      [_Case("only", base=_Side({_TEXT: 1.0}), challenger=_Side({_TEXT: 1.0}))],
  )
  missing = comparison.challenger_run_id + 1000

  body = _compare_page(
      dash_client,
      f"?{ComparisonIds.URL_BASE_RUN_ID}={comparison.base_run_id}"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}={missing}",
  )

  callback_errors.assert_none()
  alerts = _of_type(body[ComparisonIds.COMPARISON_LIST]["children"], "Alert")
  assert len(alerts) == 1, body[ComparisonIds.COMPARISON_LIST]["children"]
  assert alerts[0]["props"]["children"] == f"Challenger run {missing} not found"
  assert alerts[0]["props"]["color"] == "red"
  assert body[ComparisonIds.EMPTY_STATE]["style"] == {"display": "none"}
  assert body[ComparisonIds.SUMMARY_SECTION]["style"] == {"display": "none"}


def test_a_row_the_schema_rejects_is_logged_not_printed_on_the_page(
    dash_client, callback_errors, monkeypatch
):
  """The not-found branch used to catch pydantic's ValidationError too.

  It is a subclass of ValueError, so str() on one went into the same red
  alert as "Base run 12 not found". That text is the rejected field paths, the
  input_value, which is the database row, and a link to errors.pydantic.dev. A
  schema that has drifted from the table is a bug to log, so it has to reach
  handle_errors for a toast and a reference instead.
  """

  class _Row(pydantic.BaseModel):
    score: float

  with pytest.raises(pydantic.ValidationError) as rejected:
    _Row(score="not a number")

  def _raise(*_args, **_kwargs):
    raise rejected.value

  monkeypatch.setattr(ComparisonClient, "compare_runs", _raise)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  response = dash_http.fire_url(
      dash_client,
      dep,
      "/compare",
      f"?{ComparisonIds.URL_BASE_RUN_ID}=1"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}=2",
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)
  assert ComparisonIds.COMPARISON_LIST not in body.get("response", {})
  assert body["sideUpdate"][NOTIFICATION_CONTAINER]["sendNotifications"]
  assert any("errors.pydantic.dev" in m for m in callback_errors.messages)

  callback_errors.clear()


def test_a_compare_link_with_a_word_for_a_run_id_only_raises_a_toast(
    dash_client, callback_errors
):
  """A non-numeric run id never reaches the not-found branch.

  ``_parse_search`` calls int() on the parameter before the callback's own
  try/except, so a hand-edited URL is an unhandled ValueError that
  ``handle_errors`` turns into a toast and a logged traceback. That is the
  behavior, and it is a different one from the run-not-found alert above, so
  both are pinned.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  response = dash_http.fire_url(
      dash_client,
      dep,
      "/compare",
      f"?{ComparisonIds.URL_BASE_RUN_ID}=abc"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}=2",
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)
  assert ComparisonIds.METRICS_CARDS not in body.get("response", {})
  assert body["sideUpdate"][NOTIFICATION_CONTAINER]["sendNotifications"]
  assert any(
      "invalid literal" in m for m in callback_errors.messages
  ), f"the gate saw {callback_errors.messages}"

  callback_errors.clear()
