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

"""A status with no line in the badge map still renders a page.

``run_status_display`` was a bare subscript on a dict keyed by RunStatus. A
member added to the enum without a line in the map raised KeyError out of
whatever page was drawing the badge, and every page that lists runs draws one.
``handle_errors`` turns that into an empty container and a toast, so the whole
table goes missing over one unrecognised row.

``tests/ui/test_run_status_badges.py`` pins the function. What is added here is
the two pages, because the fallback is only worth anything if the page around
it survives.
"""

from __future__ import annotations

import json
from typing import Any

from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.ui import utils
from prism.ui.ids import EvaluationIds
import pytest
from tests.ui import dash_http


@pytest.fixture(name="unmapped")
def _unmapped(monkeypatch) -> RunStatus:
  """Takes PAUSED out of the badge map, and returns it.

  Deleting an entry stands in for a member that was added to RunStatus and
  never given a line here, which is the case this is for. PAUSED is the one
  that has already happened once: the three maps this replaced were written
  before it existed.
  """
  trimmed = dict(utils._RUN_STATUS_DISPLAY)  # pylint: disable=protected-access
  del trimmed[RunStatus.PAUSED]
  monkeypatch.setattr(utils, "_RUN_STATUS_DISPLAY", trimmed)
  return RunStatus.PAUSED


def _badges(node: Any) -> list[dict[str, Any]]:
  """Every serialized Badge in a tree, in document order."""
  if isinstance(node, list):
    return [b for item in node for b in _badges(item)]
  if isinstance(node, dict):
    found = [node] if node.get("type") == "Badge" else []
    return found + [b for value in node.values() for b in _badges(value)]
  return []


def test_the_evaluations_table_still_lists_a_run_whose_status_is_unmapped(
    dash_client, callback_errors, db_session, seeded, unmapped
):
  """One unrecognised row used to take the whole table with it.

  The list draws a badge per run, so the KeyError came out of the loop and
  ``handle_errors`` returned no_update for the container. The page rendered
  the layout's empty placeholder over a database with runs in it, next to a
  toast that named none of them.
  """
  db_session.get(Run, seeded.run_id).status = unmapped
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.RUN_LIST_CONTAINER}.children")
  response = dash_http.fire_url(dash_client, dep, "/evaluations", "")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  container = dash_http.body(response)["response"][
      EvaluationIds.RUN_LIST_CONTAINER
  ]["children"]

  assert f"/evaluations/runs/{seeded.run_id}" in json.dumps(container)
  fallback = [
      b for b in _badges(container) if b["props"]["children"] == "PAUSED"
  ]
  assert len(fallback) == 1, json.dumps(container)[:2000]
  assert fallback[0]["props"]["color"] == "gray"


def test_the_trace_header_falls_back_to_the_raw_name_of_the_status(
    dash_client, callback_errors, db_session, seeded, unmapped
):
  """The header is two outputs, a label and a colour, and both have to land.

  Grey and the raw enum name is not a good badge. It is a legible one, and it
  says which status it could not draw, which is what a reader needs to report
  it. The alternative was a page that did not load.
  """
  trial = (
      db_session.query(Trial)
      .filter_by(run_id=seeded.run_id)
      .order_by(Trial.id)
      .first()
  )
  trial.status = unmapped
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.AGENT_TRACE_STATUS}.children")
  response = dash_http.fire_url(
      dash_client, dep, f"/evaluations/trials/{trial.id}/trace"
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  badge = dash_http.body(response)["response"][EvaluationIds.AGENT_TRACE_STATUS]

  assert badge["children"] == "PAUSED"
  assert badge["color"] == "gray"


def test_the_fallback_is_the_only_thing_that_changed_for_a_mapped_status(
    dash_client, callback_errors, db_session, seeded
):
  """Without this the tests above pass for a function that greys everything.

  Same page, same run, the map left alone. The label is the one the map
  carries and not the enum name, which is what tells the two branches apart.
  """
  db_session.get(Run, seeded.run_id).status = RunStatus.PAUSED
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.RUN_LIST_CONTAINER}.children")
  response = dash_http.fire_url(dash_client, dep, "/evaluations", "")

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  container = dash_http.body(response)["response"][
      EvaluationIds.RUN_LIST_CONTAINER
  ]["children"]
  drawn = [b for b in _badges(container) if b["props"]["children"] == "Paused"]

  assert len(drawn) == 1, json.dumps(container)[:2000]
  assert drawn[0]["props"]["color"] == "yellow"
  assert "PAUSED" not in [b["props"]["children"] for b in _badges(container)]
