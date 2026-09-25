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

"""The Looker client secret must not be sent back to the browser.

``open_edit_modal`` pre-fills the Edit Agent form from the stored config, and
the secret field used to be pre-filled too. dmc renders it as a
``PasswordInput``, which masks the characters on screen but does nothing to
the value: it arrives in the callback response as plaintext and sits in the
DOM, readable in devtools, every time the modal is opened.

Leaving it out makes blank the normal state of the field, so the two callbacks
that read it have to agree that blank means "keep the stored secret" and not
"clear it". Getting that wrong silently locks the agent out of Looker on the
next unrelated edit, so the rest of these tests pin it down.

``fetch_remote_config`` is the other way out. It dumps the whole AgentConfig
into a ``dcc.Store`` on every detail page load, and
``get_gcp_agent_details`` back-fills the stored secret onto that config so the
Run Eval button can tell whether credentials exist. The back-fill has to stay
and the dump has to drop the secret.
"""

from __future__ import annotations

import datetime
from typing import Any
from unittest import mock

from prism.common.schemas import agent as agent_schemas
from prism.ui.callbacks import agent_detail_callbacks
import pytest

_STORED_SECRET = "stored-looker-secret"

# Indices into open_edit_modal's output tuple, ordered to match its ``Output``
# list.
_CLIENT_ID_VALUE = 6
_SECRET_VALUE = 7

# submit_edit returns (modal_opened, loading, href, notifications, refresh).
_NOTIFICATIONS = 3

# Indices into fetch_remote_config's output tuple.
_GCP_CONFIG_STORE = 3
_RUN_EVAL_DISABLED = 6


def _looker_agent(secret: str | None = _STORED_SECRET) -> agent_schemas.Agent:
  """A registered Looker agent, with or without a stored secret."""
  return agent_schemas.Agent(
      id=7,
      name="Looker Agent",
      created_at=datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc),
      config=agent_schemas.AgentConfig(
          project_id="a-project",
          location="us-central1",
          agent_resource_id="agent-7",
          system_instruction="an instruction",
          datasource=agent_schemas.LookerConfig(
              instance_uri="https://looker.example.com",
              explores=["model.explore"],
          ),
          looker_client_id="a-client-id",
          looker_client_secret=secret,
      ),
  )


@pytest.fixture(name="agents_client")
def _agents_client():
  """Stands in for ``get_client().agents``, holding one Looker agent."""
  client = mock.MagicMock()
  client.agents.get_agent.return_value = _looker_agent()
  with mock.patch.object(
      agent_detail_callbacks, "get_client", return_value=client
  ):
    yield client.agents


def _submit(agents_client, secret: Any) -> tuple[Any, ...]:
  """Submits the edit form with everything unchanged except the secret."""
  return agent_detail_callbacks.submit_edit(
      1,  # n_clicks
      "/agents/view/7",
      "Looker Agent",
      "an instruction",
      "https://looker.example.com",
      "model.explore",
      "a-client-id",
      secret,
      "",  # bq_tables_raw
      "",  # golden_queries_raw
  )


def test_opening_the_edit_modal_does_not_send_the_stored_secret(agents_client):
  result = agent_detail_callbacks.open_edit_modal(
      1, {"system_instruction": "an instruction"}, "/agents/view/7"
  )

  assert _STORED_SECRET not in str(result), (
      "The stored Looker secret reached the browser. PasswordInput hides it"
      " from the user, not from the page."
  )
  assert result[_SECRET_VALUE] == ""
  # The client id isn't a credential, so it stays pre-filled. Without it a
  # blank secret would look the same as a half-filled form.
  assert result[_CLIENT_ID_VALUE] == "a-client-id"


def test_submitting_a_blank_secret_leaves_the_stored_one_alone(agents_client):
  """Blank means unchanged, and unchanged means ``None``.

  This is the callback's half: the config it hands the client carries None, not
  ``""``, which would wipe the stored secret. The client here is a MagicMock,
  so the rule on the other side (``AgentRepository.update`` writes the secret
  only when it is not None) is pinned in
  tests/repositories/test_agent_repository_secret.py.
  """
  _submit(agents_client, "")

  agents_client.update_agent.assert_called_once()
  config = agents_client.update_agent.call_args.kwargs["config"]
  assert config.looker_client_secret is None


def test_a_typed_secret_still_replaces_the_stored_one(agents_client):
  """Rotating a credential has to keep working."""
  _submit(agents_client, "a-new-secret")

  config = agents_client.update_agent.call_args.kwargs["config"]
  assert config.looker_client_secret == "a-new-secret"


def test_a_blank_secret_is_rejected_when_nothing_is_stored(agents_client):
  """Blank is only "unchanged" when there is something to leave unchanged.

  With no secret on record, a blank field is an incomplete Looker config and
  saving it would produce an agent that can't run.
  """
  agents_client.get_agent.return_value = _looker_agent(secret=None)

  result = _submit(agents_client, "")

  assert not agents_client.update_agent.called
  assert result[_NOTIFICATIONS][0]["title"] == "Missing Looker Credentials"


def test_the_detail_page_store_does_not_carry_the_secret(agents_client):
  """The config Store is serialized into the page, so it has to be clean."""
  agents_client.get_gcp_agent_details.return_value = _looker_agent()

  result = agent_detail_callbacks.fetch_remote_config({"agent_id": 7})

  assert _STORED_SECRET not in str(result), (
      "The stored Looker secret reached the browser in the config Store,"
      " where anything on the page can read it."
  )
  stored = result[_GCP_CONFIG_STORE]
  assert "looker_client_secret" not in stored
  # The instruction is what open_edit_modal reads out of the Store. The
  # datasource goes in too, and the detail page's own renderers read it.
  assert stored["system_instruction"] == "an instruction"
  assert stored["datasource"]["instance_uri"] == "https://looker.example.com"


def test_run_eval_stays_enabled_when_only_the_stored_secret_proves_the_creds(
    agents_client,
):
  """Dropping the secret from the Store must not disarm the Run Eval button.

  GCP does not echo Looker credentials back, so ``get_gcp_agent_details``
  back-fills the stored one and the button is enabled off the back of it. The
  check runs before the dump, and this is what says so.
  """
  agents_client.get_gcp_agent_details.return_value = _looker_agent()

  result = agent_detail_callbacks.fetch_remote_config({"agent_id": 7})

  assert result[_RUN_EVAL_DISABLED] is False


def test_run_eval_is_disabled_when_no_secret_is_stored_either(agents_client):
  agents_client.get_gcp_agent_details.return_value = _looker_agent(secret=None)

  result = agent_detail_callbacks.fetch_remote_config({"agent_id": 7})

  assert result[_RUN_EVAL_DISABLED] is True
