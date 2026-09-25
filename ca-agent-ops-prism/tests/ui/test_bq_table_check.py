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

"""The Test Tables button on the two agent config forms.

Looker credentials have had a Test Connection button since the start. BigQuery
had nothing, so the first time anyone learned a table was wrong was a run where
every trial failed. Both forms now have the same button, and both have to
report the same thing, because the same agent is edited through either one.
"""

from __future__ import annotations

from typing import Any, Iterator
from unittest import mock

import dash
from dash import _callback
import dash_mantine_components as dmc
from prism.ui.callbacks import agent_add_callbacks
from prism.ui.callbacks import agent_detail_callbacks
from prism.ui.components.agent_components import render_bq_check_results
from prism.ui.pages.agent_ids import AgentIds
import pytest

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import

# The two forms, and what each one calls its button and its alert.
_FORMS = [
    (
        agent_add_callbacks.test_bq_tables_add,
        AgentIds.Form.BTN_TEST_BQ,
        AgentIds.Form.ALERT_BQ_TEST,
        "prism.ui.callbacks.agent_add_callbacks.get_client",
    ),
    (
        agent_detail_callbacks.test_bq_tables,
        AgentIds.Detail.BTN_TEST_BQ,
        AgentIds.Detail.ALERT_BQ_TEST,
        "prism.ui.callbacks.agent_detail_callbacks.get_client",
    ),
]


def _callback_list() -> list[dict[str, Any]]:
  """Every registered spec, in the shape that carries ``running``."""
  return (
      _callback.GLOBAL_CALLBACK_LIST
      or app._callback_list  # pylint: disable=protected-access
  )


def _walk(component: Any) -> Iterator[Any]:
  """Yields every component in a rendered tree, depth first."""
  yield component
  children = getattr(component, "children", None)
  if children is None:
    return
  if not isinstance(children, (list, tuple)):
    children = [children]
  for child in children:
    if child is not None and not isinstance(child, (str, int, float)):
      yield from _walk(child)


def _all_page_components() -> list[Any]:
  """Every component in every registered page layout."""
  components = []
  for page in dash.page_registry.values():
    layout = page.get("layout")
    if callable(layout):
      try:
        layout = layout()
      except TypeError:
        continue
    if layout is not None:
      components.extend(_walk(layout))
  return components


@pytest.fixture(name="page_components", scope="module")
def _page_components() -> list[Any]:
  return _all_page_components()


def _find(components: list[Any], component_id: str) -> Any:
  found = [c for c in components if getattr(c, "id", None) == component_id]
  assert len(found) == 1, f"expected one {component_id}, got {len(found)}"
  return found[0]


def _ok(table: str) -> dict[str, str]:
  return {"table": table, "status": "ok", "message": "Found."}


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_both_forms_have_the_button(
    page_components, callback, button_id, alert_id, patch
):
  """The agent is edited through either form, so both need the check."""
  del callback, patch
  assert isinstance(_find(page_components, button_id), dmc.Button)
  assert isinstance(_find(page_components, alert_id), dmc.Alert)


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_the_alert_is_hidden_until_the_button_is_pressed(
    page_components, callback, button_id, alert_id, patch
):
  del callback, button_id, patch
  assert _find(page_components, alert_id).hide is True


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_pressing_the_button_checks_every_line(
    callback, button_id, alert_id, patch
):
  """The textarea holds one table per line, and all of them get checked."""
  del button_id, alert_id
  with mock.patch(patch) as factory:
    agents = factory.return_value.agents
    agents.check_bigquery_tables.return_value = [_ok("p.d.a"), _ok("p.d.b")]

    _, hide, color = callback(1, "p.d.a\np.d.b")

  agents.check_bigquery_tables.assert_called_once_with(
      tables=["p.d.a", "p.d.b"]
  )
  assert hide is False
  assert color == "green"


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_an_empty_textarea_does_not_call_bigquery(
    callback, button_id, alert_id, patch
):
  """Nothing to check is not a failure, and it is not worth a round trip."""
  del button_id, alert_id
  with mock.patch(patch) as factory:
    children, hide, color = callback(1, "")

    factory.return_value.agents.check_bigquery_tables.assert_not_called()

  assert "Enter at least one table" in children
  assert (hide, color) == (False, "orange")


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_a_failed_check_says_so_without_quoting_the_exception(
    callback, button_id, alert_id, patch
):
  """One round trip per table, so the call has plenty of ways to fail.

  What it raises names the project and the table it was reading, and this
  alert renders in the page.
  """
  del button_id, alert_id
  with mock.patch(patch) as factory:
    agents = factory.return_value.agents
    agents.check_bigquery_tables.side_effect = RuntimeError("boom")

    children, hide, color = callback(1, "p.d.a")

  assert "boom" not in children
  assert "server log" in children
  assert (hide, color) == (False, "red")


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_the_button_spins_for_the_length_of_the_check(
    callback, button_id, alert_id, patch
):
  """One round trip per table, so this is the slowest button on the form.

  A ``loading`` value returned with the result cannot show a spinner: the
  round trip is over by the time it arrives. Only ``running=`` can.
  """
  del callback, alert_id, patch
  specs = [
      spec
      for spec in _callback_list()
      if any(
          dep.get("id") == button_id and dep.get("property") == "n_clicks"
          for dep in spec["inputs"]
      )
  ]
  assert specs, f"{button_id}: no callback takes it as an Input"
  for spec in specs:
    while_running = spec.get("running", {}).get("running", {})
    assert while_running.get(f"{button_id}.loading") is True


@pytest.mark.parametrize("callback,button_id,alert_id,patch", _FORMS)
def test_the_alert_stays_hidden_on_a_page_load(
    callback, button_id, alert_id, patch
):
  """Dash fires the callback with no clicks when the modal first renders."""
  del button_id, alert_id
  with mock.patch(patch) as factory:
    children, hide, _ = callback(None, "p.d.a")

    factory.return_value.agents.check_bigquery_tables.assert_not_called()

  assert children is dash.no_update
  assert hide is True


def test_a_clean_result_reads_as_a_pass():
  children, color = render_bq_check_results([_ok("p.d.a"), _ok("p.d.b")])

  assert color == "green"
  assert "All 2 tables are readable." in str(children)


def test_one_failure_colours_the_whole_alert():
  """A green alert with one red badge in it reads as a pass at a glance."""
  results = [
      _ok("p.d.a"),
      {"table": "p.d.b", "status": "not_found", "message": "No such table."},
  ]

  children, color = render_bq_check_results(results)

  assert color == "red"
  assert "1 of 2 tables could not be read." in str(children)


@pytest.mark.parametrize(
    "status,badge_color",
    [
        ("ok", "green"),
        ("invalid", "red"),
        ("not_found", "red"),
        ("denied", "orange"),
        ("error", "red"),
    ],
)
def test_each_status_gets_its_own_badge_colour(status, badge_color):
  """Permission denied is not the same failure as a wrong path."""
  children, _ = render_bq_check_results(
      [{"table": "p.d.a", "status": status, "message": "m"}]
  )

  badges = [c for c in _walk(children) if isinstance(c, dmc.Badge)]
  assert len(badges) == 1
  assert badges[0].color == badge_color


def test_an_unknown_status_is_treated_as_a_failure():
  """A status the UI has not been taught must not render as a pass."""
  children, color = render_bq_check_results(
      [{"table": "p.d.a", "status": "something-new", "message": "m"}]
  )

  assert color == "red"
  assert "1 of 1 tables could not be read." in str(children)


def test_every_table_is_named_in_the_result():
  """The message has to say which line to fix."""
  results = [
      _ok("p.d.a"),
      {"table": "p.d.b", "status": "denied", "message": "no grant"},
  ]

  rendered = str(render_bq_check_results(results)[0])

  assert "p.d.a" in rendered
  assert "p.d.b" in rendered
  assert "no grant" in rendered
