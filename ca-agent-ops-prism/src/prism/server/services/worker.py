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
from typing import Any
import uuid

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
from prism.server.services import bigquery_exporter
from prism.server.services import execution_service
from prism.server.services import snapshot_service
from prism.server.services import suggestion_service
import psutil
import sqlalchemy

logger = logging.getLogger(__name__)


def execute_trial(trial_id: int):
  """Standalone function to execute a trial, called in a new process."""
  # A spawned child starts with no handlers, so give it some. This is inside
  # the entry point, not at module scope: the module is imported by the web
  # app too, and force=True there tears down whatever logging the app set up.
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
      handlers=[logging.StreamHandler(sys.stdout)],
      force=True,
  )

  logger.info(
      "Starting execution of trial %s in process %s", trial_id, os.getpid()
  )

  try:
    with db.SessionLocal() as session:
      t_repo = trial_repository.TrialRepository(session)
      trial = t_repo.get_trial(trial_id)
      if not trial:
        logger.error("Trial %s not found in child process", trial_id)
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
      logger.info(
          "Finished execution of trial %s in process %s", trial_id, os.getpid()
      )
  except Exception as e:
    # The reference id is the only thing tying the trial page to this log
    # line, which is where the traceback stays.
    ref = uuid.uuid4().hex[:6]
    logger.exception(
        "Failed to execute trial %s in process %s (ref %s)",
        trial_id,
        os.getpid(),
        ref,
    )
    _fail_trial_during_setup(trial_id, e, ref)


def _fail_trial_during_setup(trial_id: int, error: Exception, ref: str):
  """Records on the trial that the setup above execute_trial raised.

  ExecutionService keeps its own failures on the trial. The trial lookup and
  the two clients built before it did not, so the process just exited. The
  manager then saw a dead PID and called _retry_or_fail, which cleared the
  trial and tried three times more before settling on "Worker process
  crashed". A wrong location or a missing credential fails the same way on
  every retry, so the four attempts bought nothing and the message named none
  of it.

  Through the same sanitiser ExecutionService uses. This used to store
  str(error) and the traceback, and setup is where the credential, location
  and client construction failures happen, so it was the writer whose
  exceptions carried the most: the project, the dataAgents path and the
  service account that was refused, on a page with no authentication in front
  of it.
  """
  with db.SessionLocal() as session:
    trial = session.get(run_models.Trial, trial_id)
    if not trial:
      return
    # The except this runs under covers execute_trial as well as the setup
    # above it, so an exception that got past ExecutionService's own handling
    # arrives here too. SETUP went on unconditionally, which captioned the
    # error card on the trial page with the wrong stage and sent the reader
    # looking at credentials for a trial that had died scoring assertions.
    # RUNNING is the status the claim leaves, so it is the one that means the
    # child never reached execution.
    if trial.status is execution.RunStatus.RUNNING:
      trial.failed_stage = "SETUP"
    else:
      trial.failed_stage = trial.failed_stage or trial.status.value
    trial.status = execution.RunStatus.FAILED
    trial.error_message = (
        f"{execution_service.displayable_error(error)} (ref {ref})"
    )
    trial.error_traceback = None
    trial.completed_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()


# Start times are floats out of psutil and floats back out of the column, so
# the comparison needs a tolerance.
_PID_START_TOLERANCE_S = 0.01


def _process_started_at(pid: int) -> float | None:
  """The start time of a live process, or None if it has already gone."""
  try:
    return psutil.Process(pid).create_time()
  except psutil.NoSuchProcess:
    return None


def _own_child(pid: int):
  """Our multiprocessing handle for a PID, or None if we do not have one.

  active_children() is multiprocessing's own bookkeeping, so this finds the
  children this process spawned and nothing else. Children spawned before a
  restart are gone from it, which is why the callers still have to cope with
  None.
  """
  for child in multiprocessing.active_children():
    if child.pid == pid:
      return child
  return None


def _is_trial_process(trial, proc) -> bool:
  """Whether the live process at the trial's PID is the trial's own worker.

  A PID is not identity on its own. A container restart gives the worker a
  fresh PID namespace and its new children land on the PIDs recorded by the
  trials claimed before the restart, so those trials read as alive and held
  their run's capacity for the full 30 minute timeout. The ppid check does not
  catch that either: it answers whether the process is one of our children,
  not whether it is this trial's child. The recorded start time answers that.

  Trials claimed before the column existed have nothing to compare, so they
  keep the old answer.
  """
  if trial.trial_pid_started_at is None:
    return True
  return (
      abs(proc.create_time() - trial.trial_pid_started_at)
      < _PID_START_TOLERANCE_S
  )


def _in_pid_grace_period(trial) -> bool:
  """Whether a trial with no PID yet is new enough to still be waiting for one.

  The claim and the PID are two commits and the manager loop can see the gap
  between them. Ten seconds is long enough for the spawn.
  """
  if not trial.started_at:
    return False
  cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
      seconds=10
  )
  return trial.started_at > cutoff


# How long a trial can hold its row without finishing before the sweep treats
# it as wedged, and how long the sweep keeps trying before it gives up on the
# process and frees the row anyway.
_STALE_AFTER = datetime.timedelta(minutes=30)
_ABANDON_AFTER = datetime.timedelta(hours=4)


# The statuses a trial holds while a worker is on it. PENDING belongs to
# whoever claims it next, and the rest are terminal.
_IN_FLIGHT = (
    execution.RunStatus.RUNNING,
    execution.RunStatus.EXECUTING,
    execution.RunStatus.EVALUATING,
)


def _lock_if_in_flight(session, trial) -> bool:
  """Locks the trial's row and says whether its worker is still on it.

  The callers read their trials once at the top of a pass, and the children go
  on working while the pass walks the list. A trial that finished in that
  window was written over from here: its answer thrown away on a retry, or a
  0.0 scored into the run's accuracy after it had passed. The re-read takes a
  row lock, so the child's commit either lands before it and is seen, or waits
  behind it.

  Returns with the lock held when it returns True, and the caller commits.
  """
  # OF trials, because the eager loads put the run and the agent on the
  # nullable side of an outer join and Postgres will not lock those.
  session.refresh(trial, with_for_update={"of": run_models.Trial})
  if trial.status in _IN_FLIGHT:
    return True

  logger.info(
      "Trial %s reached %s during the pass, leaving it alone",
      trial.id,
      trial.status,
  )
  # Writes nothing. It is here to let go of the row lock the re-read took.
  session.commit()
  return False


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

  def __init__(self, session_factory: Any = db.SessionLocal):
    if self._initialized:
      return
    # There is no manager-wide trial limit. Each run carries its own
    # concurrency and only one run is active at a time, so _start_new_trials
    # reads the limit off the run.
    self.session_factory = session_factory
    self.stop_event = threading.Event()
    self._thread = None
    self._running = False
    self._initialized = True
    logger.info("Initialized WorkerProcessManager")

  def start(self):
    """Starts the background management thread."""
    if self._running:
      logger.info("WorkerProcessManager is already running")
      return
    self._running = True
    self.stop_event.clear()

    self._thread = threading.Thread(
        target=self._management_loop, name="WorkerManager", daemon=True
    )
    self._thread.start()
    logger.info("Started WorkerProcessManager management thread")

  def stop(self, timeout: float = 10.0):
    """Stops the management thread and waits for it to finish its pass.

    The wait matters to the tests. The loop sleeps two seconds a pass, so
    returning straight after setting the event left a thread that would wake
    up and query a schema the test had already dropped.
    """
    self.stop_event.set()
    self._running = False

    if self._thread and self._thread.is_alive():
      self._thread.join(timeout=timeout)
      if self._thread.is_alive():
        logger.error("WorkerProcessManager thread did not stop in %ss", timeout)
    self._thread = None

    logger.info("Stopped WorkerProcessManager")

  def _management_loop(self):
    """Main loop for monitoring and spawning trial processes."""
    logger.info("Started WorkerProcessManager loop")

    while not self.stop_event.is_set():
      try:
        self._check_active_trials()

        with WorkerProcessManager._aggregator_lock:
          self._aggregate_run_statuses()
          self._recover_stale_trials()

        self._start_new_trials()

        # On the event, not a sleep. stop() joins this thread, and a plain
        # sleep held the join for the rest of the two seconds with the test's
        # schema already dropped underneath it.
        self.stop_event.wait(2.0)
      except Exception:  # pylint: disable=broad-exception-caught
        logger.exception("Error in WorkerProcessManager loop")
        self.stop_event.wait(5)

  def _check_active_trials(self):
    """Checks RUNNING, EXECUTING and EVALUATING trials for process liveness.

    Handles its own exceptions, the way the aggregator and the stale sweep do.
    Letting them reach the management loop threw away the rest of the pass: the
    trials after this one, both of those steps and _start_new_trials. A
    database blip on the first trial's commit stopped anything at all being
    claimed for the five seconds the loop then waits.
    """
    try:
      with self.session_factory() as session:
        t_repo = trial_repository.TrialRepository(session)
        active_trials = t_repo.list_by_status([
            execution.RunStatus.RUNNING,
            execution.RunStatus.EXECUTING,
            execution.RunStatus.EVALUATING,
        ])

        for trial in active_trials:
          if trial.run.status is execution.RunStatus.CANCELLED:
            # Cancel only stops the PENDING trials, so whatever was already in
            # flight ran to the end against the agent and billed for it, then
            # wrote its answer into a run nobody was going to look at.
            if not trial.trial_pid and _in_pid_grace_period(trial):
              continue
            if not self._kill_trial_process(trial):
              continue
            # The kill waits up to five seconds either side, and the child can
            # finish inside that. Writing CANCELLED over a trial that passed
            # orphans its assertion results and takes it out of the run's
            # accuracy, which counts terminal trials only.
            if not _lock_if_in_flight(session, trial):
              continue
            logger.warning(
                "Stopped trial %s because run %s was cancelled",
                trial.id,
                trial.run_id,
            )
            trial.status = execution.RunStatus.CANCELLED
            trial.completed_at = datetime.datetime.now(datetime.timezone.utc)
            session.commit()
            continue

          if not trial.trial_pid:
            if _in_pid_grace_period(trial):
              continue

            # Retry like any other lost process. This used to fail the trial
            # outright, skipping the retry count, so a trial killed in the gap
            # between the claim and the PID was failed for good and scored 0.0
            # against the run. The trial that got further, with a process that
            # died, was retried.
            logger.warning(
                "Trial %s has no PID but is RUNNING. Marking FAILED/RETRY.",
                trial.id,
            )
            self._retry_or_fail(session, trial, "Worker process never started")
            continue

          is_alive = False
          try:
            p = psutil.Process(trial.trial_pid)
            # A dead PID can still resolve as a zombie, so exclude that. The
            # identity check excludes a PID that now belongs to a later
            # process, which is what a restart leaves behind.
            if p.is_running() and p.status() != psutil.STATUS_ZOMBIE:
              is_alive = _is_trial_process(trial, p)
          except psutil.NoSuchProcess:
            is_alive = False
          except psutil.AccessDenied:
            # Cannot read it, so cannot call it dead. Retrying on a process
            # that is still running gives the trial two workers, and this
            # exception used to escape the loop and skip every trial after it.
            is_alive = True

          if not is_alive:
            logger.warning(
                "Trial %s PID %s is dead or defunct. Marking FAILED/RETRY.",
                trial.id,
                trial.trial_pid,
            )
            self._retry_or_fail(session, trial, "Worker process crashed")
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception("Error during liveness check step")

  def _start_new_trials(self):
    """Claims and starts new trials if under concurrency limit."""
    with self.session_factory() as session:
      r_repo = run_repository.RunRepository(session)
      t_repo = trial_repository.TrialRepository(session)

      # Prefer a run already RUNNING, otherwise promote the next PENDING one.
      running_run = r_repo.get_oldest_running()

      if not running_run:
        running_run = r_repo.promote_next_run()

      if not running_run:
        return

      active_run = running_run

      # Capacity is per run, so count only this run's trials.
      current_active_trials = t_repo.list_by_status([
          execution.RunStatus.RUNNING,
          execution.RunStatus.EXECUTING,
          execution.RunStatus.EVALUATING,
      ])
      active_run_trials = [
          t for t in current_active_trials if t.run_id == active_run.id
      ]

      capacity = active_run.concurrency - len(active_run_trials)
      if capacity <= 0:
        return

      for _ in range(capacity):
        trial = t_repo.pick_next_pending_trial(run_id=active_run.id)
        if not trial:
          break

        trial_id = trial.id
        logger.info(
            "Manager claimed trial %s for run %s", trial_id, active_run.id
        )

        try:
          ctx = multiprocessing.get_context("spawn")
          p = ctx.Process(target=execute_trial, args=(trial_id,), daemon=True)
          p.start()
        except Exception:  # pylint: disable=broad-exception-caught
          ref = uuid.uuid4().hex[:6]
          logger.exception(
              "Failed to spawn process for trial %s (ref %s)", trial_id, ref
          )
          # A spawn failure is usually EAGAIN under load, which is the same
          # transient the concurrency limit exists for. Failing the trial here
          # spent none of its retries and scored 0.0 into the run's accuracy.
          self._retry_or_fail(
              session, trial, f"Could not start a worker process (ref {ref})"
          )
          # Out of the loop, not on to the next trial. _retry_or_fail puts the
          # trial back to PENDING and pick_next_pending_trial orders by id, so
          # the next turn of this loop picks the same trial again and a spawn
          # failure that lasts more than a moment spent all three retries in
          # one pass.
          break

        # Recorded with the PID, because the PID alone stops identifying the
        # process as soon as the container restarts.
        started_at = _process_started_at(p.pid)
        if started_at is None:
          # Gone already, so there is no start time to record. Writing the PID
          # without one leaves a row that _is_trial_process has nothing to
          # compare and so calls alive on every later pass, which is the state
          # the column was added to get rid of.
          logger.error(
              "Trial %s: process %s exited before it could be recorded",
              trial_id,
              p.pid,
          )
          self._retry_or_fail(
              session, trial, "The worker process exited immediately"
          )
          break

        try:
          trial.trial_pid = p.pid
          trial.trial_pid_started_at = started_at
          session.commit()
        except Exception:  # pylint: disable=broad-exception-caught
          # The claim committed in pick_next_pending_trial, so the row is
          # already RUNNING with a live process behind it. Handing the trial
          # back while that process runs is the double-execution case, so the
          # process goes first and the trial follows it.
          session.rollback()
          ref = uuid.uuid4().hex[:6]
          logger.exception(
              "Trial %s spawned as PID %s but the row did not commit (ref %s)",
              trial_id,
              p.pid,
              ref,
          )
          p.terminate()
          p.join(timeout=5)
          if p.is_alive():
            # terminate is SIGTERM, and the child can be inside a blocking GDA
            # call that will not take it. The outcome of the join was thrown
            # away, so the trial went back on the queue while its first
            # process was still running against the agent.
            p.kill()
            p.join(timeout=5)
          if p.is_alive():
            # SIGKILL has not landed either, so the process may still be in a
            # call against the agent. Handing the trial back now is the double
            # execution this branch exists to prevent, so it stays claimed and
            # _recover_stale_trials takes it once the process is gone.
            logger.error(
                "Trial %s: process %s survived kill, leaving the trial claimed"
                " (ref %s)",
                trial_id,
                p.pid,
                ref,
            )
            self._record_surviving_worker(trial_id, p.pid, started_at)
            break
          self._retry_or_fail(
              session, trial, f"Could not record the worker process (ref {ref})"
          )
          break

        logger.info("Spawned process %s for trial %s", p.pid, trial_id)

  def _record_surviving_worker(
      self, trial_id: int, pid: int, started_at: float
  ):
    """Writes the PID of a worker the kill above could not account for.

    Leaving the trial claimed only holds if the row says what is holding it.
    The rollback took the PID with it, and the two five second joins before
    this put the trial past _in_pid_grace_period, so the next liveness pass
    read a RUNNING trial with no PID, retried it, and spawned a second worker
    onto a question the first one was still asking the agent. With the PID on
    the row the liveness check sees the process, and the stale sweep frees the
    trial once it has gone.

    In a session of its own, because the one whose commit failed may have lost
    its connection.
    """
    try:
      with self.session_factory() as session:
        session.execute(
            sqlalchemy.update(run_models.Trial)
            .where(run_models.Trial.id == trial_id)
            .where(run_models.Trial.status.in_(_IN_FLIGHT))
            .values(trial_pid=pid, trial_pid_started_at=started_at)
        )
        session.commit()
    except Exception:  # pylint: disable=broad-exception-caught
      # There is nothing else to try. The trial keeps its claim with no PID on
      # it, so the next pass will retry it with the process still up.
      logger.exception(
          "Trial %s: could not record surviving process %s", trial_id, pid
      )

  def _aggregate_run_statuses(self):
    """Checks active runs for completion."""
    try:
      with self.session_factory() as session:
        run_repo = run_repository.RunRepository(session)
        active_runs = run_repo.list_active()

        for run in active_runs:
          # A run with no trials is trivially done, so all_done stays True and
          # it completes here. Skipping it instead left it RUNNING forever,
          # and promote_next_run will not promote past a RUNNING run, so one
          # empty suite jammed every later run behind it.
          all_done = True
          for trial in run.trials:
            if trial.status not in (
                execution.RunStatus.COMPLETED,
                execution.RunStatus.FAILED,
                execution.RunStatus.CANCELLED,
            ):
              all_done = False
              break

          if all_done:
            # Conditional on the status the read above saw. Cancelling a run
            # while the aggregator was walking its trials rewrote CANCELLED
            # back to COMPLETED and stamped a fresh completed_at over the real
            # one, which is what Run.duration_ms is measured from.
            completed = session.execute(
                sqlalchemy.update(run_models.Run)
                .where(run_models.Run.id == run.id)
                .where(
                    run_models.Run.status.in_([
                        execution.RunStatus.PENDING,
                        execution.RunStatus.RUNNING,
                        execution.RunStatus.PAUSED,
                    ])
                )
                .values(
                    status=execution.RunStatus.COMPLETED,
                    completed_at=datetime.datetime.now(datetime.timezone.utc),
                )
            ).rowcount
            session.commit()
            if not completed:
              continue

            logger.info("Run %s completed", run.id)

            if settings.bigquery_export_enabled:
              logger.info(
                  "Triggering BigQuery export for completed Run %s", run.id
              )
              exporter = bigquery_exporter.BigQueryExporter()
              exporter.export_run_async(run.id, self.session_factory)
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception("Error during aggregation step")

  def _recover_stale_trials(self):
    """Resets trials stuck in RUNNING, EXECUTING or EVALUATING for 30 minutes.

    The process is killed before the row is freed. Freeing it first leaves the
    wedged process writing to the same trial while _start_new_trials spawns a
    second one for it, so both write the row and both bill the agent API. A
    trial whose process the kill could not account for keeps its row and is
    looked at again on a later pass, up to _ABANDON_AFTER.
    """
    try:
      # _check_active_trials already fails a trial whose PID is gone. This
      # timeout is for what a PID check cannot see: a process still alive but
      # wedged, or a PID that has since been reused by something else.
      with self.session_factory() as session:
        now = datetime.datetime.now(datetime.timezone.utc)
        stale_cutoff = now - _STALE_AFTER
        abandon_cutoff = now - _ABANDON_AFTER

        stale = session.scalars(
            sqlalchemy.select(run_models.Trial)
            .where(
                run_models.Trial.status.in_([
                    execution.RunStatus.RUNNING,
                    execution.RunStatus.EXECUTING,
                    execution.RunStatus.EVALUATING,
                ])
            )
            .where(run_models.Trial.started_at < stale_cutoff)
        ).all()

        recovered = 0
        for trial in stale:
          if not self._kill_trial_process(trial):
            if trial.started_at < abandon_cutoff:
              # The kill has been failing for four hours, so waiting for a
              # later pass is not going to work. The run cannot aggregate
              # while this trial is in flight and nothing else is allowed to
              # start, so the queue is stopped on a process we have no way to
              # reach. Failed, not retried, because a retry would spawn a
              # second process while whatever is holding this one is still up.
              self._abandon_trial(session, trial)
              recovered += 1
              continue
            # The process is still up, or we could not prove it is not.
            # Freeing the row now gets a second worker spawned onto a trial
            # the first one is still writing to, so leave it for a later pass.
            logger.warning(
                "Trial %s is stale but its process is not gone, leaving it"
                " claimed for now",
                trial.id,
            )
            continue
          # Through _retry_or_fail, so the attempt is counted and committed on
          # its own. Resetting straight to PENDING spent no retry, so a trial
          # that wedges the same way every time came back for ever: its run
          # never reached a terminal status, and promote_next_run will not
          # promote past a run that is still going, so everything queued
          # behind it waited too.
          self._retry_or_fail(
              session,
              trial,
              "The trial made no progress for"
              f" {int(_STALE_AFTER.total_seconds() // 60)} minutes.",
          )
          recovered += 1

        if recovered:
          logger.warning("Recovered %s stale trials via timeout", recovered)
    except Exception:  # pylint: disable=broad-exception-caught
      logger.exception("Error during stale trial recovery step")

  def _kill_trial_process(self, trial) -> bool:
    """Kills a trial's subprocess. True only if the process is provably gone.

    The caller frees the trial row on the strength of this answer, and a row
    freed while its process is still writing to it gets a second worker
    spawned for the same trial. Both then write the row and both bill the
    agent API. So every path that cannot show the process is gone answers
    False and the trial waits for a later pass.
    """
    if not trial.trial_pid:
      return True

    try:
      p = psutil.Process(trial.trial_pid)
    except psutil.NoSuchProcess:
      return True
    except psutil.AccessDenied:
      # Something we are not allowed to read is on that PID, which is enough
      # to say it is not our child, but not enough to say ours has gone. This
      # used to escape the recovery pass entirely and the exception handler
      # around it skipped every remaining stale trial.
      logger.warning(
          "Trial %s PID %s cannot be read, so it is neither killed nor freed",
          trial.id,
          trial.trial_pid,
      )
      return False

    if trial.trial_pid_started_at is None:
      # Nothing to compare, so the ppid is the only identity this trial has,
      # and it cannot tell a recycled PID from our own reparented child. Half
      # an hour is long enough for either, so the row stays claimed.
      try:
        parent = p.ppid()
      except psutil.NoSuchProcess:
        return True
      except psutil.AccessDenied:
        parent = None
      if parent != os.getpid():
        logger.warning(
            "Trial %s PID %s has another parent and no recorded start time,"
            " so it is neither killed nor freed",
            trial.id,
            trial.trial_pid,
        )
        return False
    elif not _is_trial_process(trial, p):
      logger.warning(
          "Trial %s PID %s was taken over by a later process. The trial's own"
          " process is gone, so there is nothing to kill.",
          trial.id,
          trial.trial_pid,
      )
      return True

    child = _own_child(trial.trial_pid)
    survived = False
    try:
      p.kill()
      if child is None:
        p.wait(timeout=5)
      else:
        # The handle does the waiting when the child is one of ours. psutil's
        # wait() calls os.waitpid itself, which reaps the child behind
        # multiprocessing's back: Popen.poll() then gets ChildProcessError, the
        # handle is never discarded from multiprocessing's _children, and the
        # Finalize that closes the two parent pipe descriptors never runs. A
        # long lived server leaked both on every trial it killed.
        child.join(timeout=5)
        survived = child.is_alive()
    except psutil.NoSuchProcess:
      return True
    except psutil.AccessDenied:
      logger.error(
          "Not allowed to kill process %s for trial %s",
          trial.trial_pid,
          trial.id,
      )
      return False
    except psutil.TimeoutExpired:
      survived = True

    if survived:
      logger.error(
          "Trial %s process %s survived kill", trial.id, trial.trial_pid
      )
      return False

    logger.warning(
        "Killed wedged process %s for trial %s", trial.trial_pid, trial.id
    )
    return True

  def _retry_or_fail(self, session, trial, message: str):
    """Decides whether to retry or fail a trial.

    A trial that finished during the pass is left where it is. See
    _lock_if_in_flight.
    """
    if not _lock_if_in_flight(session, trial):
      return

    if trial.retry_count < trial.max_retries:
      logger.warning(
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
      trial.trial_pid_started_at = None
      trial.output_text = None
      trial.error_message = None
      trial.error_traceback = None
      trial.failed_stage = None
      trial.trace_results = None
      trial.assertion_results = []
      # Both of these outlived the reset. The trial page captions the error
      # card with failed_stage, so a retry showed the stage the first attempt
      # died in, and the suggestions panel offered assertions written against
      # an answer that had been thrown away.
      trial.suggested_asserts = []
    else:
      logger.error(
          "Trial %s failed after %s retries", trial.id, trial.max_retries
      )
      trial.status = execution.RunStatus.FAILED
      trial.error_message = f"{message} (After {trial.max_retries} retries)"
      # Stamped here as well as in ExecutionService, because a trial the
      # manager fails never gets back to the child that would have stamped it.
      # Without it the trial row has a start and no end, and every duration
      # the run reports skips it.
      trial.completed_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()

  def _abandon_trial(self, session, trial):
    """Fails a trial whose process we have given up on reaching.

    Terminal, with no retry. See the caller in _recover_stale_trials.
    """
    if not _lock_if_in_flight(session, trial):
      return

    logger.error(
        "Trial %s has been stale for over %s hours and its process %s cannot"
        " be killed. Failing it so the run can finish.",
        trial.id,
        int(_ABANDON_AFTER.total_seconds() // 3600),
        trial.trial_pid,
    )
    trial.status = execution.RunStatus.FAILED
    trial.error_message = (
        "The trial made no progress and its worker process could not be"
        " stopped."
    )
    trial.completed_at = datetime.datetime.now(datetime.timezone.utc)
    session.commit()
