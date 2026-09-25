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

"""Changing the suite on /compare drops the two runs chosen under the old one.

``populate_run_selects`` fires on the suite dropdown and rewrites both run
lists. It used to leave the two values alone, so they went on naming runs of
the suite that was on screen before. The fields render blank, because a value
that is not in the data shows nothing, and that is the whole of what the user
sees. Apply reads the values as State, not as what is drawn, so it built
``?suite_id=<new>&base_run_id=<run of the old suite>`` off two empty-looking
dropdowns.

``tests/ui/test_dispatch_compare_selection.py`` covers the same mismatch in the
modal on the evaluations list, which is a different pair of dropdowns.
"""

from __future__ import annotations

from typing import Any
import urllib.parse

from prism.common.schemas.agent import AgentConfig
from prism.common.schemas.execution import RunStatus
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services.snapshot_service import SnapshotService
from prism.ui.ids import ComparisonIds
from tests.ui import dash_http

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import

_BASE = f"{ComparisonIds.BASE_RUN_SELECT}.value"
_CHAL = f"{ComparisonIds.CHALLENGE_RUN_SELECT}.value"


def _values(response) -> dict[str, Any]:
  """The property values a 200 carries, keyed by ``<id>.<property>``."""
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def _populate(deps: list[dict[str, Any]]) -> dict[str, Any]:
  """The callback filling the three dropdowns on /compare."""
  return dash_http.find(deps, f"{ComparisonIds.SUITE_SELECT}.data")


def _other_suite(db_session, name: str) -> int:
  """A suite of its own with one completed run, and the suite's id."""
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
  return suite.id


def test_picking_another_suite_clears_both_run_values(
    dash_client, callback_errors, db_session, seeded
):
  """The values have to go with the data they were chosen from."""
  other_suite_id = _other_suite(db_session, "other")
  deps = dash_http.dependencies(dash_client)
  dep = _populate(deps)

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{ComparisonIds.LOC_URL}.pathname": "/compare",
          f"{ComparisonIds.SUITE_SELECT}.value": str(other_suite_id),
          f"{ComparisonIds.LOC_URL}.search": (
              f"?{ComparisonIds.URL_BASE_RUN_ID}={seeded.run_id}"
          ),
      },
      changed=[f"{ComparisonIds.SUITE_SELECT}.value"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  offered = {
      o["value"] for o in values[f"{ComparisonIds.BASE_RUN_SELECT}.data"]
  }
  assert str(seeded.run_id) not in offered
  assert values[_BASE] is None
  assert values[_CHAL] is None


def test_the_load_path_keeps_the_selection_the_url_asked_for(
    dash_client, callback_errors, db_session, seeded
):
  """Clearing on every run of this callback would undo the deep link.

  The same callback fires on the pathname, which is how a bookmarked
  ``/compare?base_run_id=...`` fills its dropdowns. There the values are the
  selection, so writing None over them empties the modal the link opened.
  """
  del db_session
  deps = dash_http.dependencies(dash_client)
  dep = _populate(deps)

  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{ComparisonIds.LOC_URL}.pathname": "/compare",
          f"{ComparisonIds.SUITE_SELECT}.value": None,
          f"{ComparisonIds.LOC_URL}.search": (
              f"?{ComparisonIds.URL_BASE_RUN_ID}={seeded.run_id}"
          ),
      },
      changed=[f"{ComparisonIds.LOC_URL}.pathname"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  values = _values(response)

  offered = {
      o["value"] for o in values[f"{ComparisonIds.BASE_RUN_SELECT}.data"]
  }
  assert str(seeded.run_id) in offered, "the linked run was not offered"
  assert _BASE not in values
  assert _CHAL not in values


def test_apply_cannot_build_a_cross_suite_url_after_a_suite_change(
    dash_client, callback_errors, db_session, seeded
):
  """The two callbacks in sequence, which is what the user drives.

  Apply reads the run values as State. Whatever the suite change left in them
  is what goes into the query string, and the page that URL loads reports one
  of the runs as belonging to another suite. Following the browser here means
  reading a value Dash did not write as unchanged, which is what the dropdown
  in front of the user still holds.
  """
  other_suite_id = _other_suite(db_session, "other")
  deps = dash_http.dependencies(dash_client)

  changed = dash_http.fire(
      dash_client,
      _populate(deps),
      {
          f"{ComparisonIds.LOC_URL}.pathname": "/compare",
          f"{ComparisonIds.SUITE_SELECT}.value": str(other_suite_id),
          f"{ComparisonIds.LOC_URL}.search": "",
      },
      changed=[f"{ComparisonIds.SUITE_SELECT}.value"],
  )
  assert changed.status_code == 200, changed.data[:2000]
  written = _values(changed)

  # An output left at no_update keeps the value the field already had.
  stale = str(seeded.run_id)
  base_value = written.get(_BASE, stale)
  chal_value = written.get(_CHAL, stale)

  apply_dep = dash_http.find(
      deps,
      f"{ComparisonIds.SELECT_RUNS_MODAL}.opened",
      triggered_by=ComparisonIds.BTN_APPLY_SELECT_RUNS,
  )
  applied = dash_http.fire(
      dash_client,
      apply_dep,
      {
          f"{ComparisonIds.BTN_APPLY_SELECT_RUNS}.n_clicks": 1,
          f"{ComparisonIds.SUITE_SELECT}.value": str(other_suite_id),
          _BASE: base_value,
          _CHAL: chal_value,
          f"{ComparisonIds.LOC_URL}.search": "",
      },
      changed=[f"{ComparisonIds.BTN_APPLY_SELECT_RUNS}.n_clicks"],
  )

  # Apply returns a bare no_update when it has nothing to build, and Dash
  # reads that as a PreventUpdate and answers 204 with no body.
  assert applied.status_code in (200, 204), applied.data[:2000]
  callback_errors.assert_none()
  search = _values(applied).get(f"{ComparisonIds.LOC_URL}.search", "")
  params = urllib.parse.parse_qs(search.lstrip("?"))

  assert stale not in params.get(ComparisonIds.URL_BASE_RUN_ID, [])
  assert stale not in params.get(ComparisonIds.URL_CHALLENGER_RUN_ID, [])
