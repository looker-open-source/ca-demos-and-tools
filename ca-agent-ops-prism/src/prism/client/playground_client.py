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

"""Playground Client implementation."""

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas.assertion import Assertion
from prism.common.schemas.trace import PlaygroundTraceSchema
from prism.common.schemas.trace import SimulationResult
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.services import assertion_mappers
from prism.server.services.playground_service import PlaygroundService
from prism.server.services.suggestion_service import SuggestionService
from prism.server.services.suite_service import SuiteService


class PlaygroundClient:
  """Playground Client implementation."""

  @inject
  def run_simulation(
      self,
      agent_id: int,
      example_id: int,
      playground_service: PlaygroundService = Depends(
          dependencies.get_playground_service
      ),
      suggestion_service: SuggestionService = Depends(
          dependencies.get_suggestion_service
      ),
      suite_service: SuiteService = Depends(dependencies.get_suite_service),
      agent_repo: AgentRepository = Depends(dependencies.get_agent_repository),
  ) -> SimulationResult:
    """Runs a full simulation using IDs, fetching data from the database."""
    # 1. Fetch Question and Assertions if example_id is provided
    example = suite_service.get_example(example_id)
    if not example:
      raise ValueError(f"Example with ID {example_id} not found.")

    # 2. Execute and Save Trace
    trace_model = playground_service.execute_and_save(
        agent_id=agent_id, example_id=example_id
    )
    trace = PlaygroundTraceSchema.model_validate(trace_model)

    # 3. Generate Suggestions
    # We need the agent's location for Vertex AI routing
    agent = agent_repo.get_by_id(agent_id)
    location = agent.location if agent else None

    suggestions = suggestion_service.suggest_assertions_from_trace(
        trace=trace.trace_results or [],
        existing_assertions=[
            assertion_mappers.model_to_schema(a) for a in example.asserts or []
        ],
        location=location,
    )

    # 4. Construct UI-ready response
    result_summary = {
        "passed": trace.passed,
        "score": trace.score,
        "duration_ms": trace.duration_ms,
        "assertion_results": [r.model_dump() for r in trace.assertion_results],
        "response_text": trace.output_text,
        "error": trace.error_message,
    }

    suggestions_ui = []
    for idx, s in enumerate(suggestions or []):
      s_dict = s.model_dump()
      s_dict["_checked"] = False
      s_dict["_backend_index"] = idx
      suggestions_ui.append(s_dict)

    return SimulationResult(
        trace=trace,
        suggestions=suggestions,
        result_summary=result_summary,
        suggestions_ui=suggestions_ui,
    )

  @inject
  def get_trace(
      self,
      trace_id: int,
      service: PlaygroundService = Depends(dependencies.get_playground_service),
  ) -> PlaygroundTraceSchema | None:
    """Gets a trace by ID."""
    model = service.get_trace(trace_id)
    if not model:
      return None
    return PlaygroundTraceSchema.model_validate(model)
