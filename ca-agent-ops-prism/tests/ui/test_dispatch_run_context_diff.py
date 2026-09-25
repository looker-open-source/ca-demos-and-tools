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

"""Dispatch tests for the agent context snapshot and its live diff.

The run detail page keeps a snapshot of the agent's context as it was when the
run started, and offers to diff it against what the agent is published with
now. The live half is a GDA call, which means it can fail, and the e2e specs
install a working cassette for it every time.
"""

from __future__ import annotations

import datetime
import json
from typing import Any

from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.ids import EvaluationIds
from prism.ui.models.ui_state import RunDetailPageState
import pytest
from tests.ui import dash_http

# Importing the app registers every page and every callback.
from prism.ui.app import app  # pylint: disable=unused-import

_SNAPSHOT = {"system_instruction": "Answer questions about orders."}


def _run_data(
    run_id: int = 99, snapshot: dict[str, Any] | None = None
) -> dict[str, Any]:
  """The RUN_DATA_STORE payload for one run with no trials."""
  run = RunSchema(
      id=run_id,
      test_suite_snapshot_id=1,
      agent_id=7,
      status=RunStatus.COMPLETED,
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      agent_context_snapshot=snapshot,
  )
  return RunDetailPageState(run=run, trials=[]).model_dump(mode="json")


def _run_detail_dep(dash_client):
  """The ``render_run_detail_components`` entry."""
  deps = dash_http.dependencies(dash_client)
  return dash_http.find(deps, f"{EvaluationIds.RUN_CHARTS_CONTAINER}.children")


def _live_fetch_dep(dash_client):
  """The ``fetch_live_config_for_diff`` entry.

  Three callbacks write the diff store and two write the content, so this is
  picked out by being the only one whose input is the store itself.
  """
  deps = dash_http.dependencies(dash_client)
  matches = [
      dep
      for dep in deps
      if [i["id"] for i in dep["inputs"]]
      == [EvaluationIds.RUN_CONTEXT_DIFF_STORE]
      and EvaluationIds.RUN_CONTEXT_DIFF_CONTENT in dep["output"]
  ]
  assert len(matches) == 1, f"expected one live-fetch callback, got {matches}"
  return matches[0]


def test_a_run_without_a_snapshot_offers_nothing_to_compare(
    dash_client, callback_errors
):
  """A run from before snapshots exist has nothing to diff against live.

  ``render_run_context`` returns early for a null snapshot and the Compare
  button only exists in the other branch. Rendering the button anyway leaves
  a click that opens a modal diffing an empty dict, which reads as the agent
  having lost its whole context.
  """
  dep = _run_detail_dep(dash_client)

  without = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data()},
      )
  )["response"]
  charts = json.dumps(without[EvaluationIds.RUN_CHARTS_CONTAINER]["children"])
  assert "No context snapshot available." in charts
  assert EvaluationIds.RUN_CONTEXT_DIFF_BTN not in charts

  # The other direction, because a card that never renders the button would
  # pass the assertion above.
  with_snapshot = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {
              f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data(
                  snapshot=_SNAPSHOT
              )
          },
      )
  )["response"]
  charts = json.dumps(
      with_snapshot[EvaluationIds.RUN_CHARTS_CONTAINER]["children"]
  )
  assert EvaluationIds.RUN_CONTEXT_DIFF_BTN in charts
  assert "Answer questions about orders." in charts

  callback_errors.assert_none()


def test_the_poll_does_not_reseed_the_context_trigger(
    dash_client, callback_errors
):
  """Re-rendering the same run must leave the diff store alone.

  The run detail page polls every three seconds while a run is unfinished, and
  every tick re-runs this callback. Writing the trigger each time restarts
  ``fetch_run_context``, which resets ``live`` to None, so a diff the user
  already fetched is thrown away underneath them.
  """
  dep = _run_detail_dep(dash_client)
  run_data = _run_data(run_id=99)

  first = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {f"{EvaluationIds.RUN_DATA_STORE}.data": run_data},
      )
  )["response"]
  assert first[EvaluationIds.RUN_CONTEXT_TRIGGER]["data"] == 99

  again = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {
              f"{EvaluationIds.RUN_DATA_STORE}.data": run_data,
              f"{EvaluationIds.RUN_CONTEXT_TRIGGER}.data": 99,
          },
      )
  )["response"]
  # no_update writes nothing, so the key is absent while the rest are there.
  assert EvaluationIds.RUN_CONTEXT_TRIGGER not in again
  assert EvaluationIds.RUN_CHARTS_CONTAINER in again

  # Navigating to another run still seeds it, or the diff would stay on the
  # run the tab opened with.
  moved = dash_http.body(
      dash_http.fire(
          dash_client,
          dep,
          {
              f"{EvaluationIds.RUN_DATA_STORE}.data": _run_data(run_id=100),
              f"{EvaluationIds.RUN_CONTEXT_TRIGGER}.data": 99,
          },
      )
  )["response"]
  assert moved[EvaluationIds.RUN_CONTEXT_TRIGGER]["data"] == 100

  callback_errors.assert_none()


class _FailingContext:
  """A client whose published-context lookup does not answer."""

  def __init__(self, error: Exception | None):
    self.error = error

  def get_published_context(self, agent_id):
    del agent_id
    if self.error:
      raise self.error
    return None


@pytest.mark.parametrize(
    "error",
    [RuntimeError("seeded failure"), None],
    ids=["raises", "returns_none"],
)
def test_a_failed_live_fetch_does_not_claim_the_agent_is_unchanged(
    dash_client, monkeypatch, error
):
  """The badge may only say unchanged when the live context came back.

  Both ways the lookup can come back empty land in the same fallback, which
  sets live to the snapshot. The user is then told the published context is
  unchanged on the strength of a call that never returned it. The two cases
  are a raised exception and the None ``get_published_context`` returns when
  the agent row is gone.
  """

  class _Client:
    agents = _FailingContext(error)

  monkeypatch.setattr(evaluation_callbacks, "get_client", _Client)

  dep = _live_fetch_dep(dash_client)
  response = dash_http.fire(
      dash_client,
      dep,
      {
          f"{EvaluationIds.RUN_CONTEXT_DIFF_STORE}.data": {
              "snapshot": _SNAPSHOT,
              "live": None,
              "agent_id": 7,
              "is_fetching": True,
          }
      },
  )

  assert response.status_code == 200, response.data[:2000]
  body = dash_http.body(response)["response"]
  title = json.dumps(body[EvaluationIds.RUN_CONTEXT_DIFF_TITLE]["children"])
  assert "No changes detected" not in title, title
  assert "Changes detected" not in title, title

  content = json.dumps(body[EvaluationIds.RUN_CONTEXT_DIFF_CONTENT]["children"])
  assert "Live context unavailable" in content, content

  # live stays unset, so the next click refetches instead of showing the
  # snapshot back to the user as if it were live.
  assert body[EvaluationIds.RUN_CONTEXT_DIFF_STORE]["data"]["live"] is None
  assert (
      body[EvaluationIds.RUN_CONTEXT_DIFF_STORE]["data"]["is_fetching"] is False
  )
