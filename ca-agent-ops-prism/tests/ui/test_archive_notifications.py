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

"""Tests that the archive callbacks send a notification the UI can render.

Both write to NotificationContainer's ``sendNotifications``, which takes a
list of actions. They used to pass a bare dict, which the component drops
silently, so neither the success toast nor the error one ever appeared.

The two failure tests also check the message is not the exception text.
``test_error_alerts`` says why.
"""

from __future__ import annotations

from typing import Any
from unittest import mock

import dash
from prism.ui.callbacks.agent_detail_callbacks import toggle_agent_archive
from prism.ui.callbacks.evaluation_callbacks import toggle_run_archive
from prism.ui.ids import EvaluationIds
from prism.ui.pages.agent_ids import AgentIds
import pytest

# What a SQLAlchemy error puts in str(e), standing in for the real thing.
_BOUND_PARAMS = "UPDATE agent SET is_archived WHERE id = %(id_1)s"


def _assert_is_notification_list(value: Any, title: str) -> None:
  """Asserts ``value`` is a list of actions NotificationContainer renders."""
  assert isinstance(value, list), f"expected a list of actions, got {value!r}"
  assert len(value) == 1
  assert value[0]["action"] == "show"
  assert value[0]["title"] == title


@pytest.fixture(name="agent_client")
def _agent_client():
  """Patches the client the agent detail callbacks reach for."""
  with mock.patch(
      "prism.ui.callbacks.agent_detail_callbacks.get_client"
  ) as factory:
    yield factory.return_value.agents


@pytest.fixture(name="run_client")
def _run_client():
  """Patches the client the evaluation callbacks reach for."""
  with mock.patch(
      "prism.ui.callbacks.evaluation_callbacks.get_client"
  ) as factory:
    yield factory.return_value.runs


def _agent_context(triggered_id: str):
  """A callback context naming the button that fired."""
  context = mock.Mock()
  context.triggered = [{"prop_id": f"{triggered_id}.n_clicks"}]
  return mock.patch.object(dash, "callback_context", context)


def test_agent_archive_success(agent_client):
  """The agent id comes off the pathname, and the toast is a list."""
  with _agent_context(AgentIds.Detail.BTN_ARCHIVE):
    _, notifications = toggle_agent_archive(1, None, "/agents/7")

  agent_client.archive_agent.assert_called_once_with(7)
  _assert_is_notification_list(notifications, "Success")


def test_agent_archive_failure(agent_client):
  """A raise still reaches the user, and without the statement in it."""
  agent_client.archive_agent.side_effect = RuntimeError(_BOUND_PARAMS)

  with _agent_context(AgentIds.Detail.BTN_ARCHIVE):
    _, notifications = toggle_agent_archive(1, None, "/agents/7")

  _assert_is_notification_list(notifications, "Error")
  assert _BOUND_PARAMS not in notifications[0]["message"]


def test_run_archive_success(run_client):
  """The run id comes off the pathname, and the page must stay put."""
  with mock.patch.object(dash, "ctx") as ctx:
    ctx.triggered_id = EvaluationIds.BTN_ARCHIVE
    href, _, notifications = toggle_run_archive(1, None, "/evaluations/run/9")

  run_client.archive_run.assert_called_once_with(9)
  _assert_is_notification_list(notifications, "Success")
  # redirect-handler is refresh=True, so returning the current pathname
  # reloaded the page and threw the notification away with it.
  assert href is dash.no_update


def test_run_archive_failure(run_client):
  """A raise still reaches the user, and without the parameters in it."""
  run_client.archive_run.side_effect = RuntimeError(_BOUND_PARAMS)

  with mock.patch.object(dash, "ctx") as ctx:
    ctx.triggered_id = EvaluationIds.BTN_ARCHIVE
    _, _, notifications = toggle_run_archive(1, None, "/evaluations/run/9")

  _assert_is_notification_list(notifications, "Error")
  assert _BOUND_PARAMS not in notifications[0]["message"]
