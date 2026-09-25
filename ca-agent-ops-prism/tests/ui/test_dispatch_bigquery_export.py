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

"""The BigQuery export controls on the run detail page, over HTTP.

``tests/ui/test_run_detail_bigquery_badge.py`` calls
``render_run_detail_components`` directly and covers what the page is allowed
to ask BigQuery. Three things it cannot reach are here: the failed-export
badge, the Sync button's callback, and the signal that button writes to make
the page reload itself. The last two only exist as wiring, so they have to be
driven through the dispatch route to be tested at all.

``_run_data`` is a copy of the helper in that file. If a third file wants it,
it should move to ``tests/ui/conftest.py``.
"""

from __future__ import annotations
import datetime
from typing import Any
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.config import settings
from prism.server.models.run import Run
from prism.server.services import bigquery_exporter
from prism.ui.constants import NOTIFICATION_CONTAINER
from prism.ui.ids import EvaluationIds
from prism.ui.models.ui_state import RunDetailPageState
import pytest
from sqlalchemy import orm
from tests.ui import dash_http

_RUN_ID = 99


def _run_data(status: RunStatus = RunStatus.COMPLETED) -> dict[str, Any]:
  """The RUN_DATA_STORE payload for a run in the given status."""
  run = RunSchema(
      id=_RUN_ID,
      test_suite_snapshot_id=1,
      agent_id=1,
      status=status,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
  )
  return RunDetailPageState(run=run, trials=[]).model_dump(mode="json")


def _by_input(client, component_id: str) -> dict[str, Any]:
  """The one callback taking ``component_id`` as an input.

  The Sync button's callback writes RUN_UPDATE_SIGNAL.data, and so does the
  archive callback, so it cannot be found by what it writes.
  """
  matches = [
      dep
      for dep in dash_http.dependencies(client)
      if any(i["id"] == component_id for i in dep["inputs"])
  ]
  assert len(matches) == 1, f"{len(matches)} callbacks take {component_id}"
  return matches[0]


@pytest.fixture(name="export_enabled")
def _export_enabled(monkeypatch):
  """Turns the feature on, without letting anything reach BigQuery."""
  monkeypatch.setattr(settings, "bigquery_export_enabled", True)
  monkeypatch.setattr(
      bigquery_exporter.BigQueryExporter,
      "check_run_exported",
      lambda self, run_id: bigquery_exporter.EXPORT_STATE_NOT_EXPORTED,
  )


def test_the_badge_says_so_when_the_last_export_failed(
    dash_client, callback_errors, export_enabled, monkeypatch
):
  """A failed export has to be visible, and has to say what to do about it.

  The failure is only recorded in this process's memory, so nothing else will
  ever surface it. Without the badge a run that failed to export looks exactly
  like one that was never exported, and the tooltip is the only place the
  error text appears.
  """
  monkeypatch.setattr(
      bigquery_exporter,
      "get_run_export_error",
      lambda run_id: "Quota exceeded for project my-gcp-project",
  )
  dep = dash_http.find(
      dash_http.dependencies(dash_client),
      f"{EvaluationIds.RUN_BIGQUERY_BADGE}.children",
  )

  response = dash_http.fire(
      dash_client,
      dep,
      {f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data()},
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  body = dash_http.body(response)["response"]
  tooltip = body[EvaluationIds.RUN_BIGQUERY_BADGE]["children"]
  assert tooltip["props"]["label"] == (
      "Export failed: Quota exceeded for project my-gcp-project. Click 'Sync to"
      " BigQuery' to retry."
  ), "the tooltip is the only place the error text is shown"
  badge = tooltip["props"]["children"]
  assert badge["props"]["children"] == "BQ: Failed"
  assert badge["props"]["color"] == "red"
  assert body[EvaluationIds.BTN_SYNC_BIGQUERY]["style"] == {"display": "block"}


def test_the_sync_button_dispatches_the_export_and_says_it_started(
    dash_client, callback_errors, export_enabled, monkeypatch
):
  """Clicking Sync has to reach the exporter and report back twice.

  The notification is a list, because NotificationContainer ignores a bare
  dict and the toast disappears. The signal is the other half: the export runs
  on a thread, so the only way the badge beside the button catches up is the
  page refetching itself, which is what the signal is for.
  """
  dispatched = []
  monkeypatch.setattr(
      bigquery_exporter.BigQueryExporter,
      "export_run_async",
      lambda self, run_id, session_factory, force=False: dispatched.append(
          (run_id, force)
      ),
  )

  response = dash_http.fire(
      dash_client,
      _by_input(dash_client, EvaluationIds.BTN_SYNC_BIGQUERY),
      {
          f"{EvaluationIds.BTN_SYNC_BIGQUERY}.n_clicks": 1,
          f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data(),
      },
  )

  assert response.status_code == 200, response.data[:2000]
  callback_errors.assert_none()
  assert dispatched == [(_RUN_ID, True)]

  body = dash_http.body(response)["response"]
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  assert isinstance(notifications, list), "a bare dict is dropped on the floor"
  assert len(notifications) == 1
  assert notifications[0]["action"] == "show"
  assert notifications[0]["title"] == "BigQuery Sync Started"
  assert notifications[0]["color"] == "blue"
  assert f"Run #{_RUN_ID}" in notifications[0]["message"]
  assert body[EvaluationIds.RUN_UPDATE_SIGNAL]["data"]["action"] == "sync_bq"


def test_a_sync_that_cannot_start_says_so(
    dash_client, callback_errors, monkeypatch
):
  """The button is reachable with the export off, so the toast has to fire.

  This is the branch that catches everything, a missing dataset or a permission
  error as much as the disabled flag. What it catches names the project and the
  dataset, so the toast says which run failed and nothing else. Nothing is
  dispatched, but the signal is still written, so the badge is re-read either
  way.
  """
  monkeypatch.setattr(settings, "bigquery_export_enabled", False)
  response = dash_http.fire(
      dash_client,
      _by_input(dash_client, EvaluationIds.BTN_SYNC_BIGQUERY),
      {
          f"{EvaluationIds.BTN_SYNC_BIGQUERY}.n_clicks": 1,
          f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data(),
      },
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)["response"]
  notifications = body[NOTIFICATION_CONTAINER]["sendNotifications"]
  assert notifications == [{
      # NotificationContainer dispatches on this. Without it the entry matches
      # nothing and the toast never appears, which is what this test used to
      # pin.
      "action": "show",
      "title": "BigQuery Sync Failed",
      "message": (
          f"Could not export Run #{_RUN_ID}. The details are in the server log."
      ),
      "color": "red",
  }]
  assert body[EvaluationIds.RUN_UPDATE_SIGNAL]["data"]["action"] == "sync_bq"

  # The callback logs the exception before answering, so the gate has one.
  assert callback_errors.messages
  callback_errors.clear()


def test_the_update_signal_makes_the_detail_page_read_the_run_again(
    dash_client, callback_errors, db_session: orm.Session, seeded
):
  """Whatever writes the signal gets a fresh page, with no poll to wait for.

  Sync and archive both change a run and then write the signal. Polling stops
  once a run is finished, so if the signal were State instead of Input the
  page would sit on the old data until it was reloaded by hand. This fires the
  fetch with only the signal changed, which is the case that would break.
  """
  dep = dash_http.find(
      dash_http.dependencies(dash_client),
      f"{EvaluationIds.RUN_DATA_STORE}.data",
  )
  signal = f"{EvaluationIds.RUN_UPDATE_SIGNAL}.data"
  assert signal in [
      dash_http.address(i) for i in dep["inputs"]
  ], "the signal is not an input, so writing it refetches nothing"

  def fetch(stamp: float) -> dict[str, Any]:
    response = dash_http.fire(
        dash_client,
        dep,
        {
            "url.pathname": f"/evaluations/runs/{seeded.run_id}",
            f"{EvaluationIds.RUN_POLLING_INTERVAL}.n_intervals": 0,
            signal: {"timestamp": stamp, "action": "sync_bq"},
        },
        changed=[signal],
    )
    assert response.status_code == 200, response.data[:2000]
    return dash_http.body(response)["response"][EvaluationIds.RUN_DATA_STORE][
        "data"
    ]

  before = fetch(1.0)
  assert before["run"]["id"] == seeded.run_id
  assert len(before["trials"]) == 3

  run = db_session.get(Run, seeded.run_id)
  run.status = RunStatus.CANCELLED
  db_session.commit()

  after = fetch(2.0)
  callback_errors.assert_none()
  assert after["run"]["status"] == RunStatus.CANCELLED.value
