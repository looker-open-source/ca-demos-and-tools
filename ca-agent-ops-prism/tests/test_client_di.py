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

"""Tests for FastDepends Dependency Injection in Client."""

import unittest
from unittest import mock

import fast_depends
from prism.client import agent_client
from prism.client import dependencies
from prism.client import prism_client
from prism.client import suite_client
from prism.client.run_client import RunsClient
from prism.common.schemas import agent as agent_schemas
from prism.server.services.agent_service import AgentService
import pydantic


class TestClientDI(unittest.TestCase):

  def test_get_client_instantiation(self):
    """Each property hands back the sub-client it is named for.

    The eight properties are copy-paste of one another, so a property handing
    back its neighbor's facade is what goes wrong. trials is the exception: it
    is the runs client under a second name, which call sites still use.
    """
    client = prism_client.PrismClient()

    self.assertIsInstance(client.agents, agent_client.AgentsClient)
    self.assertIsInstance(client.suites, suite_client.SuitesClient)
    self.assertIsInstance(client.runs, RunsClient)
    self.assertIs(client.trials, client.runs)

  def test_agent_client_list_agents_injection(self):
    """list_agents reaches its service through the provider, not a kwarg.

    Passing service= binds the parameter before FastDepends looks at it, so
    that call goes on passing with @inject and the Depends default both
    deleted. Overriding the provider is what exercises the resolution.
    """

    mock_service = mock.Mock(spec=AgentService)
    # Real Agent schemas, or the list mapping raises a Pydantic validation
    # error before the assertion is reached.
    mock_service.list_agents.return_value = [
        agent_schemas.Agent(
            id=1,
            name="Test Agent",
            config=agent_schemas.AgentConfig(
                project_id="test-project",
                location="us-central1",
                agent_resource_id="agent-123",
            ),
            created_by="user",
            created_at="2024-01-01T00:00:00",
        )
    ]

    client = agent_client.AgentsClient()

    with fast_depends.dependency_provider.scope(
        dependencies.get_agent_service, lambda: mock_service
    ):
      agents = client.list_agents()

    self.assertEqual(len(agents), 1)
    self.assertEqual(agents[0].name, "Test Agent")
    mock_service.list_agents.assert_called_once_with(include_archived=False)

  def test_pydantic_type_validation(self):
    runs = RunsClient()

    # Either error, because FastDepends wraps the pydantic one and which
    # arrives depends on where the coercion of "abc" to an int is attempted.
    with self.assertRaises(
        (pydantic.ValidationError, fast_depends.exceptions.ValidationError)
    ):
      runs.create_run(agent_id="abc", test_suite_id=1)

  def test_a_row_with_no_created_at_is_rejected(self):
    """A row the mapping cannot complete raises instead of coming back blank.

    created_at is what is missing here, not config. config carries a
    default_factory on AgentBase, so a row without one maps to an empty
    AgentConfig and never raises. The test below says so.
    """
    mock_service = mock.Mock(spec=AgentService)
    mock_service.list_agents.return_value = [{"id": 1, "name": "No Timestamp"}]

    client = agent_client.AgentsClient()

    # Raised by Agent.model_validate inside _map_agent, not by the client.
    with self.assertRaises(pydantic.ValidationError) as caught:
      client.list_agents(service=mock_service)

    self.assertEqual(
        {error["loc"] for error in caught.exception.errors()},
        {("created_at",)},
    )

  def test_a_row_with_no_config_maps_to_an_empty_one(self):
    """The mapping fills config in rather than refusing the row."""
    mock_service = mock.Mock(spec=AgentService)
    mock_service.list_agents.return_value = [
        {"id": 1, "name": "No Config", "created_at": "2024-01-01T00:00:00"}
    ]

    client = agent_client.AgentsClient()

    agents = client.list_agents(service=mock_service)

    self.assertEqual(len(agents), 1)
    self.assertIsNone(agents[0].config.project_id)
    self.assertIsNone(agents[0].config.agent_resource_id)


if __name__ == "__main__":
  unittest.main()
