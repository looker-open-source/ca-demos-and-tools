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

"""Background worker service for asynchronous evaluation execution."""

import datetime
import logging
import multiprocessing
import os
import sys
import threading
import time
from typing import Any

from prism.common.schemas import execution
from prism.server import db
from prism.server.clients import gemini_data_analytics_client
from prism.server.clients import gen_ai_client
from prism.server.config import settings
from prism.server.models import run as run_models
from prism.server.repositories import example_repository
from prism.server.repositories import run_repository
from prism.server.repositories import suite_repository
from prism.server.repositories import trial_repository
from prism.server.services import execution_service
from prism.server.services import snapshot_service
from prism.server.services import suggestion_service
import psutil
import sqlalchemy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)


def execute_trial(trial_id: int):
  """Standalone function to execute a trial, called in a new process."""
  logging.info(
      "Starting execution of trial %s in process %s", trial_id, os.getpid()
  )

  try:
    with db.SessionLocal() as session:
      t_repo = trial_repository.TrialRepository(session)
      trial = t_repo.get_trial(trial_id)
      if not trial:
        logging.error("Trial %s not found in child process", trial_id)
        return

      agent = trial.run.agent
      suite_repo = suite_repository.SuiteRepository(session)
      example_repo = example_repository.ExampleRepository(session)
      snap_service = snapshot_service.SnapshotService(
          session, suite_repo, example_repo
      )

      parent = f"projects/{agent.project_id}/locations/{agent.location}"
      gda_client = gemini_data_analytics_client.GeminiDataAnalyticsClient(
          parent
      )

      gen_ai_client_inst = gen_ai_client.GenAIClient(
          project=settings.gcp_genai_project,
          location=settings.gcp_genai_location,
      )
      sug_service = suggestion_service.SuggestionService(
          gen_ai_client_inst, t_repo, example_repo
      )

      exec_service = execution_service.ExecutionService(
          session=session,
          snapshot_service=snap_service,
          client=gda_client,
          suggestion_service=sug_service,
      )

      exec_service.execute_trial(trial.id)
      logging.info(
          "Finished execution of trial %s in process %s", trial_id, os.getpid()
      )
  except Exception as e:
    logging.exception(
        "Failed to execute trial %s in process %s: %s", trial_id, os.getpid(), e
    )


class WorkerProcessManager:
  """Manages a pool of processes for executing evaluation trials."""

  _instance = None
  _lock = threading.Lock()
  _aggregator_lock = threading.Lock()

  def __new__(cls, *args, **kwargs):
    if not cls._instance:
      with cls._lock:
        if not cls._instance:
          cls._instance = super(WorkerProcessManager, cls).__new__(cls)
          cls._instance._initialized = False
    return cls._instance

  def __init__(
      self,
      max_concurrent_trials: int = 2,
      session_factory: Any = db.SessionLocal,
  ):
    if self._initialized:
      return
    self.max_concurrent_trials = max_concurrent_trials
    self.session_factory = session_factory
    self.stop_event = threading.Event()
    self._thread = None
    self._running = False
    self._initialized = True
    logging.info(
        "Initialized WorkerProcessManager (Limit: %s)", max_concurrent_trials
    )

  def start(self):
    """Starts the background management thread."""
    if self._running:
      logging.info("WorkerProcessManager is already running")
      return
    self._running = True
    self.stop_event.clear()

    self._thread = threading.Thread(
        target=self._management_loop, name="WorkerManager", daemon=True
    )
    self._thread.start()
    logging.info("Started WorkerProcessManager management thread")

  def stop(self):
    """Signals the management thread to stop."""
    self.stop_event.set()
    self._running = False
    logging.info("Signalled WorkerProcessManager to stop")

  def _management_loop(self):
    """Main loop for monitoring and spawning trial processes."""
    logging.info("Started WorkerProcessManager loop")

    while not self.stop_event.is_set():
      try:
        # Step 1: Monitor active trials (Cleanup dead processes)
        self._check_active_trials()

        # Step 2: Aggregation & Recovery (Global maintenance)
        with WorkerProcessManager._aggregator_lock:
          self._aggregate_run_statuses()
          self._recover_stale_trials()

        # Step 3: Spawn new trials if capacity exists
        self._start_new_trials()

        time.sleep(2.0)
      except Exception:  # pylint: disable=broad-exception-caught
        logging.exception("Error in WorkerProcessManager loop")
        time.sleep(5)

  def _check_active_trials(self):
    """Checks RUNNING trials for process liveness."""
    with self.session_factory() as session:
      t_repo = trial_repository.TrialRepository(session)
      active_trials = t_repo.list_by_status([
          execution.RunStatus.RUNNING,
          execution.RunStatus.EXECUTING,
          execution.RunStatus.EVALUATING,
      ])

      for trial in active_trials:
        # 1. Check PID existence
        if not trial.trial_pid:
          # If it just started, ignore for 10 seconds (grace period for DB write)
          if trial.started_at:
            grace_period = datetime.datetime.now(
                datetime.timezone.utc
            ) - datetime.timedelta(seconds=10)
            if trial.started_at > grace_period:
              continue

          logging.warning(
              "Trial %s has no PID but is RUNNING. Marking FAILED.",
              trial.id,
          )
          self._fail_trial(trial, "Internal Error: Process lost (No PID)")
          continue

        # 2. Check PID Liveness
        is_alive = False
        try:
          p = psutil.Process(trial.trial_pid)
          # Ensure it's not a zombie and it IS a python process (rudimentary check)
          if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
            is_alive = True
        except psutil.NoSuchProcess:
          is_alive = False

        if not is_alive:
          logging.warning(
              "Trial %s PID %s is dead or defunct. Marking FAILED/RETRY.",
              trial.id,
              trial.trial_pid,
          )
          self._retry_or_fail(session, trial, "Worker process crashed")
          continue

  def _start_new_trials(self):
    """Claims and starts new trials if under concurrency limit."""
    with self.session_factory() as session:
      t_repo = trial_repository.TrialRepository(session)

      # 1. Check current capacity
      active_count = len(
          t_repo.list_by_status([
              execution.RunStatus.RUNNING,
              execution.RunStatus.EXECUTING,
              execution.RunStatus.EVALUATING,
          ])
      )

      capacity = self.max_concurrent_trials - active_count
      if capacity <= 0:
        return

      # 2. Claim pending trials
      for _ in range(capacity):
        trial = t_repo.pick_next_pending_trial()
        if not trial:
          break

        trial_id = trial.id
        logging.info("Manager claimed trial %s", trial_id)

        # 3. Spawn (Outside session to avoid leaks/locks)
        try:
          ctx = multiprocessing.get_context("spawn")
          p = ctx.Process(target=execute_trial, args=(trial_id,), daemon=True)
          p.start()

          # Update PID immediately
          trial.trial_pid = p.pid
          session.commit()
          logging.info("Spawned process %s for trial %s", p.pid, trial_id)
        except Exception as e:
          logging.error("Failed to spawn process for trial %s: %s", trial_id, e)
          trial.status = execution.RunStatus.FAILED
          trial.error_message = f"Process spawn failed: {str(e)}"
          session.commit()

  def _aggregate_run_statuses(self):
    """Checks RUNNING runs for completion."""
    try:
      with self.session_factory() as session:
        run_repo = run_repository.RunRepository(session)
        active_runs = run_repo.list_active()

        for run in active_runs:
          all_done = True
          for trial in run.trials:
            if trial.status not in (
                execution.RunStatus.COMPLETED,
                execution.RunStatus.FAILED,
                execution.RunStatus.CANCELLED,
            ):
              all_done = False
              break

          if all_done and run.trials:
            logging.info("Run %s completed", run.id)
            run.status = execution.RunStatus.COMPLETED
            run.completed_at = datetime.datetime.now(datetime.timezone.utc)
            session.commit()
    except Exception:  # pylint: disable=broad-exception-caught
      logging.exception("Error during aggregation step")

  def _recover_stale_trials(self):
    """Resets trials stuck in RUNNING for more than 30 minutes to PENDING."""
    try:
      # Note: with process management, we usually rely on PID liveness.
      # Stale recovery is a fallback for systemic issues.
      with self.session_factory() as session:
        stale_cutoff = datetime.datetime.now(
            datetime.timezone.utc
        ) - datetime.timedelta(minutes=30)

        stale_stmt = (
            sqlalchemy.update(run_models.Trial)
            .where(
                run_models.Trial.status.in_([
                    execution.RunStatus.RUNNING,
                    execution.RunStatus.EXECUTING,
                    execution.RunStatus.EVALUATING,
                ])
            )
            .where(run_models.Trial.started_at < stale_cutoff)
            .values(
                status=execution.RunStatus.PENDING,
                started_at=None,
                trial_pid=None,
            )
        )
        result = session.execute(stale_stmt)
        if result.rowcount > 0:
          logging.warning(
              "Recovered %s stale trials via timeout", result.rowcount
          )
        session.commit()
    except Exception:  # pylint: disable=broad-exception-caught
      logging.exception("Error during stale trial recovery step")

  def _fail_trial(self, trial, message: str):
    """Helper to mark a trial as failed in a new session."""
    with self.session_factory() as session:
      # Re-fetch to avoid session issues
      t = session.get(run_models.Trial, trial.id)
      if t:
        t.status = execution.RunStatus.FAILED
        t.error_message = message
        session.commit()

  def _retry_or_fail(self, session, trial, message: str):
    """Decides whether to retry or fail a trial."""
    if trial.retry_count < trial.max_retries:
      logging.warning(
          "Retrying trial %s (%s/%s)",
          trial.id,
          trial.retry_count + 1,
          trial.max_retries,
      )
      trial.status = execution.RunStatus.PENDING
      trial.retry_count += 1
      trial.started_at = None
      trial.completed_at = None
      trial.trial_pid = None
      trial.output_text = None
      trial.error_message = None
      trial.error_traceback = None
      trial.trace_results = None
      trial.assertion_results = []
    else:
      logging.error(
          "Trial %s failed after %s retries", trial.id, trial.max_retries
      )
      trial.status = execution.RunStatus.FAILED
      trial.error_message = f"{message} (After {trial.max_retries} retries)"
    session.commit()
