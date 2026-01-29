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

"""Service for executing tests (Runs)."""

import datetime
import logging
import traceback  # pylint: disable=unused-import
from typing import Any

from google.protobuf import json_format
from sqlalchemy import orm

from prism.common.schemas.assertion import Assertion
from prism.common.schemas.execution import EphemeralTestResult
from prism.common.schemas.trace import AskQuestionResponse
from prism.common.schemas.trace import DurationMetrics
from prism.server.clients.gemini_data_analytics_client import GeminiDataAnalyticsClient
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.config import settings
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
from prism.server.models.example import Example
from prism.server.models.run import Run
from prism.server.models.run import RunStatus
from prism.server.models.run import Trial
from prism.server.repositories.agent_repository import AgentRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.suite_repository import SuiteRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services import assert_engine
from prism.server.services import assertion_mappers
from prism.server.services.snapshot_service import SnapshotService


class ExecutionService:
  """Service for managing test executions."""

  def __init__(
      self,
      session: orm.Session,
      snapshot_service: SnapshotService,
      client: GeminiDataAnalyticsClient,
      gen_ai_client: GenAIClient | None = None,
      suggestion_service: (
          Any | None
      ) = None,  # Avoid circular import if needed, or import properly
  ):
    """Initializes the ExecutionService."""
    self.session = session
    self.snapshot_service = snapshot_service
    self.client = client
    self._gen_ai_client = gen_ai_client
    self.suggestion_service = suggestion_service
    # Instantiate Repositories
    self.agent_repository = AgentRepository(session)
    self.run_repository = RunRepository(session)
    self.suite_repository = SuiteRepository(session)
    self.trial_repository = TrialRepository(session)

  def create_run(self, agent_id: int, test_suite_id: int) -> Run:
    """Creates a new Run by snapshotting the suite and creating trials.

    Args:
      agent_id: The ID of the Agent to test.
      test_suite_id: The ID of the Test Suite to run.

    Returns:
      The newly created Run (in PENDING status).

    Raises:
      ValueError: If agent or suite not found.
    """
    agent = self.agent_repository.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    self._validate_agent_credentials(agent)

    # 1. Snapshot the Suite (Core "Freeze" step)
    snapshot = self.snapshot_service.create_snapshot(suite_id=test_suite_id)

    # 2. Capture Agent Context Snapshot (Full published context from GDA)
    agent_context_snapshot = {}
    try:
      agent_name = (
          f"projects/{agent.project_id}/locations/{agent.location}/"
          f"dataAgents/{agent.agent_resource_id}"
      )
      # Fetch actual published context from GDA
      agent_context_snapshot = self.client.get_agent_context(
          agent_name=agent_name, context_target="published"
      )
    except Exception as e:  # pylint: disable=broad-exception-caught
      logging.warning("Failed to fetch full agent context for snapshot: %s", e)

    # 3. Create the Run
    run = self.run_repository.create(
        test_suite_snapshot_id=snapshot.id,
        agent_id=agent.id,
        agent_context_snapshot=agent_context_snapshot,
    )

    # 4. Create Trials for each Example in the Snapshot
    # This prepares the specific work items to be processed.
    for example_snap in snapshot.examples:
      self.trial_repository.create(
          run_id=run.id,
          example_snapshot_id=example_snap.id,
      )

    return run

  def get_run(self, run_id: int) -> Run | None:
    """Gets a Run by ID."""
    return self.run_repository.get_by_id(run_id)

  def list_runs(self, limit: int = 100, offset: int = 0) -> list[Run]:
    """Lists Runs."""
    return list(self.run_repository.list_all(limit=limit, offset=offset))

  def list_trials(self, run_id: int) -> list[Trial]:
    """Lists Trials for a Run."""
    return list(self.trial_repository.list_for_run(run_id))

  def get_trial(self, trial_id: int) -> Trial | None:
    """Gets a Trial by ID."""
    return self.session.get(Trial, trial_id)

  @property
  def gen_ai_client(self) -> GenAIClient:
    """Returns the GenAIClient, initializing it if necessary."""
    if self._gen_ai_client is None:
      self._gen_ai_client = GenAIClient(
          project=settings.gcp_genai_project,
          location=settings.gcp_genai_location,
      )
    return self._gen_ai_client

  def execute_trial(self, trial_id: int) -> Trial:
    """Executes a single trial by ID.

    Args:
      trial_id: The ID of the Trial to execute.

    Returns:
      The executed Trial object.
    """
    trial = self.trial_repository.get_trial(trial_id)
    if not trial:
      raise ValueError(f"Trial with id {trial_id} not found")

    # Double check status if needed, but usually worker claims it first
    # If it's already completed, we might want to skip or re-run based on caller intent.
    # For now, we assume it's claimed and RUNNING.

    run = trial.run
    agent = self.agent_repository.get_by_id(run.agent_id)
    if not agent:
      raise ValueError(f"Agent with id {run.agent_id} not found")

    self._execute_trial(trial, agent)
    return trial

  def _execute_trial(self, trial: Trial, agent: Agent):
    """Executes a single trial with granular status tracking."""
    logging.info("Executing trial %s", trial.id)
    trial.status = RunStatus.RUNNING
    trial.started_at = None
    trial.completed_at = None
    trial.output_text = None
    trial.error_message = None
    trial.error_traceback = None
    trial.trace_results = None
    trial.assertion_results = []
    self.session.commit()

    try:
      # --- Stage 1: EXECUTING (Agent Interaction) ---
      trial.status = RunStatus.EXECUTING
      trial.started_at = datetime.datetime.now(datetime.timezone.utc)
      self.session.commit()

      # Prepare inputs
      question = trial.example_snapshot.question
      # Use the resource ID from the agent model (source of truth for the model identity)
      agent_resource_id = (
          f"projects/{agent.project_id}/locations/{agent.location}/"
          f"dataAgents/{agent.agent_resource_id}"
      )

      # Call Client (ExecutionService is now guaranteed to have a client)
      response = self.client.ask_question(
          agent_id=agent_resource_id,
          question=question,
          client_id=agent.looker_client_id,
          client_secret=agent.looker_client_secret,
      )

      # Mark completion time immediately after response
      trial.completed_at = datetime.datetime.now(datetime.timezone.utc)

      # Save results
      trial.trace_results = [
          json_format.MessageToDict(
              item._pb,  # pylint: disable=protected-access
              preserving_proto_field_name=True,
          )
          for item in response.protobuf_response
      ]

      # Extract response text (Final Answer)
      response_text = ""
      for message in reversed(response.protobuf_response):
        if hasattr(message, "system_message"):
          sys_msg = message.system_message
          if hasattr(sys_msg, "text") and hasattr(sys_msg.text, "parts"):
            response_text += " ".join(sys_msg.text.parts)
            break

      trial.output_text = response_text.strip()

      # Duration and TTFR are now purely derived from timestamps/trace in the model properties.

      if response.error_message:
        trial.error_message = response.error_message
        trial.status = RunStatus.FAILED
        trial.failed_stage = "EXECUTING"
        self.session.commit()
        return

      # Offline evaluation only handles assertions (suggestions require LLM
      # interaction)
      # --- Stage 2: EVALUATING (Assertions & Suggestions) ---
      trial.status = RunStatus.EVALUATING
      self.session.commit()

      # Execute Assertions
      assertions = []
      for snap in trial.example_snapshot.asserts:
        assertions.append(assertion_mappers.snapshot_model_to_schema(snap))

      results = assert_engine.evaluate_all(
          response=response,
          assertions=assertions,
          llm_client=self.gen_ai_client,
          question=question,
      )

      # Save results to DB
      for snap, res in zip(trial.example_snapshot.asserts, results):
        trial.assertion_results.append(
            AssertionResult(
                assertion_snapshot_id=snap.id,
                passed=res.passed,
                score=res.score,
                reasoning=res.reasoning,
                error_message=None,
            )
        )

      # Generate Suggestions
      if self.suggestion_service and trial.trace_results:
        try:
          trace = [
              (t if isinstance(t, dict) else json_format.MessageToDict(t))
              for t in trial.trace_results
          ]
          suggestions = self.suggestion_service.suggest_assertions_from_trace(
              trace=trace,
              existing_assertions=assertions,
          )
          for s in suggestions:
            trial.suggested_asserts.append(
                assertion_mappers.schema_to_suggested_model(s, trial.id)
            )
        except Exception as e:
          logging.warning("Error generating suggestions: %s", e)

      # Finalize
      trial.status = RunStatus.COMPLETED
      self.session.commit()

    except Exception as e:
      logging.error("Error executing trial %s: %s", trial.id, e)
      # Determine failure stage based on current status before setting it to FAILED
      trial.failed_stage = trial.status.value
      trial.status = RunStatus.FAILED
      trial.error_message = str(e)
      trial.error_traceback = traceback.format_exc()
      self.session.commit()

  def evaluate_offline(
      self, trial_id: int, assertions: list[Assertion]
  ) -> list[AssertionResult]:
    """Evaluates assertions on a completed trial without re-running the query.

    Args:
        trial_id: The ID of the trial to evaluate.
        assertions: The list of assertions to check.

    Returns:
        A list of AssertionResult schema objects.
    """
    trial = self.get_trial(trial_id)
    if not trial:
      raise ValueError(f"Trial with id {trial_id} not found")

    if not trial.trace_results:
      logging.warning("No trace results found for trial %s", trial_id)
      return []

    # Reconstruct AskQuestionResponse
    # We construct a dummy duration because we only care about functional asserts usually,
    # or we should store duration in trial to be precise.
    # Trial has duration_ms.
    duration = DurationMetrics(
        total_duration=trial.duration_ms or 0, time_to_first_response=0
    )

    response = AskQuestionResponse(
        response=trial.trace_results,
        duration=duration,
        error_message=trial.error_message,
    )

    results = assert_engine.evaluate_all(
        response=response,
        assertions=assertions,
        llm_client=self.gen_ai_client,
        question=trial.example_snapshot.question,
    )

    # Note: We are returning the results but NOT updating the trial in DB
    # to avoid overwriting the original run's integrity unless requested.
    return results

  def regenerate_trial_suggestions(self, trial_id: int):
    """Regenerates suggested assertions for a trial.

    Args:
        trial_id: The ID of the trial to regenerate suggestions for.
    """
    trial = self.get_trial(trial_id)
    if not trial:
      raise ValueError(f"Trial with id {trial_id} not found")

    if not self.suggestion_service:
      logging.warning(
          "No suggestion service configured for regenerate_trial_suggestions"
      )
      return

    # 1. Clear existing suggestions
    trial.suggested_asserts = []
    self.session.commit()

    # 2. Prepare trace
    trace = [
        (t if isinstance(t, dict) else json_format.MessageToDict(t))
        for t in trial.trace_results or []
    ]

    # 3. Map existing assertions for deduplication
    # We include BOTH the original snapshot asserts AND the current live example asserts
    # because the question might have evolved since the trial was run.
    existing_assertions = []
    seen_hashes = set()

    def add_unique(a_schema):
      h = self.suggestion_service._hash_assertion(a_schema)
      if h not in seen_hashes:
        existing_assertions.append(a_schema)
        seen_hashes.add(h)

    # 3a. Add snapshot asserts
    for snap in trial.example_snapshot.asserts:
      add_unique(assertion_mappers.snapshot_model_to_schema(snap))

    # 3b. Add live asserts from the original question (if it still exists)
    q_id = trial.example_snapshot.original_example_id
    if q_id:
      original_example = self.session.get(Example, q_id)
      if original_example:
        for a_model in original_example.asserts:
          add_unique(assertion_mappers.model_to_schema(a_model))

    # 4. Generate new suggestions
    suggestions = self.suggestion_service.suggest_assertions_from_trace(
        trace=trace,
        existing_assertions=existing_assertions,
    )
    logging.info(
        "Generated %s suggestions for trial %s", len(suggestions), trial_id
    )

    # 5. Save to DB
    for s in suggestions:
      trial.suggested_asserts.append(
          assertion_mappers.schema_to_suggested_model(s, trial.id)
      )
    self.session.commit()
    logging.info("Saved suggestions to DB for trial %s", trial_id)

  def execute_ephemeral_test(
      self, agent_id: int, question: str, assertions: list[Assertion]
  ) -> "EphemeralTestResult":  # Forward ref or string
    """Executes a single ephemeral test (Playground run).

    Args:
        agent_id: The ID of the Agent to test.
        question: The question to ask.
        assertions: The list of assertions to check.

    Returns:
        An EphemeralTestResult object.
    """
    # Import locally to avoid circular imports if strictly needed,
    # but EphemeralTestResult is in schemas.execution.
    # We should import it at top level if possible.
    # Using 'dict' return type annotation update for now requires import.

    agent = self.agent_repository.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    self._validate_agent_credentials(agent)

    agent_resource_id = f"projects/{agent.project_id}/locations/{agent.location}/dataAgents/{agent.agent_resource_id}"

    # 3. Call Client
    response = self.client.ask_question(
        agent_id=agent_resource_id,
        question=question,
        client_id=agent.looker_client_id,
        client_secret=agent.looker_client_secret,
    )

    # 4. Evaluate Assertions
    results = assert_engine.evaluate_all(
        response=response,
        assertions=assertions,
        llm_client=self.gen_ai_client,
        question=question,
    )

    # 5. Construct Result
    trace_results = [
        json_format.MessageToDict(m._pb) for m in response.protobuf_response
    ]

    duration_ms = 0
    if response.duration and response.duration.total_duration is not None:
      duration_ms = response.duration.total_duration

    # Extract SQL or Text for convenience
    generated_sql = ""
    response_text = ""
    for message in response.protobuf_response:
      if "system_message" in message:
        sys_msg = message.system_message
        if "text" in sys_msg:
          response_text += " ".join(sys_msg.text.parts) + "\n"
        if "data" in sys_msg and "generated_sql" in sys_msg.data:
          generated_sql = sys_msg.data.generated_sql

    return EphemeralTestResult(
        passed=all(r.passed for r in results) if results else True,
        score=sum(r.score for r in results) / len(results) if results else None,
        duration_ms=duration_ms,
        assertion_results=results,
        response_text=response_text.strip(),
        generated_sql=generated_sql,
        trace=trace_results,
        error_message=response.error_message,
    )

  def _validate_agent_credentials(self, agent: Agent):
    """Validates that Looker agents have credentials."""
    if not agent.datasource_config:
      return

    is_looker = (
        "instance_uri" in agent.datasource_config
        or "looker_instance_uri" in agent.datasource_config
    )
    if is_looker:
      if not agent.looker_client_id or not agent.looker_client_secret:
        raise ValueError(
            "Looker datasource requires Looker Client ID and Secret. "
            "Please edit the agent to provide them."
        )
