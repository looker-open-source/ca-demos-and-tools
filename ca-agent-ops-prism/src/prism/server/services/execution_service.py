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
from typing import Any
import uuid

from google.api_core import exceptions as api_exceptions
from google.protobuf import json_format
from prism.common.schemas.agent import normalize_location
from prism.common.schemas.assertion import Assertion
from prism.common.schemas.execution import EphemeralTestResult

# The same helper the GDA client puts on a failed ask_question, so a trial that
# failed in the call and one that failed around it read the same way.
from prism.server.clients.gemini_data_analytics_client import (
    _readable_api_error,
)
from prism.server.clients.gemini_data_analytics_client import (
    GeminiDataAnalyticsClient,
)
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.config import settings
from prism.server.models.agent import Agent
from prism.server.models.assertion import AssertionResult
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
from sqlalchemy import orm

logger = logging.getLogger(__name__)


def displayable_error(e: Exception) -> str:
  """What a failed trial is allowed to say on the trial detail page.

  prism has no authentication, so this text is readable by anyone who can
  reach the port and it lands in the screenshots attached to bugs. A GCP error
  is trimmed to its status and message. Anything else raised inside prism is
  named by its type alone: a SQLAlchemy error carries the statement and its
  bound parameters, and the caller pairs this with a reference id that finds
  the whole thing in the server log.
  """
  if isinstance(e, api_exceptions.GoogleAPICallError):
    return _readable_api_error(e)
  return f"{type(e).__name__} raised while running this trial."


class ExecutionService:
  """Service for managing test executions."""

  def __init__(
      self,
      session: orm.Session,
      snapshot_service: SnapshotService,
      client: GeminiDataAnalyticsClient,
      gen_ai_client: GenAIClient | None = None,
      suggestion_service: Any | None = None,
  ):
    """Initializes the ExecutionService."""
    self.session = session
    self.snapshot_service = snapshot_service
    self.client = client
    self._gen_ai_client = gen_ai_client
    self.suggestion_service = suggestion_service
    self.agent_repository = AgentRepository(session)
    self.run_repository = RunRepository(session)
    self.suite_repository = SuiteRepository(session)
    self.trial_repository = TrialRepository(session)

  def create_run(
      self,
      agent_id: int,
      test_suite_id: int,
      generate_suggestions: bool = False,
      concurrency: int = 2,
  ) -> Run:
    """Creates a new Run by snapshotting the suite and creating trials.

    Args:
      agent_id: The ID of the Agent to test.
      test_suite_id: The ID of the Test Suite to run.
      generate_suggestions: Whether to generate suggested assertions.
      concurrency: Number of parallel trials for this run.

    Returns:
      The newly created Run (in PENDING status).

    Raises:
      ValueError: If the agent or the suite is not found, if the suite has no
        active questions, if the agent has no datasource, or if a Looker agent
        is missing its client id or its secret. The last two come from
        _validate_agent_can_run and are refusals the user has to act on.
    """
    agent = self.agent_repository.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    self._validate_agent_can_run(agent)

    # Checked before the snapshot, so a rejected run leaves nothing behind.
    # A run with no trials used to be created happily and then sit RUNNING
    # forever, holding up every run queued after it.
    suite = self.suite_repository.get_by_id(test_suite_id)
    if not suite:
      raise ValueError(f"TestSuite with id {test_suite_id} not found")
    # Against the archived filter, because that is what the snapshot takes.
    # suite.examples is the unfiltered backref, so a suite whose questions
    # were all archived passed this guard and then snapshotted to nothing.
    active_examples = [e for e in suite.examples if not e.is_archived]
    if not active_examples:
      raise ValueError(
          f"Test suite '{suite.name}' has no active questions, so there is"
          " nothing to run. Add a question first."
      )

    # Freeze the suite contents so later edits cannot change this run.
    snapshot = self.snapshot_service.create_snapshot(suite_id=test_suite_id)

    # Capture the full published agent context from GDA.
    agent_context_snapshot = {}
    try:
      loc = normalize_location(agent.location)
      agent_name = (
          f"projects/{agent.project_id}/locations/{loc}/"
          f"dataAgents/{agent.agent_resource_id}"
      )
      agent_context_snapshot = self.client.get_agent_context(
          agent_name=agent_name, context_target="published"
      )
    except Exception as e:  # pylint: disable=broad-exception-caught
      logger.warning("Failed to fetch full agent context for snapshot: %s", e)

    # One trial per example in the snapshot, written in the same transaction
    # as the run. A run committed before its trials is a PENDING run with
    # nothing to wait for, and the worker completes it on its next pass.
    return self.run_repository.create(
        test_suite_snapshot_id=snapshot.id,
        agent_id=agent.id,
        agent_context_snapshot=agent_context_snapshot,
        generate_suggestions=generate_suggestions,
        concurrency=concurrency,
        example_snapshot_ids=[e.id for e in snapshot.examples],
    )

  def get_run(self, run_id: int) -> Run | None:
    """Gets a Run by ID."""
    return self.run_repository.get_by_id(run_id)

  def list_runs(
      self, limit: int = 100, offset: int = 0, include_archived: bool = False
  ) -> list[Run]:
    """Lists Runs."""
    return list(
        self.run_repository.list_all(
            limit=limit, offset=offset, include_archived=include_archived
        )
    )

  def archive_run(self, run_id: int) -> Run:
    """Archives a run."""
    return self.run_repository.archive(run_id=run_id)

  def unarchive_run(self, run_id: int) -> Run:
    """Unarchives a run."""
    return self.run_repository.unarchive(run_id=run_id)

  def list_trials(self, run_id: int) -> list[Trial]:
    """Lists Trials for a Run."""
    return list(self.trial_repository.list_for_run(run_id))

  def get_trial(self, trial_id: int) -> Trial | None:
    """Reads one trial. Nothing is eager loaded, unlike list_trials."""
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

    run = trial.run
    agent = self.agent_repository.get_by_id(run.agent_id)
    if not agent:
      raise ValueError(f"Agent with id {run.agent_id} not found")

    self._execute_trial(trial, agent)
    return trial

  def _execute_trial(self, trial: Trial, agent: Agent):
    """Executes a single trial with granular status tracking."""
    logger.info("Executing trial %s", trial.id)
    trial.status = RunStatus.RUNNING
    # started_at is left as the claim set it. Clearing it here committed a
    # RUNNING row with no start time, and the stale sweep selects on
    # started_at < cutoff, which NULL never satisfies. A trial that wedged
    # between this commit and the EXECUTING one below was invisible to the
    # sweep for good and held its run's capacity for ever. The EXECUTING commit
    # overwrites it a moment later, so nothing downstream reads the claim time.
    trial.completed_at = None
    trial.output_text = None
    trial.error_message = None
    trial.error_traceback = None
    trial.failed_stage = None
    trial.trace_results = None
    trial.assertion_results = []
    # Both of these survived a retry. The trial page reads failed_stage to
    # caption the error card, so a retry that got further still showed the
    # stage the first attempt died in, and the suggestions panel offered
    # assertions written against an answer that had been replaced.
    trial.suggested_asserts = []
    self.session.commit()

    try:
      trial.status = RunStatus.EXECUTING
      trial.started_at = datetime.datetime.now(datetime.timezone.utc)
      self.session.commit()

      question = trial.example_snapshot.question
      loc = normalize_location(agent.location)
      agent_resource_id = (
          f"projects/{agent.project_id}/locations/{loc}/"
          f"dataAgents/{agent.agent_resource_id}"
      )

      response = self.client.ask_question(
          agent_id=agent_resource_id,
          question=question,
          client_id=agent.looker_client_id,
          client_secret=agent.looker_client_secret,
      )

      # Stamped here, not after the assertions, so the trial duration is the
      # time the agent took and not the time the evaluation took.
      trial.completed_at = datetime.datetime.now(datetime.timezone.utc)

      trial.trace_results = []
      for item in response.protobuf_response:
        if isinstance(item, dict):
          trial.trace_results.append(item)
        elif hasattr(item, "_pb"):
          trial.trace_results.append(
              json_format.MessageToDict(
                  item._pb,  # pylint: disable=protected-access
                  preserving_proto_field_name=True,
              )
          )
        elif hasattr(item, "to_dict"):
          trial.trace_results.append(item.to_dict())
        else:
          trial.trace_results.append(dict(item))

      response_text_parts = []
      for message in response.protobuf_response:
        if hasattr(message, "system_message"):
          sys_msg = message.system_message
          if hasattr(sys_msg, "text"):
            text_type = getattr(sys_msg.text, "text_type", 0)
            if text_type in (1, "FINAL_RESPONSE"):
              if hasattr(sys_msg.text, "parts"):
                response_text_parts.append(" ".join(sys_msg.text.parts))

      response_text = "\n\n".join(response_text_parts)

      trial.output_text = response_text.strip()

      # Duration and TTFR are derived from the timestamps and the trace by the
      # model properties, so there is nothing to store here.

      if response.error_message:
        trial.error_message = response.error_message
        trial.status = RunStatus.FAILED
        trial.failed_stage = "EXECUTING"
        self.session.commit()
        return

      trial.status = RunStatus.EVALUATING
      self.session.commit()

      assertions = []
      for snap in trial.example_snapshot.asserts:
        assertions.append(assertion_mappers.snapshot_model_to_schema(snap))

      results = assert_engine.evaluate_all(
          response=response,
          assertions=assertions,
          llm_client=self.gen_ai_client,
          question=question,
      )

      for snap, res in zip(trial.example_snapshot.asserts, results):
        if res.error_message:
          # The check could not be run at all, which is not the agent getting
          # it wrong. Trial.score is a weighted mean over the rows that exist,
          # so the row is left out rather than written with score 0: a Vertex
          # 400 or a quota blip on the AI judge used to land as a regression
          # and the run's accuracy tracked Vertex, not the agent.
          logger.warning(
              "Assertion %s on trial %s was not evaluated: %s",
              snap.id,
              trial.id,
              res.error_message,
          )
          continue
        trial.assertion_results.append(
            AssertionResult(
                assertion_snapshot_id=snap.id,
                passed=res.passed,
                score=res.score,
                reasoning=res.reasoning,
                error_message=None,
            )
        )

      if (
          self.suggestion_service
          and trial.trace_results
          and trial.run.generate_suggestions
      ):
        try:
          trace = []
          for t in trial.trace_results:
            if isinstance(t, dict):
              trace.append(t)
            elif hasattr(t, "to_dict"):
              trace.append(t.to_dict())
            else:
              trace.append(json_format.MessageToDict(t))
          suggestions = self.suggestion_service.suggest_assertions_from_trace(
              trace=trace,
              existing_assertions=assertions,
          )
          for s in suggestions:
            trial.suggested_asserts.append(
                assertion_mappers.schema_to_suggested_model(s, trial.id)
            )
        except Exception as e:
          logger.warning("Error generating suggestions: %s", e)

      trial.status = RunStatus.COMPLETED
      self.session.commit()

    except Exception as e:
      # The reference id is the only thing tying the page to the log. str(e)
      # and format_exc used to be stored and rendered on the trial: a GDA
      # error names the project, the dataAgents path, the Looker instance and
      # the caller service account, and the traceback adds the container's
      # filesystem layout and the installed library versions.
      ref = uuid.uuid4().hex[:6]
      logger.exception("Error executing trial %s (ref %s)", trial.id, ref)
      # Read the stage off the status before it becomes FAILED.
      trial.failed_stage = trial.status.value
      trial.status = RunStatus.FAILED
      trial.error_message = f"{displayable_error(e)} (ref {ref})"
      trial.error_traceback = None
      # The attempt cleared completed_at and only the agent call stamps it, so
      # a trial that died in the call committed FAILED with a start and no end.
      # Nothing later filled it in: the worker's retry path only touches trials
      # still in flight, and this one is terminal. Trial.duration_ms was None,
      # so the trial dropped out of the dashboard's average duration and out of
      # durations_by_day, and the BigQuery export wrote both columns NULL.
      # Left alone when it is already set, so a failure in the assertions does
      # not stretch the duration past the agent call.
      if trial.completed_at is None:
        trial.completed_at = datetime.datetime.now(datetime.timezone.utc)
      self.session.commit()

  def execute_ephemeral_test(
      self, agent_id: int, question: str, assertions: list[Assertion]
  ) -> "EphemeralTestResult":
    """Executes a single ephemeral test (Playground run).

    Args:
      agent_id: The ID of the Agent to test.
      question: The question to ask.
      assertions: The list of assertions to check.

    Returns:
      An EphemeralTestResult object.
    """
    agent = self.agent_repository.get_by_id(agent_id)
    if not agent:
      raise ValueError(f"Agent with id {agent_id} not found")

    self._validate_agent_can_run(agent)

    loc = normalize_location(agent.location)
    agent_resource_id = (
        f"projects/{agent.project_id}/locations/{loc}/"
        f"dataAgents/{agent.agent_resource_id}"
    )

    response = self.client.ask_question(
        agent_id=agent_resource_id,
        question=question,
        client_id=agent.looker_client_id,
        client_secret=agent.looker_client_secret,
    )

    results = assert_engine.evaluate_all(
        response=response,
        assertions=assertions,
        llm_client=self.gen_ai_client,
        question=question,
    )

    trace_results = [
        json_format.MessageToDict(m._pb) for m in response.protobuf_response
    ]

    duration_ms = 0
    if response.duration and response.duration.total_duration is not None:
      duration_ms = response.duration.total_duration

    generated_sql = ""
    response_text_parts = []
    # ``in``, not hasattr. These are proto-plus messages, and an unset
    # singular message field still answers hasattr, because reading it returns
    # a default submessage. So the SQL branch ran for every system message and
    # each one after the SQL wrote "" over it. The SQL message is followed by
    # the result, the chart and the final answer in any real trace, so the
    # playground's SQL panel was always blank.
    for message in response.protobuf_response:
      if "system_message" in message:
        sys_msg = message.system_message
        if "text" in sys_msg:
          text_type = getattr(sys_msg.text, "text_type", 0)
          if text_type in (1, "FINAL_RESPONSE"):
            if "parts" in sys_msg.text:
              response_text_parts.append(" ".join(sys_msg.text.parts))
        # generated_sql, result and query share a oneof, so the data message
        # carrying the rows is a set ``data`` with no SQL in it.
        if "data" in sys_msg and "generated_sql" in sys_msg.data:
          generated_sql = sys_msg.data.generated_sql

    response_text = "\n\n".join(response_text_parts).strip()

    # Weighted, the way Trial.score is. A plain mean over the results gave the
    # playground a different number from the run for the same question and the
    # same assertions, and it counted an assertion the user had weighted to 0.
    # An assertion the engine could not run carries error_message and is left
    # out here for the same reason _execute_trial does not persist a row for
    # it: a judge that never answered is not a failed assertion.
    scored = [
        r for r in results if r.assertion.weight > 0 and not r.error_message
    ]
    score = None
    if scored:
      total_weight = sum(r.assertion.weight for r in scored)
      score = sum(r.score * r.assertion.weight for r in scored) / total_weight

    return EphemeralTestResult(
        # Over the same scored set. Read against every result, a failing
        # assertion the user had weighted to 0 left score at 1.0 and passed
        # at False.
        #
        # An errored call is not a pass. Its results are dropped from scored
        # above, so an example with no assertions, or one whose judge errored
        # on all of them, came out of a failed agent call with an empty set
        # and the panel painted a green check over "0 of 0 passed".
        passed=(
            not response.error_message
            and (all(r.passed for r in scored) if scored else True)
        ),
        score=score,
        duration_ms=duration_ms,
        assertion_results=results,
        response_text=response_text,
        generated_sql=generated_sql,
        trace=trace_results,
        error_message=response.error_message,
    )

  def _validate_agent_can_run(self, agent: Agent):
    """Checks the agent has a datasource, and credentials if it is Looker.

    The kind comes from the service. prism's stored config is empty for the
    datasource kinds it does not parse, so a Looker agent among those reached
    the API with no credentials and failed every trial of the run.
    """
    loc = normalize_location(agent.location)
    agent_name = (
        f"projects/{agent.project_id}/locations/{loc}/"
        f"dataAgents/{agent.agent_resource_id}"
    )

    try:
      kind = self.client.get_datasource_kind(agent_name)
    except api_exceptions.GoogleAPICallError as e:
      # The check is advisory. An agent can be added by typing a resource id
      # the caller cannot read, and blocking that would stop a run the chat
      # call would have answered.
      logger.warning("Could not read the datasource of %s: %s", agent_name, e)
      return

    if kind is None:
      raise ValueError(
          "This agent has no datasource, so there is nothing to evaluate. "
          "Add one to the agent before running it."
      )

    if kind == "looker" and not (
        agent.looker_client_id and agent.looker_client_secret
    ):
      raise ValueError(
          "Looker datasource requires Looker Client ID and Secret. "
          "Please edit the agent to provide them."
      )
