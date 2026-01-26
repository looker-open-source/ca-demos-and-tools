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

"""Service for managing Playground execution and traces."""

from prism.server.clients import gemini_data_analytics_client
from prism.server.clients import gen_ai_client
from prism.server.config import settings
from prism.server.models import playground
from prism.server.repositories import agent_repository
from prism.server.repositories import example_repository
from prism.server.repositories import playground_repository
from prism.server.repositories import suite_repository
from prism.server.repositories import trial_repository
from prism.server.services import assertion_mappers
from prism.server.services import execution_service
from prism.server.services import snapshot_service
from prism.server.services import suggestion_service
from sqlalchemy.orm import Session


class PlaygroundService:
  """Service for managing Playground execution and traces."""

  def __init__(self, session: Session):
    self._session = session
    self._playground_repo = playground_repository.PlaygroundRepository(session)
    self._agent_repo = agent_repository.AgentRepository(session)
    # Dependencies for ExecutionService
    self._suite_repo = suite_repository.SuiteRepository(session)
    self._example_repo = example_repository.ExampleRepository(session)

  def execute_and_save(
      self, agent_id: int, example_id: int
  ) -> playground.PlaygroundTrace:
    """Executes a question from an example and saves the trace."""
    # 1. Fetch Agent and Example
    agent = self._agent_repo.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent {agent_id} not found")

    example = self._example_repo.get_by_id(example_id)
    if not example:
      raise ValueError(f"Example {example_id} not found")

    # 2. Prepare assertions and question
    question = example.question
    # Convert DB models to schemas for ExecutionService

    assertions = [
        assertion_mappers.model_to_schema(a) for a in example.asserts or []
    ]

    # 3. Initialize Client
    client = gemini_data_analytics_client.GeminiDataAnalyticsClient(
        project=f"projects/{agent.project_id}/locations/{agent.location}",
        env=(
            gemini_data_analytics_client.ClientEnv(agent.env)
            if agent.env
            else gemini_data_analytics_client.ClientEnv.STAGING
        ),
    )

    # 4. Initialize Services
    snap_service = snapshot_service.SnapshotService(
        self._session, self._suite_repo, self._example_repo
    )
    gen_ai_client_inst = gen_ai_client.GenAIClient(
        project=settings.gcp_vertex_project,
        location=settings.gcp_vertex_location,
    )
    sug_service = suggestion_service.SuggestionService(
        gen_ai_client_inst,
        trial_repository.TrialRepository(self._session),
        self._example_repo,
    )
    exec_service = execution_service.ExecutionService(
        self._session,
        snap_service,
        client,
        suggestion_service=sug_service,
    )

    # 5. Execute ephemeral test
    # Ephemeral test expects list[Assertion] (schemas)
    result = exec_service.execute_ephemeral_test(
        agent_id=agent_id, question=question, assertions=assertions
    )

    # 6. Create Trace Record
    trace = playground.PlaygroundTrace(
        agent_id=agent_id,
        question=question,
        trace_results=result.trace,  # Store full trace JSON
        score=result.score,
        passed=result.passed,
        duration_ms=result.duration_ms,
        assertion_results=[r.model_dump() for r in result.assertion_results],
        output_text=result.response_text,
        error_message=result.error_message,
    )

    return self._playground_repo.save_trace(trace)

  def get_trace(self, trace_id: int) -> playground.PlaygroundTrace | None:
    """Gets a trace by ID."""
    return self._playground_repo.get_trace(trace_id)
