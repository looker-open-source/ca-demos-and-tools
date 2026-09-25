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

"""The home dashboard's 30 second refresh, driven over Dash's HTTP route.

``update_dashboard`` is fired by an Interval, so nothing that sweeps the URL
callbacks reaches it. It writes three containers and the run table is the one
with an id inside it.
"""

from __future__ import annotations

from typing import Any

from prism.ui.components.tables import render_run_table
from prism.ui.pages.home_ids import HomeIds
from tests.ui import dash_http


def _ids(node: Any) -> list[Any]:
  """Every component id in a serialized tree, in no particular order."""
  found = []
  stack = [node]
  while stack:
    item = stack.pop()
    if isinstance(item, list):
      stack.extend(item)
    elif isinstance(item, dict):
      props = item.get("props")
      if isinstance(props, dict) and "id" in props:
        found.append(props["id"])
      stack.extend(item.values())
  return found


def test_the_refresh_does_not_stamp_the_container_id_on_its_own_contents(
    dash_client, callback_errors, seeded
):
  """The table went inside the div whose id it was given.

  ``render_run_table`` puts ``table_id`` on the div it returns, and this
  callback writes the children of the div that already carries
  RECENT_RUNS_CONTAINER. Passing the same id put two nodes with one id on the
  page, and it did it again on every 30 second tick. Dash resolves a duplicate
  id to whichever it finds first, so the callback could start writing into a
  node nested inside its own output.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{HomeIds.RECENT_RUNS_CONTAINER}.children")

  response = dash_http.fire(
      dash_client, dep, {f"{HomeIds.INTERVAL}.n_intervals": 1}
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  body = dash_http.body(response)["response"]
  children = body[HomeIds.RECENT_RUNS_CONTAINER]["children"]
  assert HomeIds.RECENT_RUNS_CONTAINER not in _ids(children)
  # The table is still there. An empty container would also have no duplicate.
  assert f"/evaluations/runs/{seeded.run_id}" in str(children)


def test_the_run_table_still_takes_an_id_when_it_is_asked_for_one():
  """The parameter is not dead, so the fix belongs at the call site.

  Other callers render the table into a container of their own and address it
  by this id. Dropping the argument where the home dashboard calls it is the
  fix. Dropping it from the component would break them.
  """
  # The id goes on the div inside the Paper, which is the Paper's one child.
  assert render_run_table([], table_id="a-table").children.id == "a-table"
  assert not hasattr(render_run_table([]).children, "id")
