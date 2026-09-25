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

"""Tests for PlaygroundService, the Question Playground's run-and-store path.

The playground runs one stored example against one agent and saves the trace.
That saved row is the only record of the attempt: the question page renders the
verdict from it, and the suggestion pass reads its trace to propose assertions.
A field dropped on the way in shows the user a blank result panel, or a green
verdict, for a simulation that did not do what they watched it do.

PlaygroundService builds its own clients and its own ExecutionService inside
execute_and_save, so these tests stub those three at the module and let the
repositories and the database be real.
"""

from unittest import mock

from prism.common.schemas.assertion import TextContains
from prism.common.schemas.execution import AssertionResult
from prism.common.schemas.execution import EphemeralTestResult
from prism.server.models.agent import Agent
from prism.server.models.playground import PlaygroundTrace
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.services import playground_service
from prism.server.services.playground_service import PlaygroundService
import pytest
from sqlalchemy.orm import Session


@pytest.fixture(name="agent")
def _agent(db_session: Session) -> Agent:
  agent = Agent(
      name="Playground Agent",
      project_id="test-project",
      location="us-central1",
      agent_resource_id="agent-playground",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.commit()
  return agent


@pytest.fixture(name="example_id")
def _example_id(db_session: Session) -> int:
  """An example with one assertion on it."""
  suite = SuiteRepository(db_session).create(name="Playground Suite")
  example_repo = ExampleRepository(db_session)
  example = example_repo.create(suite.id, "How many orders shipped?")
  example_repo.add_assertion(example.id, TextContains(value="orders"))
  db_session.commit()
  return example.id


def _result(**overrides) -> EphemeralTestResult:
  """What ExecutionService hands back, with the fields a test cares about."""
  fields = {
      "passed": True,
      "score": 1.0,
      "duration_ms": 1234,
      "assertion_results": [],
      "response_text": "412 orders shipped.",
      "generated_sql": "SELECT COUNT(*) FROM orders",
      "trace": [{"type": "model_output"}],
      "error_message": None,
  }
  fields.update(overrides)
  return EphemeralTestResult(**fields)


@pytest.fixture(name="stubbed_execution")
def _stubbed_execution():
  """Stubs everything execute_and_save reaches outside the database.

  Yields the ExecutionService instance mock, so a test can set the result and
  read back the call. GeminiDataAnalyticsClient is yielded too, since the
  project string it is built with is what routes the request.
  """
  with (
      mock.patch.object(
          playground_service.gemini_data_analytics_client,
          "GeminiDataAnalyticsClient",
      ) as gda_class,
      mock.patch.object(playground_service.gen_ai_client, "GenAIClient"),
      mock.patch.object(
          playground_service.execution_service, "ExecutionService"
      ) as exec_class,
  ):
    exec_class.return_value.execute_ephemeral_test.return_value = _result()
    yield exec_class.return_value, gda_class


def test_a_simulation_is_saved_with_every_field_the_result_page_shows(
    db_session: Session, agent: Agent, example_id: int, stubbed_execution
):
  executor, _ = stubbed_execution
  executor.execute_ephemeral_test.return_value = _result(
      passed=False,
      score=0.25,
      duration_ms=987,
      response_text="I could not find an orders table.",
      trace=[{"type": "user_input"}, {"type": "model_output"}],
      assertion_results=[
          AssertionResult(
              assertion=TextContains(value="orders"),
              passed=False,
              score=0.0,
              reasoning="Not found.",
          )
      ],
  )
  service = PlaygroundService(db_session)

  trace = service.execute_and_save(agent.id, example_id)

  db_session.expire_all()
  stored = db_session.get(PlaygroundTrace, trace.id)
  assert stored is not None, "The trace has to survive the session that made it"
  assert stored.agent_id == agent.id
  assert stored.question == "How many orders shipped?"
  assert stored.passed is False
  assert stored.score == 0.25
  assert stored.duration_ms == 987
  assert stored.output_text == "I could not find an orders table."
  assert len(stored.trace_results) == 2
  assert [r["reasoning"] for r in stored.assertion_results] == ["Not found."]


def test_the_example_supplies_the_question_and_its_assertions(
    db_session: Session, agent: Agent, example_id: int, stubbed_execution
):
  """The caller passes ids, so the service is what turns them into a test."""
  executor, _ = stubbed_execution

  PlaygroundService(db_session).execute_and_save(agent.id, example_id)

  kwargs = executor.execute_ephemeral_test.call_args.kwargs
  assert kwargs["agent_id"] == agent.id
  assert kwargs["question"] == "How many orders shipped?"
  # Schemas, not ORM rows: assert_engine reads .value off these.
  assert [a.value for a in kwargs["assertions"]] == ["orders"]


def test_an_example_with_no_assertions_still_runs(
    db_session: Session, agent: Agent, stubbed_execution
):
  """The playground is also used just to see what an agent says."""
  suite = SuiteRepository(db_session).create(name="Bare Suite")
  example = ExampleRepository(db_session).create(suite.id, "Say something.")
  db_session.commit()
  executor, _ = stubbed_execution

  trace = PlaygroundService(db_session).execute_and_save(agent.id, example.id)

  assert executor.execute_ephemeral_test.call_args.kwargs["assertions"] == []
  assert trace.assertion_results == []


def test_the_request_goes_to_the_agents_own_project_and_location(
    db_session: Session, example_id: int, stubbed_execution
):
  """An agent in europe-west1 must not be asked through us-central1.

  The endpoint is derived from this string, and a mismatch is a permission
  error from the wrong region rather than anything about the agent.
  """
  agent = Agent(
      name="Europe Agent",
      project_id="eu-project",
      location="europe-west1",
      agent_resource_id="agent-eu",
      datasource_config={"type": "bigquery"},
  )
  db_session.add(agent)
  db_session.commit()
  _, gda_class = stubbed_execution

  PlaygroundService(db_session).execute_and_save(agent.id, example_id)

  assert gda_class.call_args.kwargs["project"] == (
      "projects/eu-project/locations/europe-west1"
  )


def test_the_client_is_closed_when_the_simulation_is_over(
    db_session: Session, agent: Agent, example_id: int, stubbed_execution
):
  """One gRPC channel and its thread pool per simulation, and none released.

  The playground runs inside the same gunicorn worker as the pages, and that
  worker lives as long as the container, so the channels piled up until Cloud
  Run killed it.
  """
  _, gda_class = stubbed_execution

  PlaygroundService(db_session).execute_and_save(agent.id, example_id)

  # __exit__, because the class is a mock here. close() is what it calls, and
  # tests/clients/test_gda_transport_lifecycle.py holds that half.
  gda_class.return_value.__exit__.assert_called_once()


def test_the_client_is_closed_when_the_simulation_raises(
    db_session: Session, agent: Agent, example_id: int, stubbed_execution
):
  """A failed run is the case that leaks, since nothing unwinds after it."""
  executor, gda_class = stubbed_execution
  executor.execute_ephemeral_test.side_effect = RuntimeError("503 unavailable")

  with pytest.raises(RuntimeError):
    PlaygroundService(db_session).execute_and_save(agent.id, example_id)

  gda_class.return_value.__exit__.assert_called_once()


def test_an_unknown_agent_is_refused_before_anything_is_asked(
    db_session: Session, example_id: int, stubbed_execution
):
  executor, _ = stubbed_execution

  with pytest.raises(ValueError, match="Agent 999999 not found"):
    PlaygroundService(db_session).execute_and_save(999999, example_id)

  assert not executor.execute_ephemeral_test.called


def test_an_unknown_example_is_refused_before_anything_is_asked(
    db_session: Session, agent: Agent, stubbed_execution
):
  """The picker can hold an example another tab has since archived away."""
  executor, _ = stubbed_execution

  with pytest.raises(ValueError, match="Example 999999 not found"):
    PlaygroundService(db_session).execute_and_save(agent.id, 999999)

  assert not executor.execute_ephemeral_test.called


def test_a_run_that_errored_is_saved_with_the_error(
    db_session: Session, agent: Agent, example_id: int, stubbed_execution
):
  """A failed simulation is a result, not a lost one.

  The error text is the only thing the playground can show the user, and it
  only reaches the page through this row.
  """
  executor, _ = stubbed_execution
  executor.execute_ephemeral_test.return_value = _result(
      passed=False,
      score=None,
      response_text="",
      trace=[],
      error_message="403 The caller does not have permission",
  )

  trace = PlaygroundService(db_session).execute_and_save(agent.id, example_id)

  stored = db_session.get(PlaygroundTrace, trace.id)
  assert stored.error_message == "403 The caller does not have permission"
  assert stored.passed is False
  assert stored.score is None
