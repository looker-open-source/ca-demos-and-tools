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

"""What _map_agent does with a row it cannot read field by field.

The agent table stores the config flattened into columns, so the ORM model has
no ``config`` attribute at all. ``Agent.model_validate`` on such a row reads
name, id and the timestamps, finds no config, and fills in the
``default_factory``. That is why the fallback could never fail, and why a row
the explicit construction rejected came back looking blank instead of raising.
"""

import datetime

from prism.client import agent_client
import pydantic
import pytest

_map_agent = agent_client._map_agent  # pylint: disable=protected-access


class _AgentRow:
  """The attributes _map_agent reads off a SQLAlchemy Agent model."""

  def __init__(self, datasource_config):
    self.id = 7
    self.name = "Bot"
    self.project_id = "p"
    self.location = "us"
    self.agent_resource_id = "r"
    self.datasource_config = datasource_config
    self.looker_client_id = None
    self.looker_client_secret = None
    self.created_at = datetime.datetime(2026, 1, 1)
    self.modified_at = None
    self.is_archived = False


_GOOD_CONFIG = {
    "instance_uri": "https://looker.example.com",
    "explores": ["thelook::orders"],
    "golden_queries": [{
        "natural_language_questions": ["how many orders"],
        "looker_query": {"model": "thelook", "explore": "orders"},
    }],
}

# golden_queries as a list of strings, which AgentConfig rejects. It is read
# inside the explicit construction rather than by the LookerConfig above, so
# this is the shape of row that used to reach the fallback.
_BAD_CONFIG = dict(_GOOD_CONFIG, golden_queries=["how many orders"])


def test_a_row_that_maps_is_still_mapped():
  agent = _map_agent(_AgentRow(_GOOD_CONFIG))

  assert agent.config.project_id == "p"
  assert agent.config.agent_resource_id == "r"
  assert agent.config.golden_queries[0].looker_query.explore == "orders"


def test_a_row_that_does_not_map_raises():
  """A config that fails validation has to stop the render, not blank it.

  The agent used to come back with no project, no resource id, no datasource
  and no golden queries. Nothing on the page said so, and saving Edit wrote
  that empty config straight back over the real one.
  """
  with pytest.raises(pydantic.ValidationError):
    _map_agent(_AgentRow(_BAD_CONFIG))


def test_the_failure_names_the_row(caplog):
  """The traceback pydantic raises does not say which agent it was."""
  with caplog.at_level("ERROR"):
    with pytest.raises(pydantic.ValidationError):
      _map_agent(_AgentRow(_BAD_CONFIG))

  # The message, not caplog.text. The default caplog format carries the
  # filename and the line number, and the line the log call sits on puts a 7
  # in the text whatever the log line itself says.
  errors = [r for r in caplog.records if r.levelname == "ERROR"]
  assert len(errors) == 1, [r.getMessage() for r in caplog.records]
  assert "7" in errors[0].getMessage()
