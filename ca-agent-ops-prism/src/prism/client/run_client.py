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
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.repositories.example_repository import ExampleRepository
from prism.server.repositories.run_repository import RunRepository
from prism.server.repositories.trial_repository import TrialRepository
from prism.server.services import assertion_mappers

# The module, not the three names off it. is_run_syncing and
# get_run_export_error are patched on bigquery_exporter, and a from-import
# binds past the patch.
from prism.server.services import bigquery_exporter
from prism.server.services.execution_service import ExecutionService
from prism.server.services.suggestion_service import SuggestionService
from prism.server.services.timeline_service import TimelineService
import sqlalchemy

logger = logging.getLogger(__name__)

# Statuses a run does not come back from. cancel_run refuses to touch a run
# already in one of these.
_TERMINAL_RUN_STATUSES = frozenset({
    execution_schemas.RunStatus.COMPLETED,
    execution_schemas.RunStatus.FAILED,
    execution_schemas.RunStatus.CANCELLED,
})


def _map_run(model: Any) -> execution_schemas.RunSchema:
  """Returns the RunSchema for a Run row."""
  return execution_schemas.RunSchema.model_validate(model)


def _map_trial(model: Any) -> execution_schemas.Trial:
  """Returns the Trial schema for a Trial row.

  The question lives on the example snapshot, not on the trial row, so it is
  copied onto the schema here.
  """
  try:
    schema = execution_schemas.Trial.model_validate(model)
    if hasattr(model, "example_snapshot") and model.example_snapshot:
      schema.question = model.example_snapshot.question

    return schema
  except Exception as e:
    logger.error(
        "Failed to map trial %s: %s", getattr(model, "id", "unknown"), e
    )
    # Re-raise so callers can handle or crash as before, but with logs
    raise e


class RunsClient:
  """The lifecycle of an evaluation run, from started to archived."""

  def get_bigquery_export_status(
      self, run_id: int, check_exported: bool = True
  ) -> dict[str, Any]:
    """Returns BigQuery export status for a run.

    Args:
      run_id: The run to report on.
      check_exported: Whether to ask BigQuery itself. Each check is a query job,
        so a caller that already knows the export cannot have happened (the run
        is still going) should pass False for the local-only answer.
        ``exported`` is then reported as False without asking.

    Returns:
      A dict of the flags the run-detail badge renders from, plus ``status``,
      which is "ok" when the export state is known, "failed" when an export
      failure is recorded on the run, and "unknown" when the check itself
      could not be completed.
    """
    if not settings.bigquery_export_enabled:
      return {
          "status": "ok",
          "enabled": False,
          "exported": False,
          "syncing": False,
          "failed": False,
          "error": None,
          "project": settings.bigquery_export_project,
          "dataset": settings.bigquery_export_dataset,
      }

    try:
      exporter = bigquery_exporter.BigQueryExporter()
      state = (
          exporter.check_run_exported(run_id)
          if check_exported
          else bigquery_exporter.EXPORT_STATE_NOT_EXPORTED
      )
      is_exported = state == bigquery_exporter.EXPORT_STATE_EXPORTED
      syncing = bigquery_exporter.is_run_syncing(run_id)
      error = bigquery_exporter.get_run_export_error(run_id)
      # The failed flag is set from the error alone. An export writes four
      # tables and the run row goes in whatever the other three did, so a
      # partial failure leaves is_exported True and the old
      # `error and not is_exported` reported a clean sync over the rejected
      # rows. A clean export clears the error, so a stale one cannot stick.
      #
      # A check that could not complete is its own status. It used to fold into
      # "not exported", so a permissions error on the lookup painted a finished
      # run as never exported and said so with no qualification.
      if error:
        status = "failed"
      elif state == bigquery_exporter.EXPORT_STATE_UNKNOWN:
        status = "unknown"
      else:
        status = "ok"
      return {
          "status": status,
          "enabled": True,
          "exported": is_exported,
          "syncing": syncing,
          "failed": bool(error),
          "error": error,
          "project": exporter.project_id,
          "dataset": exporter.dataset_id,
      }
    except Exception:  # pylint: disable=broad-exception-caught
      # "unknown", not "failed". A dataset the caller cannot read, or an
      # unreachable BigQuery, says nothing about whether the export happened,
      # and reporting a failure sent users to a Retry button that could not
      # help. The detail stays in the log: Prism has no auth of its own, so a
      # raw exception on the page is public, and these carry project ids,
      # dataset names and credential messages.
      logger.exception(
          "Could not determine the BigQuery export status for run %s", run_id
      )
      return {
          "status": "unknown",
          "enabled": True,
          "exported": False,
          "syncing": False,
          "failed": False,
          "error": (
              "Export status could not be determined. See the server logs."
          ),
          "project": settings.bigquery_export_project,
          "dataset": settings.bigquery_export_dataset,
      }

  def sync_run_to_bigquery(
      self, run_id: int, force: bool = True
  ) -> dict[str, Any]:
    """Starts a BigQuery export in a background thread and returns at once.

    is_in_flight is False when an export for this run was already running, in
    which case nothing new was started.
    """
    if not settings.bigquery_export_enabled:
      raise ValueError("BigQuery export is not enabled in configuration.")

    exporter = bigquery_exporter.BigQueryExporter()
    thread = exporter.export_run_async(run_id, SessionLocal, force=force)
    return {
        "status": "export_triggered",
        "run_id": run_id,
        "is_in_flight": thread is not None,
    }

  @inject
  def list_runs(
      self,
      agent_id: int | None = None,
      original_suite_id: int | None = None,
      status: execution_schemas.RunStatus | None = None,
      include_archived: bool = False,
      limit: int = 50,
      offset: int = 0,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> Sequence[execution_schemas.RunSchema]:
    """Lists evaluation runs, most recent first.

    limit and offset are named here because the repository has always taken
    them. Without them the injector dropped the keyword on the floor, so a
    caller asking for a different page silently got the first 50.
    """

    models = repo.list_all(
        agent_id=agent_id,
        original_suite_id=original_suite_id,
        status=status,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return [_map_run(m) for m in models]

  @inject
  def get_latest_runs_with_stats(
      self,
      agent_ids: Sequence[int],
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> dict[int, execution_schemas.RunStatsSchema]:
    """Gets the latest run per agent, with its average accuracy.

    Agents that have never been run are left out of the result.
    """
    data = repo.get_latest_runs_with_stats(agent_ids)
    result = {}
    for agent_id, stats in data.items():
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
    """Gets the last few runs per agent, oldest first, for the sparklines."""
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
    run_tool_timings = {}
    for trial_model in model.trials:
      trial_timings = timeline_service.calculate_tool_timings(
          trace=trial_model.trace_results or [],
          ttfr_ms=trial_model.ttfr_ms or 0,
          total_duration_ms=trial_model.duration_ms or 0,
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
    """Lists a run's trials, each with its per-tool timings filled in."""

    run = service.get_run(run_id)
    models = run.trials if run else []
    trials = []
    for m in models:
      t = _map_trial(m)
      t.tool_timings = timeline_service.calculate_tool_timings(
          trace=t.trace_results or [],
          ttfr_ms=t.ttfr_ms or 0,
          total_duration_ms=t.duration_ms or 0,
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
    """Creates a run in PENDING and leaves it for a worker to pick up.

    The suite is snapshotted at this point, so later edits to it do not change
    what this run evaluates.
    """
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
    """Gets the KPI and chart data the agent detail page is built from."""
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
    """Fetches a trial by id, or None if there is no such trial."""
    model = repo.get_trial(trial_id)
    if not model:
      return None

    trial = _map_trial(model)
    trial.tool_timings = timeline_service.calculate_tool_timings(
        trace=trial.trace_results or [],
        ttfr_ms=trial.ttfr_ms or 0,
        total_duration_ms=trial.duration_ms or 0,
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
    """Builds the trial timeline, or None if there is no such trial.

    The question is prepended as the first event. It lives on the example
    snapshot, not in the trace, so nothing else would put it on the timeline.
    """
    trial = repo.get_trial(trial_id)
    if not trial:
      return None

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
    # And as its own group. render_trace_timeline walks groups, not events, so
    # the event on its own was read by nothing and the timeline opened on the
    # agent's first step with no sign of what had been asked. Only when there
    # is a timeline to open: no groups is what the page reads as "No trace data
    # available.", and a lone question would claim a trace that does not exist.
    if timeline_obj.groups:
      timeline_obj.groups.insert(
          0,
          timeline_schemas.TimelineGroup(
              title="Question",
              duration_ms=0,
              icon="bi:person-fill",
              events=[user_input_event],
          ),
      )

    return timeline_obj

  @inject
  def curate_suggestion(
      self,
      suggestion_id: int,
      action: str,
      service: SuggestionService = Depends(dependencies.get_suggestion_service),
  ) -> None:
    """Accepts or rejects a suggested assertion.

    Accepting copies it onto the original question. Either way the suggestion
    is deleted.
    """
    service.curate_suggestion(suggestion_id, action)

  def parse_timeline(
      self,
      trace: list[dict[str, Any]],
      ttfr_ms: int = 0,
      total_duration_ms: int = 0,
  ) -> timeline_schemas.Timeline:
    """Builds a timeline from a trace the caller already holds.

    No trial id and no database read, unlike get_trial_timeline.
    """
    service = TimelineService()
    return service.create_timeline_from_trace(
        trace=trace,
        ttfr_ms=ttfr_ms,
        total_duration_ms=total_duration_ms,
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
    """Checks the run exists. The worker claims PENDING runs on its own."""
    model = repo.get_by_id(run_id)
    if not model:
      raise ValueError(f"Run {run_id} not found")

    logger.info(
        "Run %s queued for execution (Current Status: %s). Worker will pick it"
        " up.",
        run_id,
        model.status,
    )
    # No status change: the worker promotes PENDING runs on its own.

  @inject
  def pause_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Sets a PENDING or RUNNING run to PAUSED. Anything else is left alone.

    Unguarded, this wrote PAUSED over a terminal status the same way cancel
    used to. The Pause button stays on screen while the last trial finishes,
    so a click that landed just after the run completed took it out of the
    finished list and left it waiting for trials that had all run.

    The status is tested in the statement, not in Python. Reading the run and
    then writing it left a window the aggregator could complete the run in,
    and the write went through anyway.
    """
    paused = repo.session.execute(
        sqlalchemy.update(Run)
        .where(Run.id == run_id)
        .where(
            Run.status.in_([
                execution_schemas.RunStatus.PENDING,
                execution_schemas.RunStatus.RUNNING,
            ])
        )
        .values(status=execution_schemas.RunStatus.PAUSED)
    )
    repo.session.commit()
    if not paused.rowcount:
      logger.info(
          "Ignoring pause for run %s, it is not pending or running", run_id
      )

  @inject
  def resume_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Sets a PAUSED run back to RUNNING. Anything else is left alone.

    Only from PAUSED. The worker takes trials from one RUNNING run at a time
    and picks it with a limit of 1, so resuming a PENDING run gave it a second
    RUNNING run to choose from and which one made progress was down to the
    order the rows came back in.

    Conditional for the reason pause is. It is also where a run that was paused
    before it started gets its start time.
    """
    resumed = repo.session.execute(
        sqlalchemy.update(Run)
        .where(Run.id == run_id)
        .where(Run.status == execution_schemas.RunStatus.PAUSED)
        .values(
            status=execution_schemas.RunStatus.RUNNING,
            # A run paused while it was still PENDING has no start time. The
            # other two places that stamp one are promote_next_run, which the
            # worker skips for a run that is already RUNNING, and the trial
            # claim, which stamps only while the run is PENDING. So the run
            # kept a NULL started_at for the rest of its life: Run.duration_ms
            # stayed None, the run detail page and the agent dashboard showed
            # no duration on a finished run, and the BigQuery runs row went out
            # with duration_ms NULL. COALESCE, so a run that had already
            # started keeps the time it actually started.
            started_at=sqlalchemy.func.coalesce(
                Run.started_at, datetime.datetime.now(datetime.timezone.utc)
            ),
        )
    )
    repo.session.commit()
    if not resumed.rowcount:
      logger.info("Ignoring resume for run %s, it is not paused", run_id)

  @inject
  def cancel_run(
      self,
      run_id: int,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> None:
    """Cancels a run that has not finished. A finished run is left alone.

    The precondition used to be documented and not checked. Cancelling an
    already COMPLETED or FAILED run rewrote its terminal status and stamped a
    fresh completed_at over the real one, which is what Run.duration_ms is
    measured from. The UI fires this off a button that stays on screen after
    the run ends, so it was one stray click away.

    Conditional for the reason pause is. Cancel is the worse of the two to get
    wrong, because CANCELLED is terminal and the aggregator will not correct
    it: a run that had in fact completed kept the wrong status for good.
    """
    cancelled = repo.session.execute(
        sqlalchemy.update(Run)
        .where(Run.id == run_id)
        .where(Run.status.not_in(list(_TERMINAL_RUN_STATUSES)))
        .values(
            status=execution_schemas.RunStatus.CANCELLED,
            completed_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    if not cancelled.rowcount:
      repo.session.commit()
      logger.info("Ignoring cancel for run %s, it has finished", run_id)
      return

    # Also cancel this run's PENDING trials. This statement used to be built
    # but never executed, so the workers kept picking them up and a cancelled
    # run went on spending money until every trial had run.
    repo.session.execute(
        sqlalchemy.update(Trial)
        .where(Trial.run_id == run_id)
        .where(Trial.status == execution_schemas.RunStatus.PENDING)
        .values(status=execution_schemas.RunStatus.CANCELLED)
    )
    repo.session.commit()

  @inject
  def archive_run(
      self,
      run_id: int,
      service: ExecutionService = Depends(dependencies.get_execution_service),
  ) -> execution_schemas.RunSchema:
    """Hides a run from the default listing. Nothing is deleted."""
    model = service.archive_run(run_id=run_id)
    return _map_run(model)

  @inject
  def unarchive_run(
      self,
      run_id: int,
      service: ExecutionService = Depends(dependencies.get_execution_service),
  ) -> execution_schemas.RunSchema:
    """Puts an archived run back in the default listing."""
    model = service.unarchive_run(run_id=run_id)
    return _map_run(model)

  def regenerate_suggestions_async(
      self,
      trial_id: int,
      app: Any,
  ) -> None:
    """Regenerates a trial's suggestions in a background thread.

    Returns as soon as the thread starts. The caller polls for the result.
    """

    def _run():
      # Nothing else catches this. A thread that dies takes its traceback to
      # threading's excepthook on stderr, and the poller in
      # evaluation_callbacks just times out after 20 intervals and clears the
      # spinner, so the log line here is the only record of why no suggestions
      # arrived. SuggestionService reads its prompt template in __init__, so
      # the constructor below is one of the things that can raise.
      try:
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

            trial = trial_repo.get_trial(trial_id)
            if not trial:
              return

            # Generate before deleting. suggest_assertions swallows an LLM
            # error into an empty list, so deleting first meant a failed
            # regenerate wiped the suggestions the user already had and left
            # them with nothing.
            # Dedup against the question as it stands now. Regenerate passed
            # nothing, so every assertion the question already held came back
            # as a suggestion on every press. The live row is read, not the
            # snapshot, because an assertion accepted since the run is one the
            # user has already said yes to.
            original_id = trial.example_snapshot.original_example_id
            example = (
                example_repo.get_by_id(original_id) if original_id else None
            )
            existing = [
                assertion_mappers.model_to_schema(a)
                for a in (example.asserts if example else [])
            ]
            suggestions = service.suggest_assertions(
                trial_id, existing_assertions=existing
            )
            if not suggestions:
              logger.warning(
                  "Regenerate produced no suggestions for trial %s, keeping"
                  " the existing ones",
                  trial_id,
              )
              return

            session.execute(
                sqlalchemy.delete(SuggestedAssertion).where(
                    SuggestedAssertion.trial_id == trial_id
                )
            )

            for s in suggestions:
              # Through the shared mapper, which lifts reasoning out of the
              # dump and onto its own column. Building the row by hand here
              # left reasoning inside the params blob, and AssertionSchema
              # then read the NULL column over it, so every regenerated card
              # came back with a blank reasoning line.
              session.add(
                  assertion_mappers.schema_to_suggested_model(s, trial_id)
              )
            session.commit()
      except Exception:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Regenerating suggestions for trial %s failed", trial_id
        )

    threading.Thread(target=_run).start()

  @inject
  def get_unique_suites_from_snapshots(
      self,
      repo: RunRepository = Depends(dependencies.get_run_repository),
  ) -> list[dict[str, Any]]:
    """Lists the suites that have been run, for the suite filter selects."""
    return repo.get_unique_suites_from_snapshots()
