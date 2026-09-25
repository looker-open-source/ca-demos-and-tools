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

"""Every exit from the suggestion poll has to signal the panel.

``poll_suggestion_results`` has four ways out and three of them stop the
interval. Stopping it is only half of the handshake. The suggestions panel is
drawn by ``render_trial_detail``, which takes the signal as an Input and the
loading flag only as State, so a poll that clears the flag without touching the
signal re-renders nothing. The skeleton stays on screen with the interval now
disabled and nothing left to turn it off.

The arrival branch always signalled, because there was something new to show.
The timeout and the failure branches did not.
"""

from __future__ import annotations

import types
from typing import Any

from prism.server.models.run import Trial
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.ids import EvaluationIds as Ev
from tests.ui import dash_http

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import

# The wildcard output, addressed the way the graph spells it.
_SPINNERS = dash_http.address({
    "id": {"type": Ev.SUGGEST_BTN_TYPE, "index": ["ALL"]},
    "property": "loading",
})
_SPINNER = f'{{"index":0,"type":"{Ev.SUGGEST_BTN_TYPE}"}}.loading'


def _callback(
    deps: list[dict[str, Any]], output: str, *inputs: str
) -> dict[str, Any]:
  """The one callback with this output and these Inputs, in order.

  Four callbacks write the signal, all with allow_duplicate, so the output
  address does not name one of them. The Input side does.
  """
  matches = [
      dep
      for dep in deps
      if output in dep["output"]
      and len(dep["inputs"]) == len(inputs)
      and all(
          want in str(got["id"]) for want, got in zip(inputs, dep["inputs"])
      )
  ]
  assert len(matches) == 1, (
      f"expected one callback writing {output} from {list(inputs)}, found"
      f" {len(matches)}"
  )
  return matches[0]


def _values(response) -> dict[str, Any]:
  """The property values a 200 carries, keyed by ``<id>.<property>``.

  An output the callback returned no_update for is left out, so a missing key
  is the assertion that nothing was written.
  """
  written = dash_http.body(response).get("response", {})
  return {
      f"{component_id}.{prop}": value
      for component_id, props in written.items()
      for prop, value in props.items()
  }


def _trial_id(db_session, run_id: int) -> int:
  """The completed trial from the seeded run, which has no suggestions."""
  rows = (
      db_session.query(Trial).filter_by(run_id=run_id).order_by(Trial.id).all()
  )
  return rows[-1].id


def _poll(dash_client, trial_id: int, n_intervals: int) -> dict[str, Any]:
  """One tick of the polling interval on the trial page."""
  deps = dash_http.dependencies(dash_client)
  dep = _callback(
      deps, f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data", Ev.TRIAL_SUG_POLLING_INTERVAL
  )
  buttons = dep["state"][1]
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.n_intervals": n_intervals,
          "url.pathname": f"/evaluations/trials/{trial_id}",
          dash_http.address(buttons): [
              (0, {"type": Ev.SUGGEST_BTN_TYPE, "index": 0})
          ],
      },
      rendered={_SPINNERS: [0]},
  )
  assert response.status_code == 200, response.data[:2000]
  return _values(response)


def test_the_timeout_signals_so_the_panel_stops_showing_a_skeleton(
    dash_client, callback_errors, db_session, seeded
):
  """Sixty seconds with nothing generated still has to redraw the panel.

  The timeout cleared the loading flag and disabled the interval and left the
  signal alone, so the panel was never asked to render again. It kept the
  skeleton it had, and the interval that would have replaced it was off.
  ``render_empty_suggestions`` is what belongs there.
  """
  trial_id = _trial_id(db_session, seeded.run_id)

  values = _poll(dash_client, trial_id, 20)

  callback_errors.assert_none()
  assert values[
      f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data"
  ], "no signal on the timeout"
  assert values[f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.disabled"] is True
  assert values[f"{Ev.TRIAL_SUG_LOADING_STORE}.data"] is False
  assert values[_SPINNER] is False


def test_a_failed_read_signals_too(
    dash_client, callback_errors, db_session, monkeypatch, seeded
):
  """The same dead end, reached by the poll's read blowing up.

  This branch gives up for good, so it is the one place where leaving the
  skeleton up is permanent.
  """
  trial_id = _trial_id(db_session, seeded.run_id)

  def get_trial(unused_trial_id):
    raise RuntimeError("seeded failure")

  monkeypatch.setattr(
      evaluation_callbacks,
      "get_client",
      lambda: types.SimpleNamespace(
          runs=types.SimpleNamespace(get_trial=get_trial)
      ),
  )

  values = _poll(dash_client, trial_id, 3)

  callback_errors.assert_logged("Polling failed for trial")
  assert values[
      f"{Ev.TRIAL_SUG_UPDATE_SIGNAL}.data"
  ], "no signal on the failure"
  assert values[f"{Ev.TRIAL_SUG_POLLING_INTERVAL}.disabled"] is True
  assert values[f"{Ev.TRIAL_SUG_LOADING_STORE}.data"] is False
  assert values[_SPINNER] is False


def test_a_tick_that_is_still_waiting_signals_nothing(
    dash_client, callback_errors, db_session, seeded
):
  """The interval fires every three seconds, and only the exits redraw.

  Signalling on every tick would rebuild the whole trial page twenty times
  over while the generation runs.
  """
  trial_id = _trial_id(db_session, seeded.run_id)

  assert _poll(dash_client, trial_id, 3) == {}
  callback_errors.assert_none()


def test_the_panel_only_redraws_on_the_signal(dash_client):
  """Why the exits have to write it, read off the dependency graph.

  ``render_trial_detail`` has the signal as an Input and the loading store as
  State. Dash does not fire a callback for a State change, so writing the flag
  alone changes nothing on screen. If the loading store ever becomes an Input
  here, this test is the place to reconsider the three signals.
  """
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{Ev.TRIAL_DETAIL_CONTAINER}.children")

  assert Ev.TRIAL_SUG_UPDATE_SIGNAL in [i["id"] for i in dep["inputs"]]
  assert Ev.TRIAL_SUG_LOADING_STORE in [s["id"] for s in dep["state"]]
  assert Ev.TRIAL_SUG_LOADING_STORE not in [i["id"] for i in dep["inputs"]]
