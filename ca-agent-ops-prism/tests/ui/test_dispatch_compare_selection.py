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

"""Choosing two runs to compare, and arriving at a comparison that is gone.

Two ways the compare flow used to end somewhere that looked like a working
page. Picking a base run rewrote the challenger options and left the
challenger itself pointing at a run of the old suite. Opening a /compare link
whose run has since been deleted put the explanation inside a subtree the same
return hides, so the page fell back to its empty state.

``tests/ui/test_dispatch_run_comparison.py`` covers the page when both runs are
there, and ``tests/ui/test_dispatch_evaluations_list.py`` covers the modal when
the selection holds.
"""

from __future__ import annotations

from typing import Any

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.ids import ComparisonIds
from prism.ui.ids import EvaluationIds
import pytest
from tests.ui import dash_http


def _by_input(deps: list[dict[str, Any]], address: str) -> dict[str, Any]:
  """The one callback taking ``"<id>.<property>"`` as an input."""
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


def _walk(fragment: Any):
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


def _alerts(fragment: Any) -> list[dict[str, Any]]:
  """The alerts in a response fragment, in document order."""
  return [c for c in _walk(fragment) if c["type"] == "Alert"]


def _compare_page(dash_client, search: str) -> dict[str, Any]:
  """Loads /compare and returns the response keyed by component id."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  response = dash_http.fire_url(dash_client, dep, "/compare", search)
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"]


def test_a_compare_link_to_a_run_that_is_gone_explains_itself_in_the_open(
    dash_client, callback_errors
):
  """A bookmarked comparison outlives the runs it names.

  The alert used to go into the metric cards, which are a child of the summary
  section the same return sets to display:none, so it was rendered inside a
  hidden subtree and nothing reached the screen. What was on screen instead
  was the "No runs selected" empty state, which is what /compare with no query
  string at all looks like, while the URL still named two runs.
  """
  search = (
      f"?{ComparisonIds.URL_BASE_RUN_ID}=4242"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}=4243"
  )

  body = _compare_page(dash_client, search)

  callback_errors.assert_none()
  alerts = _alerts(body[ComparisonIds.COMPARISON_LIST]["children"])
  assert len(alerts) == 1, body[ComparisonIds.COMPARISON_LIST]["children"]
  assert alerts[0]["props"]["children"] == "Base run 4242 not found"
  assert alerts[0]["props"]["color"] == "red"

  # The list is the only always-visible container this return writes to. The
  # other three are hidden by the same return.
  assert body[ComparisonIds.SUMMARY_SECTION]["style"] == {"display": "none"}
  assert body[ComparisonIds.CONTEXT_DIFF_ACCORDION]["style"] == {
      "display": "none"
  }
  assert not _alerts(body[ComparisonIds.METRICS_CARDS]["children"])


def test_the_page_that_could_not_load_does_not_also_offer_a_fresh_choice(
    dash_client, callback_errors
):
  """The empty state invites a choice that has already been made.

  Showing it next to the alert reads as two different pages at once: one
  saying the comparison failed, one saying no comparison was asked for.
  """
  search = (
      f"?{ComparisonIds.URL_BASE_RUN_ID}=4242"
      f"&{ComparisonIds.URL_CHALLENGER_RUN_ID}=4243"
  )

  body = _compare_page(dash_client, search)

  callback_errors.assert_none()
  assert body[ComparisonIds.EMPTY_STATE]["style"] == {"display": "none"}


def _other_suite_run(db_session, name: str) -> int:
  """A completed run of a suite of its own, and its id."""
  config = AgentConfig(project_id="p", location="l", agent_resource_id="r")
  agent = AgentRepository(db_session).create(
      name=f"{name} Agent", config=config
  )
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  suite = suite_repo.create(name=f"{name} Suite")
  example_repo.create(suite.id, f"How many {name} orders are there?")
  snapshot = SnapshotService(
      db_session, suite_repo, example_repo
  ).create_snapshot(suite.id)
  run = RunRepository(db_session).create(snapshot.id, agent.id)
  run.status = RunStatus.COMPLETED
  db_session.commit()
  return run.id


def _sibling_run(db_session, suite_id: int, agent_id: int) -> int:
  """A second run of an existing suite, from a second snapshot of it.

  The filter joins on ``original_suite_id`` while a run row carries
  ``test_suite_snapshot_id``. With one snapshot the two ids coincide and a
  filter that reads the wrong one still looks right.
  """
  suite_repo = SuiteRepository(db_session)
  example_repo = ExampleRepository(db_session)
  snapshot = SnapshotService(
      db_session, suite_repo, example_repo
  ).create_snapshot(suite_id)
  run = RunRepository(db_session).create(snapshot.id, agent_id)
  run.status = RunStatus.COMPLETED
  db_session.commit()
  return run.id


def _filter(dash_client, base_run_id: Any, challenger_run_id: Any):
  """Fires the challenger filter as if the base dropdown had just changed."""
  deps = dash_http.dependencies(dash_client)
  dep = _by_input(deps, f"{EvaluationIds.COMPARE_BASE_SELECT}.value")
  return dash_http.fire(
      dash_client,
      dep,
      {
          f"{EvaluationIds.COMPARE_BASE_SELECT}.value": base_run_id,
          f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.value": challenger_run_id,
      },
  )


def _written(response) -> dict[str, Any]:
  """The property values a 200 carries, keyed by ``<id>.<property>``."""
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def test_changing_the_base_run_clears_a_challenger_from_the_old_suite(
    dash_client, callback_errors, db_session, seeded
):
  """The value has to go with the data it was chosen from.

  This rewrote the options and left the challenger set to a run of the suite
  that was on screen before. The field renders blank, because the value is not
  in the data, but the Compare button stays enabled and reads that value as
  State. Clicking it compared two runs of different suites, which reads like
  two identical runs rather than a mis-selection.
  """
  other = _other_suite_run(db_session, "other")

  response = _filter(
      dash_client, base_run_id=str(other), challenger_run_id=str(seeded.run_id)
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  written = _written(response)
  offered = {
      o["value"]
      for o in written[f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.data"]
  }

  assert offered == {str(other)}
  assert str(seeded.run_id) not in offered
  assert written[f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.value"] is None


def test_a_challenger_that_survives_the_filter_is_left_selected(
    dash_client, callback_errors, db_session, seeded
):
  """Clearing on every change would undo a selection that is still valid.

  Both runs here are of the seeded suite, so narrowing the options leaves the
  challenger among them. The value comes back no_update, which Dash leaves out
  of the response.
  """
  sibling = _sibling_run(db_session, seeded.suite_id, seeded.agent_id)

  response = _filter(
      dash_client,
      base_run_id=str(sibling),
      challenger_run_id=str(seeded.run_id),
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  written = _written(response)
  offered = {
      o["value"]
      for o in written[f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.data"]
  }

  assert offered == {str(sibling), str(seeded.run_id)}
  assert f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.value" not in written


@pytest.mark.parametrize("challenger", [None, ""])
def test_no_challenger_picked_yet_is_not_a_selection_to_clear(
    dash_client, callback_errors, db_session, seeded, challenger
):
  """The modal opens with the challenger preselected and the base empty.

  Picking the base first is the ordinary path, and on that path there is
  nothing to clear. Writing None into the field anyway is a write Dash sends
  to the browser for no reason.
  """
  del seeded  # The run the filter is pointed at is the one made here.
  other = _other_suite_run(db_session, "lonely")

  response = _filter(
      dash_client, base_run_id=str(other), challenger_run_id=challenger
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  written = _written(response)

  assert f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.data" in written
  assert f"{EvaluationIds.COMPARE_CHALLENGE_SELECT}.value" not in written
