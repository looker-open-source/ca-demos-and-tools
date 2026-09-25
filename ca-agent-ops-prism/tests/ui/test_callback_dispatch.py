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

"""Tests that fire callbacks through Dash's own HTTP route.

``tests/ui/test_callback_contracts.py`` decides everything it can from the
callback map without running anything. These run the callbacks, against the
test database, through ``/_dash-update-component``, and check what comes back
over the wire.

They are not a browser suite and do not replace one. Nothing here sees the gap
between a click and its response (``running=`` guards against a double click,
and a synchronous POST has no such gap), dmc portals and overlays, layout or
visibility, the six clientside callbacks, or how React applies what the server
returned.
"""

from __future__ import annotations
import re
import dash
import pytest
from tests.ui import dash_http

# Importing the app registers every page and every callback.
from prism.common.schemas.execution import RunStatus
from prism.server.models.example import Example
from prism.server.models.run import Run
from prism.ui import utils
from prism.ui.app import app  # pylint: disable=unused-import
from prism.ui.callbacks import run_comparison_callbacks
from prism.ui.callbacks import test_suite_callbacks
from prism.ui.components import eval_run_modal
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import ComparisonIds
from prism.ui.ids import EvaluationIds
from prism.ui.ids import TestSuiteHomeIds
from prism.ui.ids import TestSuiteIds
from prism.ui.pages.agent_ids import AgentIds

_PAGE_PATHS = sorted(page["path"] for page in dash.page_registry.values())


@pytest.mark.parametrize("pathname", _PAGE_PATHS)
def test_every_page_load_callback_survives_every_route(
    dash_client, callback_errors, pathname
):
  """No page-load callback may fail on any route the app registers.

  Every URL-driven callback is fired for every page, not just for the page it
  belongs to. That is what the browser does: they are all mounted in the app
  shell and all see every navigation, so a callback that assumes its own
  pathname is a defect on all the others.

  The database is empty here on purpose. A fresh install is a real state, and
  rendering nothing is where the None handling lives.
  """
  deps = dash_http.url_only(dash_http.dependencies(dash_client))
  assert deps, "no URL-driven callbacks registered"

  for dep in deps:
    response = dash_http.fire_url(dash_client, dep, pathname)
    assert response.status_code in (200, 204), (
        f"{dep['output']} answered {response.status_code} on {pathname}:\n"
        f"{response.data[:2000].decode(errors='replace')}"
    )
    # A 200 whose body will not decode means the callback returned something
    # the JSON encoder could not take.
    dash_http.body(response)

  callback_errors.assert_none(f"on {pathname}")


def test_page_load_callbacks_render_the_rows_that_exist(
    dash_client, callback_errors, seeded
):
  """The list pages must serialize the rows in the database, not empty ones.

  Without this, the sweep above stays green on a callback that answers 200 with
  empty children for everything.
  """
  deps = dash_http.dependencies(dash_client)
  cases = [
      (
          "/evaluations",
          f"{EvaluationIds.RUN_LIST_CONTAINER}.children",
          seeded.agent_name,
      ),
      ("/evaluations", f"{EvaluationIds.FILTER_AGENT}.data", seeded.agent_name),
      (
          "/test_suites",
          f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children",
          seeded.suite_name,
      ),
  ]

  for pathname, address, expected in cases:
    dep = dash_http.find(deps, address)
    response = dash_http.fire_url(dash_client, dep, pathname)
    assert (
        response.status_code == 200
    ), f"{address} answered {response.status_code} on {pathname}"
    rendered = response.data.decode()
    assert (
        expected in rendered
    ), f"{address} rendered without {expected!r}:\n{rendered[:2000]}"

  callback_errors.assert_none()


def test_archiving_a_run_over_http_writes_the_row_and_notifies(
    dash_client, callback_errors, db_session, seeded
):
  """Archiving from the UI must reach the database and say so.

  ``test_archive_notifications.py`` checks the notification shape with the
  client mocked out. This runs the same callback with the real dependency
  chain, so it also covers the write and the serialization of what comes back.
  """
  # Archiving a run that has not finished is refused, because the worker's
  # queries all skip archived runs and the run would never come back. The
  # seeded run is PENDING, so it is finished first. The refusal itself is
  # covered in test_dispatch_evaluations_list.py.
  db_session.get(Run, seeded.run_id).status = RunStatus.COMPLETED
  db_session.commit()

  deps = dash_http.dependencies(dash_client)
  archive = [
      dep
      for dep in deps
      if any(i["id"] == EvaluationIds.BTN_ARCHIVE for i in dep["inputs"])
  ]
  assert len(archive) == 1, f"expected one archive callback, got {len(archive)}"

  pathname = f"/evaluations/runs/{seeded.run_id}"
  response = dash_http.fire(
      dash_client,
      archive[0],
      {EvaluationIds.BTN_ARCHIVE + ".n_clicks": 1, "url.pathname": pathname},
      changed=[EvaluationIds.BTN_ARCHIVE + ".n_clicks"],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  notifications = dash_http.body(response)["response"][NOTIFICATION_CONTAINER]
  # NotificationContainer takes a list of actions and silently drops a bare
  # dict, so the toast only appears if this is a list.
  assert isinstance(notifications["sendNotifications"], list)

  db_session.expire_all()
  assert db_session.get(Run, seeded.run_id).is_archived


def test_toggling_one_assertion_switch_weights_that_assertion(
    dash_client, callback_errors, db_session, seeded
):
  """A row of switches share one id pattern, and only the clicked one counts.

  ``toggle_assertion_weight`` takes every switch on the page as one ALL input,
  so the value it acts on comes out of ``ctx.triggered``, not out of the list.
  Reading the list instead would weight whichever assertion happens to be
  first. Two switches go in here, with the second one flipped, so a callback
  that ignored the trigger would write to the wrong assertion and the weights
  below would come back the other way round.
  """
  example = (
      db_session.query(Example).filter_by(test_suite_id=seeded.suite_id).one()
  )
  test_case = {
      "id": example.id,
      "question": seeded.question,
      "asserts": [
          {"type": "text-contains", "value": "first", "weight": 1},
          {"type": "text-contains", "value": "second", "weight": 1},
      ],
  }

  deps = dash_http.dependencies(dash_client)
  toggles = [
      dep
      for dep in deps
      if any(
          TestSuiteIds.ASSERT_TOGGLE_ACCURACY in str(i["id"])
          for i in dep["inputs"]
      )
  ]
  assert len(toggles) == 1, f"expected one weight toggle, got {len(toggles)}"
  dep = toggles[0]
  switches = dep["inputs"][0]

  response = dash_http.fire(
      dash_client,
      dep,
      {
          dash_http.address(switches): [(0, True), (1, False)],
          f"{TestSuiteIds.STORE_BUILDER}.data": [test_case],
          f"{TestSuiteIds.STORE_SELECTED_INDEX}.data": 0,
          "url.pathname": f"/test_suites/edit/{seeded.suite_id}",
      },
      changed=[dash_http.pattern_address(switches, 1)],
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()

  stored = dash_http.body(response)["response"][TestSuiteIds.STORE_BUILDER][
      "data"
  ]
  weights = [a["weight"] for a in stored[0]["asserts"]]
  assert weights == [1, 0], weights

  db_session.expire_all()
  written = [a.weight for a in db_session.get(Example, example.id).asserts]
  assert written == [1, 0], written


def test_an_error_swallowed_by_handle_errors_still_fails_the_gate(
    dash_client, callback_errors, monkeypatch
):
  """A callback that logs instead of raising must not read as a pass.

  ``@handle_errors`` turns an exception into a logged traceback and a 200
  carrying ``no_update``, which over HTTP is identical to a callback that had
  nothing to do. Without this test the other three could be green because the
  gate never sees anything.
  """

  def boom(unused_search):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(run_comparison_callbacks, "_parse_search", boom)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  response = dash_http.fire_url(dash_client, dep, "/compare")

  assert response.status_code == 200, "handle_errors should have caught it"
  assert any(
      "seeded failure" in m for m in callback_errors.messages
  ), f"the gate saw {callback_errors.messages}"
  # Otherwise the teardown of the other tests' gate would fail this one.
  callback_errors.clear()


def test_a_failed_callback_raises_a_toast(
    dash_client, callback_errors, monkeypatch
):
  """A callback that fails has to say so on screen.

  ``handle_errors`` returns ``no_update``, so without the toast the page keeps
  its old contents and the click reads as having done nothing. The callback
  under test declares no notification output. It reaches the container through
  ``dash.set_props``, which Dash returns in ``sideUpdate``.
  """

  def boom(unused_search):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(run_comparison_callbacks, "_parse_search", boom)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  assert NOTIFICATION_CONTAINER not in dep["output"]

  body = dash_http.body(dash_http.fire_url(dash_client, dep, "/compare"))
  notifications = body["sideUpdate"][NOTIFICATION_CONTAINER][
      "sendNotifications"
  ]
  # NotificationContainer takes a list of actions and silently drops a bare
  # dict, so the toast only appears if this is a list.
  assert isinstance(notifications, list), notifications

  message = notifications[0]["message"]
  # The exception text stays in the log. A SQLAlchemy error carries the
  # statement and its parameters, which is not something to render.
  assert "seeded failure" not in message, message
  ref = re.search(r"ref ([0-9a-f]{6})", message)
  assert ref, f"no reference to find the traceback by: {message}"
  assert any(
      ref.group(1) in m for m in callback_errors.messages
  ), f"ref {ref.group(1)} is in the toast but not the log"

  callback_errors.clear()


def test_a_toast_is_addressed_so_the_client_can_collapse_repeats(
    dash_client, callback_errors, monkeypatch
):
  """The toast needs the id and the lifetime that make deduplication work.

  Mantine's ``show`` drops a notification whose id is already on screen, so
  every callback failure reuses one id. That only helps while the toast is
  still there, which is why it does not close itself.
  """

  def boom(unused_search):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(run_comparison_callbacks, "_parse_search", boom)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")
  body = dash_http.body(dash_http.fire_url(dash_client, dep, "/compare"))

  toast = body["sideUpdate"][NOTIFICATION_CONTAINER]["sendNotifications"][0]
  assert toast["id"] == utils.TOAST_ID
  assert toast["autoClose"] is False

  callback_errors.clear()


def test_a_burst_of_failures_raises_one_toast(
    dash_client, callback_errors, monkeypatch
):
  """Repeated and simultaneous failures must not stack up toasts.

  Two bursts happen in practice. ``evaluation_detail`` and ``trial_detail``
  poll every 3 seconds while a run is going, so one broken callback there would
  raise 20 toasts a minute. And a page load fires every URL-driven callback at
  once, so a database that is down fails all of them together.

  The throttle is one window across all callbacks, not one per callback, which
  is why the last failure below is a different callback and still silent. Every
  failure keeps its own log line.
  """

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(test_suite_callbacks, "get_client", boom)
  monkeypatch.setattr(run_comparison_callbacks, "_parse_search", boom)

  deps = dash_http.dependencies(dash_client)
  polled = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")
  other = dash_http.find(deps, f"{ComparisonIds.METRICS_CARDS}.children")

  bodies = [
      dash_http.body(dash_http.fire_url(dash_client, polled, "/test_suites"))
      for _ in range(5)
  ]
  bodies.append(
      dash_http.body(dash_http.fire_url(dash_client, other, "/compare"))
  )

  toasted = [b for b in bodies if "sideUpdate" in b]
  assert len(toasted) == 1, f"{len(toasted)} of 6 failures raised a toast"
  assert (
      len(callback_errors.messages) == 6
  ), "every failure still has a log line"

  callback_errors.clear()


def test_a_callback_that_never_opted_in_is_still_handled(
    dash_client, callback_errors, monkeypatch
):
  """``typed_callback`` has to apply the handling, not the callback author.

  ``update_test_suites_list`` carries no ``@handle_errors``. Before
  ``typed_callback`` applied it, this raised out of the callback and the route
  answered 500 with nothing on screen.
  """

  def boom(*unused_args, **unused_kwargs):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(test_suite_callbacks, "get_client", boom)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")
  response = dash_http.fire_url(dash_client, dep, "/test_suites")

  assert response.status_code == 200, response.data[:500]
  assert "sideUpdate" in dash_http.body(response), "no toast"
  assert any("seeded failure" in m for m in callback_errors.messages)

  callback_errors.clear()


def test_prevent_update_is_not_treated_as_a_failure(
    dash_client, callback_errors, monkeypatch
):
  """PreventUpdate has to reach Dash, not the error handler.

  It subclasses Exception, so the broad catch in ``handle_errors`` will take it
  and report "do nothing" to the user as a failure. No callback raises it
  today. Now that every callback is wrapped, the first one that does would find
  out the hard way.
  """

  def prevent(*unused_args, **unused_kwargs):
    raise dash.exceptions.PreventUpdate

  monkeypatch.setattr(test_suite_callbacks, "get_client", prevent)

  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{TestSuiteHomeIds.TEST_SUITES_LIST}.children")
  response = dash_http.fire_url(dash_client, dep, "/test_suites")

  assert response.status_code == 204, (
      "PreventUpdate should answer 204, not"
      f" {response.status_code}: {response.data[:500]}"
  )
  callback_errors.assert_none()


def test_the_eval_modal_close_button_is_wired_to_something(
    dash_client, callback_errors
):
  """The X in the modal header used to have an id and no listener.

  It was built as ``BTN_CANCEL + "-x"``, which no callback declares, so the
  only way out of the modal was the Cancel button. Nothing caught it: an id
  that no callback mentions is invisible to the callback map, and the
  component renders and clicks fine.
  """
  # Both halves, because either one alone is green on the bug. A callback can
  # declare an id the layout never renders, and the layout can render an id no
  # callback declares. That second one is what shipped.
  rendered = {
      component.id
      for component in eval_run_modal.render_modal()._traverse()
      if isinstance(getattr(component, "id", None), str)
  }
  assert AgentIds.Detail.EvalModal.BTN_CLOSE in rendered

  deps = dash_http.dependencies(dash_client)
  closers = [
      dep
      for dep in deps
      if any(
          i["id"] == AgentIds.Detail.EvalModal.BTN_CLOSE for i in dep["inputs"]
      )
  ]
  assert closers, "nothing listens to the eval modal close button"

  address = AgentIds.Detail.EvalModal.BTN_CLOSE + ".n_clicks"
  response = dash_http.fire(
      dash_client, closers[0], {address: 1}, changed=[address]
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  opened = dash_http.body(response)["response"][AgentIds.Detail.EvalModal.ROOT][
      "opened"
  ]
  assert opened is False
