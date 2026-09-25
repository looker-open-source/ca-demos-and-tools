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

"""Dispatch tests for the app shell: home, nav, 404 and error handling.

These callbacks are mounted on every page, so a regression here is not
confined to one route. They are fired through ``/_dash-update-component`` the
way ``test_callback_dispatch.py`` does.
"""

from __future__ import annotations
import dash
from prism.ui import utils

# Importing the app registers every page and every callback.
from prism.ui.app import app
from prism.ui.callbacks import shell_callbacks
from prism.ui.callbacks import test_suite_callbacks
from prism.ui.components import shell
from prism.ui.constants import GLOBAL_PROJECT_ID_STORE
from prism.ui.ids import ShellIds
from prism.ui.ids import TestSuiteHomeIds
from prism.ui.pages.home_ids import HomeIds
import pytest
from tests.ui import dash_http

_PAGE_PATHS = sorted(page["path"] for page in dash.page_registry.values())

# In the order update_active_nav_link declares its outputs.
_NAV_LINKS = (
    ShellIds.NAV_OVERVIEW,
    ShellIds.NAV_AGENTS,
    ShellIds.NAV_EVALUATIONS,
    ShellIds.NAV_TEST_SUITES,
    ShellIds.NAV_COMPARISON,
)

# The registrations that reach Dash without ``prism.ui.utils.handle_errors``,
# so a raise there is a bare 500 with nothing on screen. This list may only
# shrink. Adding a raw ``@callback`` anywhere fails the test below. The eight
# that used to be here were the context prototype page's, and they went with
# it.
_UNHANDLED_CALLBACKS = frozenset()


def _registered_prism_callbacks(dash_client):
  """Every server-side callback the app registered, by qualified name.

  Reading the map rather than the source catches a registration the AST would
  miss, and it is the same map the dispatch route dispatches on. The GET is
  what moves Dash's module-level registrations onto the app.
  """
  dash_http.dependencies(dash_client)
  found = {}
  for entry in app.callback_map.values():
    registered = entry.get("callback")
    if registered is None:
      continue  # A clientside callback, which runs in the browser.
    # dash.callback wraps with functools.wraps, so __wrapped__ is whatever was
    # handed to it: either handle_errors' wrapper or the callback itself.
    inner = registered.__wrapped__
    if not inner.__module__.startswith("prism."):
      continue  # Dash's own pages router.
    found[f"{inner.__module__}.{inner.__qualname__}"] = inner
  return found


def _is_error_handled(inner) -> bool:
  """Whether ``handle_errors`` sits between Dash and the callback body."""
  code = inner.__code__
  return code.co_name == "wrapper" and code.co_filename.endswith("ui/utils.py")


def test_every_registered_callback_is_error_handled(dash_client):
  """A raise inside a callback must not reach the user as a bare 500.

  ``typed_callback`` applies ``handle_errors`` to everything it registers, so
  the only way to miss it is to register with a raw ``@callback``. None do
  today, which is why the list above is empty. The point of the comparison is
  the other direction: a new raw ``@callback`` shows up here as a name the
  list does not have.
  """
  registered = _registered_prism_callbacks(dash_client)
  assert registered, "no prism callbacks registered"

  unhandled = {
      name for name, inner in registered.items() if not _is_error_handled(inner)
  }
  new = unhandled - _UNHANDLED_CALLBACKS
  assert not new, (
      "these callbacks bypass handle_errors, so a raise in them is a 500 with"
      f" nothing on screen: {sorted(new)}"
  )
  fixed = _UNHANDLED_CALLBACKS - unhandled
  assert not fixed, (
      "these are handled now, so drop them from _UNHANDLED_CALLBACKS:"
      f" {sorted(fixed)}"
  )


def test_the_home_dashboard_renders_the_runs_that_exist(
    dash_client, callback_errors, seeded
):
  """The home page has to serialize the rows in the database.

  ``update_dashboard`` is driven by ``home-interval``, not the URL, so the
  page-load sweep never fires it and nothing else runs it against real rows.
  It goes through ``DashboardClient``, which returns pydantic models with
  timestamps and Decimals on them, so the JSON encoder is part of what is
  under test here.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{HomeIds.CHART_CONTAINER}.children")

  response = dash_http.fire(
      dash_client, dep, {f"{HomeIds.INTERVAL}.n_intervals": 1}
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  rendered = dash_http.body(response)["response"]
  assert HomeIds.CHART_CONTAINER in rendered
  assert HomeIds.VOLUME_CHART_CONTAINER in rendered
  recent = str(rendered[HomeIds.RECENT_RUNS_CONTAINER])
  assert seeded.agent_name in recent, recent[:2000]


@pytest.mark.parametrize(
    "pathname,active",
    [
        ("/", ShellIds.NAV_OVERVIEW),
        ("/agents", ShellIds.NAV_AGENTS),
        ("/agents/onboard/existing", ShellIds.NAV_AGENTS),
        ("/evaluations", ShellIds.NAV_EVALUATIONS),
        ("/evaluations/runs/1", ShellIds.NAV_EVALUATIONS),
        ("/test_suites", ShellIds.NAV_TEST_SUITES),
        ("/compare", ShellIds.NAV_COMPARISON),
    ],
)
def test_the_header_highlights_the_section_you_are_on(
    dash_client, callback_errors, pathname, active
):
  """One header link is blue on each route family and the other four are not.

  The sweep in ``test_callback_dispatch.py`` fires this callback on every
  route but only checks the status code, so five "black" would pass it. The
  detail pages are in here because the match is a prefix: highlighting the
  section only on its list page is the regression this catches.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{_NAV_LINKS[0]}.c")

  response = dash_http.fire_url(dash_client, dep, pathname)

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  colors = dash_http.body(response)["response"]
  got = {link: colors[link]["c"] for link in _NAV_LINKS}
  assert got == {
      link: "blue" if link == active else "black" for link in _NAV_LINKS
  }, got


def test_only_the_root_path_highlights_overview():
  """Overview is reachable at ``/`` and nowhere else.

  ``update_active_nav_link`` also matches ``/overview``. No page registers
  that path and the header link points at ``/``, so that disjunct is dead. If
  a page ever claims ``/overview`` this fails, and the case list above needs
  it.
  """
  assert "/overview" not in _PAGE_PATHS

  hrefs = {
      component.id: component.href
      for component in shell.render_header()._traverse()  # pylint: disable=protected-access
      if getattr(component, "id", None) in _NAV_LINKS
  }
  assert hrefs[ShellIds.NAV_OVERVIEW] == "/"


def test_an_unknown_route_renders_the_404_layout(dash_client, callback_errors):
  """A typo in the URL has to say so, not render an empty page container.

  Dash's pages router is an ordinary server-side callback, so the 404 branch
  is readable over HTTP. The sweep only walks registered routes and never
  reaches it.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, "_pages_content.children")

  missing = dash_http.body(
      dash_http.fire_url(dash_client, dep, "/no-such-page")
  )
  assert "404 - Page not found" in str(missing["response"])

  # The other half, because a router that answered 404 for everything would
  # pass the assertion above.
  found = dash_http.body(dash_http.fire_url(dash_client, dep, "/test_suites"))
  assert "404 - Page not found" not in str(found["response"])

  callback_errors.assert_none()


def test_the_project_id_is_not_refetched_when_the_store_is_filled(
    dash_client, callback_errors, monkeypatch
):
  """Navigation must not cost an ADC round trip per page.

  ``fetch_current_project_id`` fires on every navigation because its input is
  the pathname. The guard on the current store value is the only thing
  stopping it from calling ``google.auth.default()`` each time, and from
  overwriting a project the user has since changed.
  """
  calls = []

  class _Agents:

    def get_current_gcp_project(self):
      calls.append(1)
      return "fetched-project"

  class _Client:
    agents = _Agents()

  monkeypatch.setattr(shell_callbacks, "get_client", _Client)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{GLOBAL_PROJECT_ID_STORE}.data")

  empty = dash_http.fire(dash_client, dep, {"url.pathname": "/agents"})
  assert empty.status_code == 200, empty.data[:2000]
  assert (
      dash_http.body(empty)["response"][GLOBAL_PROJECT_ID_STORE]["data"]
      == "fetched-project"
  )
  assert len(calls) == 1

  filled = dash_http.fire(
      dash_client,
      dep,
      {
          "url.pathname": "/evaluations",
          f"{GLOBAL_PROJECT_ID_STORE}.data": "already-known",
      },
  )
  # no_update writes nothing, so the response carries no properties at all.
  assert filled.status_code == 200, filled.data[:2000]
  assert dash_http.body(filled)["response"] == {}, filled.data[:2000]
  assert len(calls) == 1, "the store was already filled"

  callback_errors.assert_none()


class _Clock:
  """A monotonic clock the test moves by hand."""

  def __init__(self):
    self.now = 1000.0

  def monotonic(self) -> float:
    return self.now


def test_a_failure_after_the_window_raises_another_toast(
    dash_client, callback_errors, monkeypatch
):
  """The toast throttle has to expire, or a lasting failure goes quiet.

  ``test_a_burst_of_failures_raises_one_toast`` pins the suppress half with
  the clock standing still. A throttle that never reopened would pass it and
  leave the user with one toast for a database that is down all afternoon.
  """
  clock = _Clock()
  monkeypatch.setattr(utils, "time", clock)

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(test_suite_callbacks, "get_client", boom)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")

  def fail_once():
    return dash_http.body(dash_http.fire_url(dash_client, dep, "/test_suites"))

  assert "sideUpdate" in fail_once(), "the first failure is never throttled"

  clock.now += utils._TOAST_WINDOW_SECONDS - 1  # pylint: disable=protected-access
  assert "sideUpdate" not in fail_once(), "still inside the window"

  clock.now += 2
  assert "sideUpdate" in fail_once(), "the window expired, so say so again"

  assert len(callback_errors.messages) == 3, "every failure has a log line"
  callback_errors.clear()


def test_one_readers_failure_does_not_silence_anothers_toast(
    dash_client, callback_errors, monkeypatch
):
  """The throttle window belongs to the reader, not to the process.

  The Dockerfile runs one gunicorn worker for eight threads, so a window held
  in a module global was shared by everybody on the server. The first reader
  to hit a failure took the next 30 seconds of toasts away from the rest, and
  their pages stopped short with nothing said.
  """

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(test_suite_callbacks, "get_client", boom)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")

  def fail_once(client):
    return dash_http.body(dash_http.fire_url(client, dep, "/test_suites"))

  assert "sideUpdate" in fail_once(dash_client), "the first failure is shown"
  assert "sideUpdate" not in fail_once(dash_client), "same reader, throttled"

  # A separate client is a separate cookie jar, which is what a second browser
  # against the same worker is.
  assert "sideUpdate" in fail_once(
      app.server.test_client()
  ), "a second reader gets their own toast"

  assert len(callback_errors.messages) == 3, "every failure has a log line"
  callback_errors.clear()
