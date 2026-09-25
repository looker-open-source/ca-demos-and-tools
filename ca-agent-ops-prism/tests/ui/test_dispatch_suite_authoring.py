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

"""Authoring a test suite, driven through Dash's HTTP dispatch route.

Three things here are invisible to the sweep in ``test_callback_dispatch.py``.
The list filters are only ever fired with ``search=""``, so the parse branches
have never run. The view page is registered as ``/test_suites/view/none``, so
the router sweep always lands on the "Invalid Test Suite ID" guard and the
layout below it has never been built with a real suite. The rest of the
authoring callbacks are driven by buttons, not by the URL.

The view page is reached the way the browser reaches it, by firing Dash's own
pages router with the real suite id.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.agent import LookerConfig
from prism.common.schemas.assertion import AssertionType
from prism.server.models.assertion import Assertion
from prism.server.models.example import Example

# Aliased because pytest tries to collect any module-level name starting with
# Test and warns when it cannot.
from prism.server.models.suite import TestSuite as SuiteRow
from prism.server.repositories.agent_repository import AgentRepository
from prism.ui import utils
from prism.ui.constants import REDIRECT_HANDLER
from prism.ui.ids import EvaluationIds
from prism.ui.ids import TestSuiteHomeIds
from prism.ui.ids import TestSuiteIds
import pytest
from tests.ui import dash_http


def _outputs(dep: dict[str, Any]) -> list[dict[str, Any]]:
  """The dep's outputs as a list, however many it declares."""
  grouping = dash_http.outputs_grouping(dep["output"])
  return grouping if isinstance(grouping, list) else [grouping]


def _callback(
    deps: list[dict[str, Any]], input_address: str, output_id: str
) -> dict[str, Any]:
  """The one callback taking ``input_address`` and writing ``output_id``.

  ``dash_http.find`` cannot name most of these. ``url.search``,
  ``redirect-handler.href`` and the suite name field each have several
  callbacks behind them, which is what ``allow_duplicate`` is for, so the
  input side is what tells them apart.
  """
  matches = [
      dep
      for dep in deps
      if any(dash_http.address(i) == input_address for i in dep["inputs"])
      and any(o["id"] == output_id for o in _outputs(dep))
  ]
  assert len(matches) == 1, (
      f"expected one callback from {input_address} to {output_id}, found"
      f" {len(matches)}"
  )
  return matches[0]


def _router(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """Dash's own pages router, which builds a page layout server side."""
  return dash_http.find(deps, "_pages_content.children")


def _page(response) -> Any:
  """The layout the router returned."""
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"]["_pages_content"]["children"]


def _walk(tree: Any):
  """Every serialized component in ``tree``, depth first.

  Matching the repr of the tree finds whatever else happens to share a string,
  and these pages hide several components behind the same style dict.
  """
  stack = [tree]
  while stack:
    node = stack.pop()
    if isinstance(node, list):
      stack.extend(node)
    elif isinstance(node, dict):
      if isinstance(node.get("props"), dict):
        yield node
      stack.extend(node.values())


def _component(tree: Any, component_id: str) -> dict[str, Any]:
  """The one serialized component in ``tree`` carrying ``component_id``."""
  found = [n for n in _walk(tree) if n["props"].get("id") == component_id]
  assert len(found) == 1, f"{component_id} appears {len(found)} times"
  return found[0]


def _badges(tree: Any, label: str) -> list[dict[str, Any]]:
  """Every dmc.Badge in ``tree`` whose text is ``label``."""
  return [
      n
      for n in _walk(tree)
      if n.get("type") == "Badge" and n["props"].get("children") == label
  ]


def _meta_value(tree: Any, label: str) -> str:
  """The value the view page's header card shows under ``label``.

  The card is a grid of label and value pairs with no ids on them, so the
  label is the only way in. Each pair is a Stack of the label Text and a Group
  holding an optional icon and the value Text.
  """
  for node in _walk(tree):
    children = node["props"].get("children")
    if not isinstance(children, list) or len(children) != 2:
      continue
    head, tail = children
    if not isinstance(head, dict) or head.get("type") != "Text":
      continue
    if head["props"].get("children") != label:
      continue
    texts = [
        c
        for c in tail["props"].get("children") or []
        if isinstance(c, dict) and c.get("type") == "Text"
    ]
    assert len(texts) == 1, f"{label} has {len(texts)} values"
    return texts[0]["props"]["children"]
  raise AssertionError(f"no {label!r} item in the header card")


def _suite(
    db_session,
    name: str,
    covered: int = 0,
    uncovered: int = 0,
    archived: bool = False,
) -> SuiteRow:
  """A suite with ``covered`` examples carrying an assertion and the rest not.

  Coverage is the ratio of the two, so the filter needs suites built this way
  to have anything to tell apart.
  """
  suite = SuiteRow(name=name, description=f"{name} description", tags={})
  suite.is_archived = archived
  db_session.add(suite)
  db_session.flush()

  for i in range(covered + uncovered):
    example = Example(
        test_suite_id=suite.id,
        logical_id=f"{name}-{i}",
        question=f"Question {i} of {name}?",
    )
    db_session.add(example)
    db_session.flush()
    if i < covered:
      db_session.add(
          Assertion(
              example_id=example.id,
              type=AssertionType.TEXT_CONTAINS,
              weight=1.0,
              params={"value": "seeded", "mode": "contains"},
          )
      )

  db_session.commit()
  return suite


def _list_rows(dash_client, search: str = "") -> dict[str, str]:
  """The Test Suites list as a row of text per suite name.

  The rows carry no ids, so each one is keyed by the suite it links to. Going
  by the whole page instead would read one suite's badge off another's row.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")
  response = dash_http.fire_url(dash_client, dep, "/test_suites", search)
  assert response.status_code == 200, response.data[:2000]
  container = dash_http.body(response)["response"][
      TestSuiteHomeIds.TEST_SUITES_LIST
  ]["children"]
  rows = {}
  for node in _walk(container):
    if node.get("type") != "Tr":
      continue
    text = str(node)
    for match in re.findall(r"/test_suites/view/(\d+)", text):
      rows[int(match)] = text
  return rows


def test_an_empty_suite_is_badged_as_having_no_test_cases(
    dash_client, callback_errors, db_session, seeded
):
  """A suite with nothing in it is not a suite whose questions lack assertions.

  Coverage on an empty suite is 0.0, so it fell into the same branch as a
  suite of ten unasserted questions and got a red "No Coverage" badge. The
  view page for that same suite says "No Test Cases", so the two pages
  disagreed about it. The seeded suite is in the table too, because a branch
  that swallowed every suite would also satisfy the empty one.
  """
  empty = _suite(db_session, "Empty Suite")

  rows = _list_rows(dash_client)
  callback_errors.assert_none()

  assert "No Test Cases" in rows[empty.id]
  assert "No Coverage" not in rows[empty.id]
  assert "No Coverage" in rows[seeded.suite_id]
  assert "No Test Cases" not in rows[seeded.suite_id]


def test_the_suites_list_raises_the_overlay_while_it_queries(
    dash_client, callback_errors
):
  """The overlay has to be driven by ``running``, not by a return value.

  It used to be an output the callback set False on the way out, and nothing
  ever set it True, so toggling Show Archived re-queried with the stale table
  on screen and nothing saying work had started. ``running`` is the only part
  of this the browser acts on before the response arrives, and it is in the
  dependency graph the page fetches on load.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")

  running = dep.get("running")
  assert running, "the list callback declares no running spec"
  assert running["running"] == {f"{TestSuiteHomeIds.LOADING}.visible": True}
  assert running["runningOff"] == {f"{TestSuiteHomeIds.LOADING}.visible": False}
  # And it is not also a plain output, which is what it used to be.
  assert TestSuiteHomeIds.LOADING not in dep["output"]

  callback_errors.assert_none()


def test_saving_a_test_suite_with_no_name_says_so(
    dash_client, callback_errors, db_session
):
  """Save & Continue with the name empty used to do nothing at all.

  No message and no navigation, because both outputs came back no_update. The
  ``required`` flag on the input is a Mantine asterisk and does not stop the
  click. The field error is how the agent forms report the same thing.
  """
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps,
      f"{TestSuiteIds.SAVE_NEW_BTN}.n_clicks",
      REDIRECT_HANDLER,
  )

  def save(name):
    return dash_http.body(
        dash_http.fire(
            dash_client,
            dep,
            {
                f"{TestSuiteIds.SAVE_NEW_BTN}.n_clicks": 1,
                f"{TestSuiteIds.NAME}.value": name,
                f"{TestSuiteIds.DESC}.value": "A description",
            },
            changed=[f"{TestSuiteIds.SAVE_NEW_BTN}.n_clicks"],
        )
    )["response"]

  for empty in ("", "   ", None):
    body = save(empty)
    assert body[TestSuiteIds.NAME]["error"] == "Give the test suite a name."
    assert REDIRECT_HANDLER not in body, empty
  assert not db_session.query(SuiteRow).all()

  # A real name clears the error and navigates, or the message would stick to
  # the field after it was fixed.
  body = save("A Named Suite")
  callback_errors.assert_none()
  assert body[TestSuiteIds.NAME]["error"] is False
  created = db_session.query(SuiteRow).one()
  assert body[REDIRECT_HANDLER]["href"] == f"/test_suites/view/{created.id}"


def test_the_coverage_filter_narrows_the_list_and_round_trips_through_the_url(
    dash_client, callback_errors, db_session, seeded
):
  """A coverage filter that does not narrow the list is a filter in name only.

  Two halves, because they are different callbacks and either one alone leaves
  the control inert: the list reads ``?coverage=`` out of the URL, and the
  Select writes it back in. The seeded suite has one example and no
  assertions, so it is the NONE case.
  """
  covered = _suite(db_session, "Fully Covered Suite", covered=2)
  half = _suite(db_session, "Half Covered Suite", covered=1, uncovered=1)

  unfiltered = _list_rows(dash_client)
  assert covered.id in unfiltered
  assert half.id in unfiltered
  assert seeded.suite_id in unfiltered

  full = _list_rows(dash_client, "?coverage=FULL")
  assert covered.id in full
  assert half.id not in full
  assert seeded.suite_id not in full

  partial = _list_rows(dash_client, "?coverage=PARTIAL")
  assert half.id in partial
  assert covered.id not in partial

  none = _list_rows(dash_client, "?coverage=NONE")
  assert seeded.suite_id in none
  assert covered.id not in none

  deps = dash_http.dependencies(dash_client)
  write = _callback(deps, f"{TestSuiteHomeIds.FILTER_COVERAGE}.value", "url")
  chosen = dash_http.body(
      dash_http.fire(
          dash_client,
          write,
          {
              f"{TestSuiteHomeIds.FILTER_COVERAGE}.value": "PARTIAL",
              "url.search": "?archived=true",
          },
      )
  )["response"]["url"]["search"]
  # The archived switch writes the same string, so setting one filter has to
  # keep the other.
  assert "coverage=PARTIAL" in chosen
  assert "archived=true" in chosen

  cleared = dash_http.body(
      dash_http.fire(
          dash_client,
          write,
          {
              f"{TestSuiteHomeIds.FILTER_COVERAGE}.value": None,
              "url.search": "?coverage=PARTIAL",
          },
      )
  )["response"]["url"]["search"]
  assert cleared == ""

  callback_errors.assert_none()


def test_show_archived_brings_the_archived_suite_back_with_its_badge(
    dash_client, callback_errors, db_session, seeded
):
  """An archived suite has to be findable again, and marked when it is.

  Without the badge the restored row is indistinguishable from a live one, so
  the switch reads as having done nothing. The live suite is here so the two
  states differ by one row and not by the whole table, which would also pass
  if the list had failed to render.
  """
  archived = _suite(db_session, "Archived Suite", uncovered=1, archived=True)

  hidden = _list_rows(dash_client)
  assert archived.id not in hidden
  assert seeded.suite_id in hidden

  shown = _list_rows(dash_client, "?archived=true")
  assert archived.id in shown
  assert seeded.suite_id in shown

  deps = dash_http.dependencies(dash_client)
  rows = dash_http.fire_url(
      dash_client,
      dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children"),
      "/test_suites",
      "?archived=true",
  )
  table = dash_http.body(rows)["response"][TestSuiteHomeIds.TEST_SUITES_LIST][
      "children"
  ]
  assert len(_badges(table, "Archived")) == 1

  write = _callback(deps, f"{TestSuiteHomeIds.SWITCH_ARCHIVED}.checked", "url")
  search = dash_http.body(
      dash_http.fire(
          dash_client,
          write,
          {
              f"{TestSuiteHomeIds.SWITCH_ARCHIVED}.checked": True,
              "url.search": "?coverage=FULL",
          },
      )
  )["response"]["url"]["search"]
  assert "archived=true" in search
  assert "coverage=FULL" in search

  callback_errors.assert_none()


def test_the_filter_controls_are_restored_from_the_url(
    dash_client, callback_errors
):
  """A bookmarked filter must show in the controls, not only in the list.

  This callback is in the URL-driven sweep, but the sweep only ever passes an
  empty search, so until now the only branch that ran was the early return.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.FILTER_COVERAGE}.value")

  restored = dash_http.body(
      dash_http.fire_url(
          dash_client, dep, "/test_suites", "?coverage=FULL&archived=true"
      )
  )["response"]
  assert restored[TestSuiteHomeIds.FILTER_COVERAGE]["value"] == "FULL"
  assert restored[TestSuiteHomeIds.SWITCH_ARCHIVED]["checked"] is True

  bare = dash_http.body(
      dash_http.fire_url(dash_client, dep, "/test_suites", "")
  )["response"]
  assert bare[TestSuiteHomeIds.FILTER_COVERAGE]["value"] is None
  assert bare[TestSuiteHomeIds.SWITCH_ARCHIVED]["checked"] is False

  callback_errors.assert_none()


def test_archiving_a_suite_writes_the_row_and_the_page_comes_back_with_restore(
    dash_client, callback_errors, db_session, seeded
):
  """Archive has to write the row and leave a way back.

  The button swap is computed in the layout off ``suite.is_archived``, so the
  re-render is the only thing that shows the write took. The callback answers
  with the same pathname, which is what makes the page re-render at all.
  """
  deps = dash_http.dependencies(dash_client)
  pathname = f"/test_suites/view/{seeded.suite_id}"
  dep = _callback(
      deps, f"{TestSuiteIds.BTN_ARCHIVE}.n_clicks", REDIRECT_HANDLER
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{TestSuiteIds.BTN_ARCHIVE}.n_clicks": 1,
          f"{TestSuiteIds.BTN_RESTORE}.n_clicks": None,
          "url.pathname": pathname,
      },
      changed=[f"{TestSuiteIds.BTN_ARCHIVE}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  assert (
      dash_http.body(response)["response"][REDIRECT_HANDLER]["href"] == pathname
  )

  db_session.expire_all()
  suite = db_session.get(SuiteRow, seeded.suite_id)
  assert suite.is_archived is True

  page = _page(dash_http.fire_url(dash_client, _router(deps), pathname))
  archive = _component(page, TestSuiteIds.BTN_ARCHIVE)
  restore = _component(page, TestSuiteIds.BTN_RESTORE)
  assert archive["props"]["style"] == {"display": "none"}
  assert restore["props"]["style"] == {"display": "block"}

  callback_errors.assert_none()


def test_restoring_an_archived_suite_clears_is_archived(
    dash_client, callback_errors, db_session, seeded
):
  """Restore is the other branch of the same callback, and had no test at all.

  ``SuiteService.unarchive_suite`` is untested at every tier above the
  repository. Without this, archiving a suite is indistinguishable from
  deleting it.
  """
  suite = db_session.get(SuiteRow, seeded.suite_id)
  suite.is_archived = True
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  pathname = f"/test_suites/view/{seeded.suite_id}"
  dep = _callback(
      deps, f"{TestSuiteIds.BTN_RESTORE}.n_clicks", REDIRECT_HANDLER
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{TestSuiteIds.BTN_ARCHIVE}.n_clicks": None,
          f"{TestSuiteIds.BTN_RESTORE}.n_clicks": 1,
          "url.pathname": pathname,
      },
      changed=[f"{TestSuiteIds.BTN_RESTORE}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  db_session.expire_all()
  assert db_session.get(SuiteRow, seeded.suite_id).is_archived is False

  page = _page(dash_http.fire_url(dash_client, _router(deps), pathname))
  assert _component(page, TestSuiteIds.BTN_ARCHIVE)["props"]["style"] == {
      "display": "block"
  }
  assert _component(page, TestSuiteIds.BTN_RESTORE)["props"]["style"] == {
      "display": "none"
  }

  callback_errors.assert_none()


def test_the_edit_config_modal_prefills_from_the_suite(
    dash_client, callback_errors, db_session, seeded
):
  """Editing a suite must not start from a blank name and description.

  Two callbacks in a row, the way the page runs them. ``load_test_suite_data``
  fills the fields on load, and the Edit button copies what they hold into the
  modal. The description is the one that can be lost without trace: the
  repository skips None but writes an empty string, so a blank prefill saves
  over it.
  """
  suite = db_session.get(SuiteRow, seeded.suite_id)
  suite.description = "Seeded description"
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  load = _callback(deps, f"{TestSuiteIds.NAME}.id", TestSuiteIds.STORE_BUILDER)
  loaded = dash_http.body(
      dash_http.fire(
          dash_client,
          load,
          {
              f"{TestSuiteIds.NAME}.id": TestSuiteIds.NAME,
              "url.pathname": f"/test_suites/view/{seeded.suite_id}",
          },
      )
  )["response"]

  assert loaded[TestSuiteIds.NAME]["value"] == seeded.suite_name
  assert loaded[TestSuiteIds.DESC]["value"] == "Seeded description"
  questions = [
      tc["question"] for tc in loaded[TestSuiteIds.STORE_BUILDER]["data"]
  ]
  assert questions == [seeded.question]

  toggle = _callback(
      deps,
      f"{TestSuiteIds.BTN_CONFIG_EDIT}.n_clicks",
      TestSuiteIds.MODAL_CONFIG_EDIT,
  )
  values = {
      f"{TestSuiteIds.BTN_CONFIG_EDIT}.n_clicks": 1,
      f"{TestSuiteIds.NAME}.value": seeded.suite_name,
      f"{TestSuiteIds.DESC}.value": "Seeded description",
  }
  opened = dash_http.body(
      dash_http.fire(
          dash_client,
          toggle,
          values,
          changed=[f"{TestSuiteIds.BTN_CONFIG_EDIT}.n_clicks"],
      )
  )["response"]

  assert opened[TestSuiteIds.MODAL_CONFIG_EDIT]["opened"] is True
  assert opened[TestSuiteIds.NAME]["value"] == seeded.suite_name
  assert opened[TestSuiteIds.DESC]["value"] == "Seeded description"

  closed = dash_http.body(
      dash_http.fire(
          dash_client,
          toggle,
          dict(
              values, **{f"{TestSuiteIds.MODAL_CONFIG_CANCEL_BTN}.n_clicks": 1}
          ),
          changed=[f"{TestSuiteIds.MODAL_CONFIG_CANCEL_BTN}.n_clicks"],
      )
  )["response"]
  # Cancel closes and writes nothing else, so the two fields are absent from
  # the response rather than present and empty.
  assert closed[TestSuiteIds.MODAL_CONFIG_EDIT]["opened"] is False
  assert TestSuiteIds.NAME not in closed

  callback_errors.assert_none()


def test_saving_the_edit_config_modal_renames_the_suite(
    dash_client, callback_errors, db_session, seeded
):
  """This is the only way to rename a suite in the product.

  A second callback used to take a page Save button as its input, and that id
  was rendered as a hidden html.Div on both pages that carried it. A Div has no
  n_clicks, so nothing could fire it. It is gone, and this modal is what is
  left.
  """
  deps = dash_http.dependencies(dash_client)
  pathname = f"/test_suites/view/{seeded.suite_id}"
  dep = _callback(
      deps, f"{TestSuiteIds.MODAL_CONFIG_SAVE_BTN}.n_clicks", REDIRECT_HANDLER
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{TestSuiteIds.MODAL_CONFIG_SAVE_BTN}.n_clicks": 1,
          "url.pathname": pathname,
          f"{TestSuiteIds.NAME}.value": "Renamed Suite",
          f"{TestSuiteIds.DESC}.value": "Rewritten description",
      },
      changed=[f"{TestSuiteIds.MODAL_CONFIG_SAVE_BTN}.n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  assert (
      dash_http.body(response)["response"][REDIRECT_HANDLER]["href"] == pathname
  )

  db_session.expire_all()
  suite = db_session.get(SuiteRow, seeded.suite_id)
  assert suite.name == "Renamed Suite"
  assert suite.description == "Rewritten description"

  callback_errors.assert_none()


@pytest.mark.parametrize(
    "covered, uncovered, expected_badge, expected_count",
    [
        (2, 0, "Full Coverage", "2"),
        (1, 1, "Partial Coverage", "2"),
        (0, 1, "No Coverage", "1"),
        (0, 0, "No Test Cases", "0"),
    ],
)
def test_the_view_page_renders_the_suites_coverage_and_counts(
    dash_client,
    callback_errors,
    db_session,
    covered,
    uncovered,
    expected_count,
    expected_badge,
):
  """Tier 2 had never built this layout with a real suite.

  Dash registers the page as /test_suites/view/none, so every sweep stops at
  the digit guard and everything below it goes unrun. Coverage is computed in
  the page, not read off the suite, so all four states are rendered here.
  """
  suite = _suite(
      db_session, "Viewed Suite", covered=covered, uncovered=uncovered
  )
  # A suite written and never touched again has the two stamps within a second
  # of each other, and format_timestamp rounds to the minute, so the two meta
  # rows below read the same string and swapping the fields still passed.
  # modified_at is not in this UPDATE, so its onupdate refreshes it to now.
  suite.created_at = suite.created_at - datetime.timedelta(days=2, hours=3)
  db_session.commit()

  examples = (
      db_session.query(Example)
      .filter_by(test_suite_id=suite.id)
      .order_by(Example.id)
      .all()
  )

  deps = dash_http.dependencies(dash_client)
  page = _page(
      dash_http.fire_url(
          dash_client, _router(deps), f"/test_suites/view/{suite.id}"
      )
  )

  assert len(_badges(page, expected_badge)) == 1
  assert _meta_value(page, "Test Cases") == expected_count
  # Both through the shared helper, so both carry the clock they are on.
  assert _meta_value(page, "Created At") == utils.format_timestamp(
      suite.created_at
  )
  assert _meta_value(page, "Last Updated") == utils.format_timestamp(
      suite.modified_at
  )

  cards = str(_component(page, TestSuiteIds.TEST_CASE_LIST))
  # The loop below asserts nothing on the empty suite, so the count says how
  # many cards it is standing for.
  assert len(examples) == int(expected_count)
  for example in examples:
    assert example.question in cards
    # The card is a link into the editor for that one test case. Without the
    # id there is no way to open it.
    assert f"/test_suites/edit/{suite.id}?test_case_id={example.id}" in cards

  callback_errors.assert_none()


def test_a_missing_suite_id_renders_the_not_found_alert(
    dash_client, callback_errors, seeded
):
  """A stale bookmark has to say the suite is gone, not answer 500.

  A page layout is not wrapped by ``handle_errors``, so nothing catches a
  dereference of the missing suite. The layout builds its test case list
  before it checks that the suite exists, which is what makes the guard worth
  pinning.
  """
  deps = dash_http.dependencies(dash_client)
  missing = seeded.suite_id + 10_000

  response = dash_http.fire_url(
      dash_client, _router(deps), f"/test_suites/view/{missing}"
  )

  assert response.status_code == 200, response.data[:2000]
  assert "Test Suite not found" in str(_page(response))
  callback_errors.assert_none()


def test_a_looker_agent_without_credentials_warns_before_the_run(
    dash_client, callback_errors, db_session, seeded
):
  """The only pre-flight warning before a run that would fail every trial.

  A Looker agent needs a client id and secret to answer anything, and the run
  modal is the last place to say so. The seeded agent is the other half: a
  details panel that always warned would be as useless as one that never did.
  """
  repo = AgentRepository(db_session)
  looker = repo.create(
      name="Looker Agent",
      config=AgentConfig(
          project_id="p",
          location="l",
          agent_resource_id="r",
          datasource=LookerConfig(
              instance_uri="https://looker.example.com", explores=["orders"]
          ),
      ),
  )
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.AGENT_DETAILS}.children")

  warned = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {f"{EvaluationIds.AGENT_SELECT}.value": str(looker.id)},
      )
  )["response"][EvaluationIds.AGENT_DETAILS]["children"]
  assert "Missing Credentials" in str(warned)

  fine = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {f"{EvaluationIds.AGENT_SELECT}.value": str(seeded.agent_id)},
      )
  )["response"][EvaluationIds.AGENT_DETAILS]["children"]
  assert seeded.agent_name in str(fine)
  assert "Missing Credentials" not in str(fine)

  callback_errors.assert_none()
