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

"""A callback that fails must not render the exception into the page.

``handle_errors`` gets this right: ``_notify_failure`` raises a fixed toast and
keeps the exception in the log, because "a SQLAlchemy error carries the
statement and its bound parameters".

Callbacks that catch their own exception bypass that. Four of them built the
alert with an f-string around the exception, which put a GDA resource name and
the request being sent, or a SQL statement and its bound parameters, on the
page. These tests are about that text, so they assert on it directly.

One of the four was found by a browser spec that loaded an agent detail page
with no cassette recorded. The alert rendered the cassette path and the full
request JSON. The other three were the same shape and are pinned here rather
than one browser spec each: none of this needs a browser, since the alert text
is in the callback's return value.

Four more do it through a notification instead of an alert. Same exception,
same page, different widget. Two are covered here and the two archive toggles
in ``test_archive_notifications``, which already had the mocks for them.

Not covered, on purpose: the Looker and BigQuery check buttons. Reporting why
the connection failed is what those buttons are for. So is telling someone
their golden-query JSON will not parse.
"""

from __future__ import annotations

from unittest import mock

import dash
from prism.ui.callbacks import agent_add_callbacks
from prism.ui.callbacks import agent_detail_callbacks
from prism.ui.callbacks import agent_monitor_callbacks
from prism.ui.callbacks import evaluation_callbacks
from prism.ui.callbacks import test_suite_questions_callbacks
import pytest

# Stands in for whatever the client raised. Each assertion looks for these two
# strings, which is what a resource name and a bound parameter look like.
_SECRET_DETAIL = "projects/p/locations/global/dataAgents/a"
_BOUND_PARAMS = "WHERE trial.id = %(id_1)s"


def _boom(*unused_args, **unused_kwargs):
  raise RuntimeError(f"{_SECRET_DETAIL} {_BOUND_PARAMS}")


def _client_raising_from(attribute: str):
  """A ``get_client()`` whose ``attribute`` call raises."""
  client = mock.MagicMock()
  target = client
  for part in attribute.split("."):
    target = getattr(target, part)
  target.side_effect = _boom
  return client


@pytest.mark.parametrize(
    "module,attribute,call",
    [
        (
            agent_detail_callbacks,
            "agents.get_gcp_agent_details",
            lambda: agent_detail_callbacks.fetch_remote_config({"agent_id": 7}),
        ),
        (
            evaluation_callbacks,
            "runs.get_trial",
            lambda: evaluation_callbacks.render_trial_detail(
                "/evaluations/trials/7", False
            ),
        ),
    ],
)
def test_a_failed_load_does_not_render_the_exception(module, attribute, call):
  with mock.patch.object(
      module, "get_client", return_value=_client_raising_from(attribute)
  ):
    rendered = str(call())

  assert _SECRET_DETAIL not in rendered, rendered[:2000]
  assert _BOUND_PARAMS not in rendered, rendered[:2000]
  # The user still has to be told something failed.
  assert "Could not" in rendered, rendered[:2000]


def test_a_failed_discovery_does_not_render_the_exception():
  client = mock.MagicMock()
  client.agents.discover_gcp_agents.side_effect = _boom
  with mock.patch.object(
      agent_monitor_callbacks, "get_client", return_value=client
  ):
    rendered = str(agent_monitor_callbacks.perform_discovery(True, "a-project"))

  assert _SECRET_DETAIL not in rendered, rendered[:2000]
  assert "Could not" in rendered, rendered[:2000]


def test_a_failed_test_case_render_does_not_render_the_exception():
  """The only one of the four raising from a render, not from a client."""
  # TestCaseState(**q) is what raises: the dict is not a test case.
  rendered = str(
      test_suite_questions_callbacks.render_test_case_sidebar(
          [{"not": _SECRET_DETAIL}], 0
      )
  )

  assert _SECRET_DETAIL not in rendered, rendered[:2000]
  assert "Could not" in rendered, rendered[:2000]


@pytest.mark.parametrize(
    "module,attribute,call",
    [
        (
            agent_add_callbacks,
            "agents.register_gcp_agent",
            lambda: agent_add_callbacks.add_agent(
                1, "A", "p", "", "bq", "p.d.t", None, None, None, None
            ),
        ),
        (
            agent_detail_callbacks,
            "agents.update_agent",
            lambda: agent_detail_callbacks.submit_edit(
                1, "/agents/view/7", "A", "", None, None, None, None, None, None
            ),
        ),
    ],
)
def test_a_failed_write_does_not_notify_with_the_exception(
    module, attribute, call
):
  """Same defect through a toast instead of an alert."""
  with mock.patch.object(
      module, "get_client", return_value=_client_raising_from(attribute)
  ):
    rendered = str(call())

  assert _SECRET_DETAIL not in rendered, rendered[:2000]
  assert _BOUND_PARAMS not in rendered, rendered[:2000]
  assert "Could not" in rendered, rendered[:2000]


def test_the_agent_detail_alert_still_names_the_agent_config():
  """A fixed message still has to say which thing failed.

  Eight callbacks now share the same shape, so the replacement text is the
  only thing telling them apart on screen.
  """
  client = _client_raising_from("agents.get_gcp_agent_details")
  with mock.patch.object(
      agent_detail_callbacks, "get_client", return_value=client
  ):
    rendered = str(agent_detail_callbacks.fetch_remote_config({"agent_id": 7}))

  assert "configuration" in rendered
  assert "server log" in rendered


def test_a_failed_fetch_leaves_edit_disabled_and_duplicate_usable():
  """The failure branch has to return both flags, and not the same one.

  Dropping them locks the page into a loading state with no way out. Enabling
  Edit is worse: the config Store stays where it was, so the instruction
  textarea opens blank and saving publishes that blank over the live agent.
  Duplicate re-reads GCP when it submits, so it has nothing to overwrite.
  """
  client = _client_raising_from("agents.get_gcp_agent_details")
  with mock.patch.object(
      agent_detail_callbacks, "get_client", return_value=client
  ):
    result = agent_detail_callbacks.fetch_remote_config({"agent_id": 7})

  # Indices 4 and 5 are the edit and duplicate button disabled flags.
  assert result[4] is True
  assert result[5] is False


@pytest.mark.parametrize(
    "get_trial,expected",
    [
        (_boom, "server log"),
        (lambda *unused: None, "Trial not found"),
    ],
)
def test_a_failed_trial_load_alerts_where_the_page_shows_it(
    get_trial, expected
):
  """Both error returns put the alert in the detail container, not first.

  The outputs are declared breadcrumbs, title, description, actions,
  container. Both returns used to lead with the alert, so it rendered into the
  breadcrumb bar and the container kept the ``dmc.Loader`` the layout left
  there. The page read as still loading with an error above it.
  """
  client = mock.MagicMock()
  client.runs.get_trial.side_effect = get_trial
  with mock.patch.object(
      evaluation_callbacks, "get_client", return_value=client
  ):
    result = evaluation_callbacks.render_trial_detail(
        "/evaluations/trials/7", ""
    )

  assert expected in str(result[4]), result[4]
  # The breadcrumb bar keeps whatever it had. Writing the alert here is the
  # bug, and str() of a no_update is not empty, so check the type.
  assert isinstance(result[0], type(dash.no_update)), result[0]
