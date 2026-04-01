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

"""Runs Client implementation for evaluating runs and trials."""

import datetime
import logging
import threading
from typing import Any
from typing import Sequence

from fast_depends import Depends
from fast_depends import inject
from prism.client import dependencies
from prism.common.schemas import execution as execution_schemas
from prism.common.schemas import timeline as timeline_schemas
from prism.server.clients.gen_ai_client import GenAIClient
from prism.server.config import settings
from prism.server.db import SessionLocal
from prism.server.models.assertion import SuggestedAssertion
from prism.server.models.run import Trial
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services.execution_service import ExecutionService
from prism.server.services.suggestion_service import SuggestionService
from prism.server.services.timeline_service import TimelineService
import sqlalchemy


def _map_run(model: Any) -> execution_schemas.RunSchema:
  """Maps a database Run model to a RunSchema."""
  return execution_schemas.RunSchema.model_validate(model)


def _map_trial(model: Any) -> execution_schemas.Trial:
  """Maps a database Trial model to a Trial schema."""
  try:
    schema = execution_schemas.Trial.model_validate(model)
    if hasattr(model, "example_snapshot") and model.example_snapshot:
      schema.question = model.example_snapshot.question

    return schema
  except Exception as e:
    logging.error(
        "Failed to map trial %s: %s", getattr(model, "id", "unknown"), e
    )
    # Re-raise so callers can handle or crash as before, but with logs
    raise e


class RunsClient:
  """Runs Client implementation."""

  @inject
  def list_runs(
      self,
      agent_id: int | None = None,
      original_suite_id: int | None = None,
      status: execution_schemas.RunStatus | None = None,
      include_archived: bool = False,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> Sequence[execution_schemas.RunSchema]:
    """Lists evaluation runs with optional filtering."""

    models = repo.list_all(
        agent_id=agent_id,
        original_suite_id=original_suite_id,
        status=status,
        include_archived=include_archived,
    )
    return [_map_run(m) for m in models]

  @inject
  def get_latest_runs_with_stats(
      self,
      agent_ids: Sequence[int],
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> dict[int, execution_schemas.RunStatsSchema]:
    """Gets the latest run for multiple agents, including average accuracy."""
    # The repo returns dict[int, RunStatsTypedDict] with "run" and "accuracy"
    data = repo.get_latest_runs_with_stats(agent_ids)
    result = {}
    for agent_id, stats in data.items():
      # The repo returns dict[int, RunStatsTypedDict]
      run_schema = _map_run(stats["run"])
      result[agent_id] = execution_schemas.RunStatsSchema(
          run=run_schema, accuracy=stats["accuracy"]
      )
    return result

  @inject
  def get_run_history_for_agents(
      self,
      agent_ids: Sequence[int],
      limit: int = 10,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> dict[int, list[execution_schemas.RunHistoryPoint]]:
    """Gets execution history for multiple agents."""
    # The repo returns dict[int, list[dict]]
    data = repo.get_run_history_for_agents(agent_ids, limit=limit)
    result = {}
    for agent_id, history_list in data.items():
      points = []
      for point in history_list:
        points.append(execution_schemas.RunHistoryPoint.model_validate(point))
      result[agent_id] = points

    return result

  @inject
  def get_run(
      self,
      run_id: int,
      service: ExecutionService = Depends(dependencies.get_execution_service),
      timeline_service: TimelineService = Depends(
          dependencies.get_timeline_service
      ),
  ) -> execution_schemas.RunSchema | None:
    """Gets a specific evaluation run by ID, including aggregated statistics."""

    model = service.get_run(run_id)
    if not model:
      return None

    run = _map_run(model)
    # Aggregate tool timings from trials
    run_tool_timings = {}
    for trial_model in model.trials:
      trial_timings = timeline_service.calculate_tool_timings(
          trace=trial_model.trace_results or [],
          ttfr_ms=trial_model.ttfr_ms or 0,
      )
      for tool, duration in trial_timings.items():
        run_tool_timings[tool] = run_tool_timings.get(tool, 0) + duration

    run.tool_timings = run_tool_timings
    return run

  @inject
  def list_trials(
      self,
      run_id: int,
      service: ExecutionService = Depends(dependencies.get_execution_service),
      timeline_service: TimelineService = Depends(
          dependencies.get_timeline_service
      ),
  ) -> Sequence[execution_schemas.Trial]:
    """Lists all trials for a given run ID."""

    models = service.get_run(run_id).trials if service.get_run(run_id) else []
    trials = []
    for m in models:
      t = _map_trial(m)
      t.tool_timings = timeline_service.calculate_tool_timings(
          trace=t.trace_results or [],
          ttfr_ms=t.ttfr_ms or 0,
      )
      trials.append(t)
    return trials

  @inject
  def create_run(
      self,
      agent_id: int,
      test_suite_id: int,
      generate_suggestions: bool = False,
      concurrency: int = 2,
      service: ExecutionService = Depends(dependencies.get_execution_service),
  ) -> execution_schemas.RunSchema:
    """Creates a new evaluation run for an agent and test suite."""
    model = service.create_run(
        agent_id=agent_id,
        test_suite_id=test_suite_id,
        generate_suggestions=generate_suggestions,
        concurrency=concurrency,
    )
    return execution_schemas.RunSchema.model_validate(model)

  @inject
  def get_agent_dashboard_stats(
      self,
      agent_id: int,
      days: int = 30,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> dict[str, Any]:
    """Gets aggregated dashboard stats for an agent."""
    return repo.get_agent_dashboard_stats(agent_id=agent_id, days=days)

  @inject
  def get_trial(
      self,
      trial_id: int,
      repo: TrialRepository = Depends(dependencies.get_trial_repository),
      timeline_service: TimelineService = Depends(
          dependencies.get_timeline_service
      ),
  ) -> execution_schemas.Trial | None:
    """Fetch a single Trial by ID."""
    model = repo.get_trial(trial_id)
    if not model:
      return None

    trial = _map_trial(model)
    trial.tool_timings = timeline_service.calculate_tool_timings(
        trace=trial.trace_results or [],
        ttfr_ms=trial.ttfr_ms or 0,
    )
    return trial

  @inject
  def get_trial_timeline(
      self,
      trial_id: int,
      repo: TrialRepository = Depends(dependencies.get_trial_repository),
      timeline_service: TimelineService = Depends(
          dependencies.get_timeline_service
      ),
  ) -> timeline_schemas.Timeline | None:
    """Generates a timeline for a given trial."""
    trial = repo.get_trial(trial_id)
    if not trial:
      return None

    # Construct Timeline logic
    baseline = trial.started_at or trial.created_at
    trace_results = trial.trace_results or []
    if isinstance(trace_results, dict):
      trace_results = trace_results.get("response", [])

    timeline_obj = timeline_service.create_timeline_from_trace(
        trace=trace_results,
        ttfr_ms=trial.ttfr_ms or 0,
        total_duration_ms=trial.duration_ms or 0,
        start_time_baseline=baseline,
    )

    # Prepend User Input (Question)
    question = (
        trial.example_snapshot.question if trial.example_snapshot else "Unknown"
    )
    user_input_event = timeline_schemas.TimelineEvent(
        icon="bi:person-fill",
        title="Question",
        content=question,
        content_type="text",
        duration_ms=0,
        cumulative_duration_ms=0,
    )
    timeline_obj.events.insert(0, user_input_event)

    return timeline_obj

  @inject
  def execute_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> execution_schemas.RunSchema:
    """Queues a run for execution (status remains PENDING)."""
    model = repo.get_by_id(run_id)
    if not model:
      raise ValueError(f"Run {run_id} not found")

    logging.info(
        "Run %s queued for execution (Current Status: %s). Worker will pick it"
        " up.",
        run_id,
        model.status,
    )
    # No status change - Worker auto-promotes PENDING runs
    # We commit just in case there were other changes, though query is read-only here
    repo.session.commit()
    return _map_run(model)

  @inject
  def curate_suggestion(
      self,
      suggestion_id: int,
      action: str,
      service: SuggestionService = Depends(dependencies.get_suggestion_service),
  ) -> None:
    """Accepts or rejects a suggested assertion."""
    service.curate_suggestion(suggestion_id, action)

  @inject
  def parse_timeline(
      self,
      trace: list[dict[str, Any]],
      ttfr_ms: int = 0,
      total_duration_ms: int = 0,
      hide_query_schema: bool = False,
  ) -> timeline_schemas.Timeline:
    """Parses a trace into a timeline."""
    service = TimelineService()
    return service.create_timeline_from_trace(
        trace=trace,
        ttfr_ms=ttfr_ms,
        total_duration_ms=total_duration_ms,
        hide_query_schema=hide_query_schema,
    )

  @inject
  def list_trials_with_suggestions(
      self,
      original_example_id: int,
      repo: TrialRepository = Depends(dependencies.get_trial_repository),
  ) -> Sequence[execution_schemas.Trial]:
    """Lists recent trials for a question that have suggestions."""
    models = repo.list_trials_with_suggestions(original_example_id)
    return [_map_trial(m) for m in models]

  @inject
  def execute_run_async(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Queues a run for execution (status remains PENDING)."""
    model = repo.get_by_id(run_id)
    if not model:
      raise ValueError(f"Run {run_id} not found")

    logging.info(
        "Run %s queued for execution (Current Status: %s). Worker will pick it"
        " up.",
        run_id,
        model.status,
    )
    # No status change - Worker auto-promotes PENDING runs

  @inject
  def pause_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Pauses a RUNNING run."""
    model = repo.get_by_id(run_id)
    if model:
      model.status = execution_schemas.RunStatus.PAUSED
      repo.session.commit()

  @inject
  def resume_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Resumes a PAUSED run."""
    model = repo.get_by_id(run_id)
    if model:
      model.status = execution_schemas.RunStatus.RUNNING
      repo.session.commit()

  @inject
  def cancel_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Cancels a RUNNING or PAUSED run."""
    model = repo.get_by_id(run_id)
    if model:
      model.status = execution_schemas.RunStatus.CANCELLED
      model.completed_at = datetime.datetime.now(datetime.timezone.utc)
      # Also cancel any PENDING trials for this run
      sqlalchemy.update(Trial).where(Trial.run_id == run_id).where(
          Trial.status == execution_schemas.RunStatus.PENDING
      ).values(status=execution_schemas.RunStatus.CANCELLED)
      repo.session.commit()

  @inject
  def archive_run(
      self,
      run_id: int,
      service: ExecutionService = Depends(dependencies.get_execution_service),
  ) -> execution_schemas.RunSchema:
    """Archives a run."""
    model = service.archive_run(run_id=run_id)
    return _map_run(model)

  @inject
  def unarchive_run(
      self,
      run_id: int,
      service: ExecutionService = Depends(dependencies.get_execution_service),
  ) -> execution_schemas.RunSchema:
    """Unarchives a run."""
    model = service.unarchive_run(run_id=run_id)
    return _map_run(model)

  @inject
  def retry_trial(
      self,
      trial_id: int,
      repo: TrialRepository = Depends(dependencies.get_trial_repository),
  ) -> None:
    """Resets a trial to PENDING so the worker pool picks it up again."""
    model = repo.get_trial(trial_id)
    if model:
      model.status = execution_schemas.RunStatus.PENDING
      model.started_at = None
      model.completed_at = None
      model.output_text = None
      model.error_message = None
      model.error_traceback = None
      model.trace_results = None
      model.assertion_results = []

      # Ensure the run is also RUNNING if it was completed or failed
      if model.run.status in (
          execution_schemas.RunStatus.COMPLETED,
          execution_schemas.RunStatus.FAILED,
      ):
        model.run.status = execution_schemas.RunStatus.RUNNING
        model.run.completed_at = None

      repo.session.commit()

  @inject
  def regenerate_suggestions_async(
      self,
      trial_id: int,
      app: Any,
  ) -> None:
    """Regenerates suggestions for a trial in a background thread."""

    def _run():
      with app.app_context():
        with SessionLocal() as session:
          trial_repo = TrialRepository(session)
          example_repo = ExampleRepository(session)

          gen_ai_client_inst = GenAIClient(
              project=settings.gcp_genai_project,
              location=settings.gcp_genai_location,
          )
          service = SuggestionService(
              gen_ai_client_inst, trial_repo, example_repo
          )

          # Logic from EvaluationRunner.regenerate_suggestions
          trial = trial_repo.get_trial(trial_id)
          if not trial:
            return

          # Clear existing suggestions
          session.execute(
              sqlalchemy.delete(SuggestedAssertion).where(
                  SuggestedAssertion.trial_id == trial_id
              )
          )

          # Generate new ones
          suggestions = service.suggest_assertions(trial_id)

          # Save to DB
          for s in suggestions:
            # We need to map assertion schema back to model params
            model_suggestion = SuggestedAssertion(
                trial_id=trial_id,
                type=s.type,
                weight=s.weight,
                params=s.model_dump(exclude={"id", "type", "weight"}),
            )
            session.add(model_suggestion)
          session.commit()

    threading.Thread(target=_run).start()

  @inject
  def get_unique_suites_from_snapshots(
      self,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> list[dict[str, Any]]:
    """Gets unique suites that have been snapshotted for runs."""
    return repo.get_unique_suites_from_snapshots()
