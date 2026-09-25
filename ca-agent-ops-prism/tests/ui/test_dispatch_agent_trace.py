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

"""The Agent Trace page header, driven over Dash's HTTP route.

Dash registers the page as ``/evaluations/trials/none/trace``, so every sweep
above this stops at the path guard and returns seven no_updates. The header
badge is the only thing on the page that says what became of the trial, and it
is written as two separate outputs, a label and a colour.
"""

from __future__ import annotations

from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Trial
from prism.ui.ids import EvaluationIds
import pytest
from tests.ui import dash_http


def _header(dash_client, trial_id: int) -> dict[str, str]:
  """The trace page's status badge, as its label and its colour."""
  deps = dash_http.dependencies(dash_client)
  dep = dash_http.find(deps, f"{EvaluationIds.AGENT_TRACE_STATUS}.children")
  response = dash_http.fire_url(
      dash_client, dep, f"/evaluations/trials/{trial_id}/trace"
  )
  assert response.status_code == 200, response.data[:2000]
  return dash_http.body(response)["response"][EvaluationIds.AGENT_TRACE_STATUS]


@pytest.mark.parametrize(
    "status,color,label",
    [
        (RunStatus.COMPLETED, "green", "Completed"),
        (RunStatus.FAILED, "red", "Failed"),
        (RunStatus.CANCELLED, "gray", "Cancelled"),
        (RunStatus.RUNNING, "blue", "In Progress"),
        (RunStatus.PAUSED, "yellow", "Paused"),
        (RunStatus.PENDING, "gray", "Pending"),
    ],
)
def test_the_trace_header_reports_the_status_the_trial_is_in(
    dash_client, callback_errors, db_session, seeded, status, color, label
):
  """Everything except COMPLETED used to come out as a red "Failed".

  The header branched on one status and sent the other six to the else arm, so
  the page over a cancelled trial's trace said the agent had failed and the
  page over a still-running one said the same. The badge is what people read
  before they read the timeline.

  Spelled out, not read back out of run_status_display. The header calls that
  helper, so deriving the expected badge from it moves both sides together and
  the collapse would pass if it came back.
  """
  trial = (
      db_session.query(Trial)
      .filter_by(run_id=seeded.run_id)
      .order_by(Trial.id)
      .first()
  )
  trial.status = status
  db_session.commit()

  badge = _header(dash_client, trial.id)

  assert badge["children"] == label
  assert badge["color"] == color
  callback_errors.assert_none()


def test_a_cancelled_trace_is_not_drawn_as_a_failure(
    dash_client, callback_errors, db_session, seeded
):
  """The case the old header got most wrong, spelled out.

  Cancelled is a decision someone made. Reporting it in the red the page uses
  for a crash sends people looking for a bug that is not there.
  """
  trial = (
      db_session.query(Trial)
      .filter_by(run_id=seeded.run_id)
      .order_by(Trial.id)
      .first()
  )
  trial.status = RunStatus.CANCELLED
  db_session.commit()

  badge = _header(dash_client, trial.id)

  assert badge["children"] == "Cancelled"
  assert badge["color"] != "red"
  callback_errors.assert_none()
