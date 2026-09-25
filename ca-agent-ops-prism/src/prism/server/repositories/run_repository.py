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

"""Repository for managing Runs."""

import datetime
import logging
from typing import Any, Sequence, TypedDict

from prism.common.schemas.execution import RunStatus
from prism.server.models.assertion import AssertionResult
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import TestSuiteSnapshot
import sqlalchemy
from sqlalchemy import orm

logger = logging.getLogger(__name__)


class RunStats(TypedDict):
  run: Run
  accuracy: float | None


# The worker spawns one Python interpreter per concurrent trial, so this is a
# ceiling on child processes on a single Cloud Run instance. The NumberInput
# that feeds it has min=1 max=100, but those are client-side props and a
# hand-built POST with concurrency 50000 reached Run.concurrency unchecked and
# took the instance down.
MAX_CONCURRENCY = 16

# Statuses a run does not come back from. Archiving is only allowed from one of
# these, because the worker's queries all skip archived runs.
_TERMINAL_RUN_STATUSES = (
    RunStatus.COMPLETED,
    RunStatus.FAILED,
    RunStatus.CANCELLED,
)


class RunRepository:
  """Run lifecycle queries, plus the aggregates the dashboards read."""

  def __init__(self, session: orm.Session):
    self.session = session

  def eager_options(self):
    """Common eager loading options for Run details."""

    # example_snapshot and suggested_asserts are here for the run detail page.
    # _map_trial reads example_snapshot.question and Trial.model_validate reads
    # suggested_asserts, so without these the page paid two lazy loads per
    # trial on a three second poll. Loaded the way TrialRepository does it.
    return [
        orm.joinedload(Run.snapshot_suite),
        orm.joinedload(Run.agent),
        orm.selectinload(Run.trials)
        .selectinload(Trial.assertion_results)
        .joinedload(AssertionResult.assertion_snapshot),
        orm.selectinload(Run.trials).joinedload(Trial.example_snapshot),
        orm.selectinload(Run.trials).selectinload(Trial.suggested_asserts),
    ]

  def create(
      self,
      test_suite_snapshot_id: int,
      agent_id: int,
      agent_context_snapshot: dict[str, Any] | None = None,
      generate_suggestions: bool = False,
      concurrency: int = 2,
      example_snapshot_ids: Sequence[int] = (),
  ) -> Run:
    """Creates a new Run and one PENDING trial per example snapshot.

    The trials are committed with the run, not after it. The worker loop reads
    list_active every two seconds, and a run committed on its own is a PENDING
    run with no trials: _aggregate_run_statuses finds nothing left to wait for
    and completes the run before the caller has written its first trial.

    A suite with no examples still produces a trial-less run, which is the case
    the comment in _aggregate_run_statuses describes, and it still completes.

    concurrency is clamped to 1..MAX_CONCURRENCY here, which is the one place
    every writer of a run row passes through.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    # None is what a cleared NumberInput sends.
    requested = 2 if concurrency is None else int(concurrency)
    clamped_concurrency = max(1, min(requested, MAX_CONCURRENCY))
    if clamped_concurrency != requested:
      logger.warning(
          "Requested concurrency %s is out of range, using %s",
          concurrency,
          clamped_concurrency,
      )

    run = Run(
        test_suite_snapshot_id=test_suite_snapshot_id,
        agent_id=agent_id,
        agent_context_snapshot=agent_context_snapshot,
        status=RunStatus.PENDING,
        created_at=now,
        generate_suggestions=generate_suggestions,
        concurrency=clamped_concurrency,
        trials=[
            Trial(
                example_snapshot_id=example_snapshot_id,
                status=RunStatus.PENDING,
                created_at=now,
            )
            for example_snapshot_id in example_snapshot_ids
        ],
    )
    self.session.add(run)
    self.session.commit()
    return run

  def promote_next_run(self) -> Run | None:
    """Promotes the oldest PENDING run to RUNNING if no other run is active.

    A PAUSED run still holds the slot. Without that, pausing a run handed the
    slot to the next one and the two executed side by side.
    """

    active = (
        self.session.execute(
            sqlalchemy.select(Run)
            .where(Run.status.in_([RunStatus.RUNNING, RunStatus.PAUSED]))
            .where(Run.is_archived.is_not(True))
            .limit(1)
        )
        .scalars()
        .first()
    )
    if active:
      return None

    pending = (
        self.session.execute(
            sqlalchemy.select(Run)
            .where(Run.status == RunStatus.PENDING)
            .where(Run.is_archived.is_not(True))
            .order_by(Run.created_at.asc())
            .limit(1)
        )
        .scalars()
        .first()
    )

    if not pending:
      return None

    # Conditional, because cancel arrives on the web request thread and can
    # land in the gap between the select above and this write. The plain
    # assignment put a cancelled run back to RUNNING with every trial already
    # CANCELLED, and the aggregator then read it as done and completed it.
    promoted = self.session.execute(
        sqlalchemy.update(Run)
        .where(Run.id == pending.id)
        .where(Run.status == RunStatus.PENDING)
        .values(
            status=RunStatus.RUNNING,
            started_at=datetime.datetime.now(datetime.timezone.utc),
        )
    )
    self.session.commit()
    if not promoted.rowcount:
      return None

    self.session.refresh(pending)
    return pending

  def get_oldest_running(self) -> Run | None:
    """The RUNNING run the worker should be feeding, or None.

    Oldest first, to agree with promote_next_run. The worker used to read this
    off list_all, which orders newest first, so on the rare occasion two runs
    were RUNNING at once the worker fed the one the queue had not got to yet
    and the older one sat there with its trials unclaimed.

    No eager loads. This runs every two seconds and the caller wants the id.
    """
    stmt = (
        sqlalchemy.select(Run)
        .where(Run.status == RunStatus.RUNNING)
        .where(Run.is_archived.is_not(True))
        .order_by(Run.created_at.asc())
        .limit(1)
    )
    return self.session.scalars(stmt).first()

  def get_by_id(self, run_id: int) -> Run | None:
    """Reads one run with eager_options applied. None if there is no row."""
    stmt = (
        sqlalchemy.select(Run)
        .options(*self.eager_options())
        .where(Run.id == run_id)
    )
    return self.session.scalars(stmt).unique().first()

  def list_active(self) -> Sequence[Run]:
    """Lists all active (non-completed) runs.

    PAUSED counts as active. The aggregator works off this list, so leaving it
    out stranded a run that was paused after its last trial finished: every
    trial done, nothing left to run it, and no way back to COMPLETED.
    """
    stmt = (
        sqlalchemy.select(Run)
        .where(
            Run.status.in_(
                [RunStatus.PENDING, RunStatus.RUNNING, RunStatus.PAUSED]
            )
        )
        .where(Run.is_archived.is_not(True))
    )
    return self.session.scalars(stmt).all()

  def archive(self, run_id: int) -> Run:
    """Hides a finished run from the lists. Raises ValueError otherwise.

    Archiving takes a run out of every query the worker runs, so archiving one
    that was still going abandoned it. Its PENDING trials were never claimed
    again, the aggregator stopped looking at it, and it sat RUNNING with no
    completion time for good. Worse, promote_next_run stopped counting it as
    active and started the next run while this one's workers were still
    calling the agent, so two runs executed at once.
    """
    run = self.get_by_id(run_id)
    if not run:
      raise ValueError(f"Run with id {run_id} not found")
    if run.status not in _TERMINAL_RUN_STATUSES:
      raise ValueError(
          f"Run {run_id} is {run.status.value.lower()}. Cancel it first, then"
          " archive it."
      )
    run.is_archived = True
    self.session.commit()
    self.session.refresh(run)
    return run

  def unarchive(self, run_id: int) -> Run:
    """Puts a run back in the lists. Raises ValueError if there is no row."""
    run = self.get_by_id(run_id)
    if not run:
      raise ValueError(f"Run with id {run_id} not found")
    run.is_archived = False
    self.session.commit()
    self.session.refresh(run)
    return run

  def list_all(
      self,
      limit: int = 50,
      offset: int = 0,
      agent_id: int | None = None,
      original_suite_id: int | None = None,
      status: RunStatus | None = None,
      include_archived: bool = False,
  ) -> Sequence[Run]:
    """Lists runs newest first, filtered by whichever arguments are set."""
    stmt = sqlalchemy.select(Run).options(*self.eager_options())

    if not include_archived:
      stmt = stmt.where(Run.is_archived.is_not(True))

    if agent_id is not None:
      stmt = stmt.where(Run.agent_id == agent_id)
    if original_suite_id is not None:
      stmt = stmt.join(Run.snapshot_suite).where(
          TestSuiteSnapshot.original_suite_id == original_suite_id
      )
    if status is not None:
      stmt = stmt.where(Run.status == status)

    stmt = stmt.order_by(Run.created_at.desc()).limit(limit).offset(offset)
    return self.session.scalars(stmt).all()

  def get_latest_runs_with_stats(
      self, agent_ids: Sequence[int]
  ) -> dict[int, RunStats]:
    """Gets the latest run for multiple agents, including average accuracy."""
    if not agent_ids:
      return {}

    subquery = (
        sqlalchemy.select(
            Run.id,
            sqlalchemy.func.row_number()
            .over(partition_by=Run.agent_id, order_by=Run.created_at.desc())
            .label("rn"),
        )
        .where(
            sqlalchemy.and_(
                Run.agent_id.in_(agent_ids),
                Run.is_archived.is_not(True),
            )
        )
        .subquery()
    )

    latest_run_ids_stmt = sqlalchemy.select(subquery.c.id).where(
        subquery.c.rn == 1
    )

    latest_run_ids = self.session.scalars(latest_run_ids_stmt).all()

    if not latest_run_ids:
      return {}

    # Eager load the trials so Run.accuracy does not fire a query per run.
    runs = (
        self.session.query(Run)
        .options(*self.eager_options())
        .filter(Run.id.in_(latest_run_ids))
        .all()
    )

    # Run.accuracy is the one definition of accuracy. The SQL aggregate that
    # used to live here inner joined AssertionResult, so a FAILED trial had no
    # rows and left the denominator entirely. A run where half the trials
    # crashed reported the accuracy of the half that worked.
    result = {}
    for run in runs:
      result[run.agent_id] = {
          "run": run,
          "accuracy": run.accuracy,
      }

    return result

  def get_agent_dashboard_stats(
      self, agent_id: int, days: int = 30
  ) -> dict[str, Any]:
    """Calculates the KPI metrics and chart series for an agent dashboard."""
    now = datetime.datetime.now(datetime.timezone.utc)
    start_date = now - datetime.timedelta(days=days)
    prev_start_date = start_date - datetime.timedelta(days=days)

    # The trial join fans the rows out, so every run-level aggregate here has
    # to be distinct on Run.id. A plain count gave one row per trial, which
    # made a 50-case run that passed and a 2-case run that failed read as 96%
    # executed instead of 50%. avg_duration is the exception: it is a per-trial
    # average on purpose.
    #
    # active_suites counts the original suite, not the snapshot. Each run gets
    # its own snapshot row, so counting those always returned the run count.
    def _get_period_stats(start, end):
      stmt = (
          sqlalchemy.select(
              sqlalchemy.func.count(sqlalchemy.distinct(Run.id)).label(
                  "total_runs"
              ),
              sqlalchemy.func.count(
                  sqlalchemy.distinct(
                      sqlalchemy.case(
                          (Run.status == RunStatus.COMPLETED, Run.id)
                      )
                  )
              ).label("completed_runs"),
              sqlalchemy.func.avg(Trial.duration_ms).label("avg_duration"),
              sqlalchemy.func.count(
                  sqlalchemy.distinct(TestSuiteSnapshot.original_suite_id)
              ).label("active_suites"),
          )
          .join(Trial, Trial.run_id == Run.id, isouter=True)
          .join(
              TestSuiteSnapshot,
              TestSuiteSnapshot.id == Run.test_suite_snapshot_id,
              isouter=True,
          )
          .where(
              Run.agent_id == agent_id,
              Run.created_at >= start,
              Run.created_at < end,
              Run.is_archived.is_not(True),
          )
      )
      return self.session.execute(stmt).one()

    curr = _get_period_stats(start_date, now)
    prev = _get_period_stats(prev_start_date, start_date)

    exec_rate = (curr.completed_runs or 0) / (curr.total_runs or 1)
    prev_exec_rate = (prev.completed_runs or 0) / (prev.total_runs or 1)
    exec_rate_delta = exec_rate - prev_exec_rate

    avg_duration = float(curr.avg_duration or 0)
    prev_duration = float(prev.avg_duration or 0)
    duration_delta = avg_duration - prev_duration

    # eager_options, because r.accuracy below reads every trial's score, and
    # that walks the assertion results and their snapshots. Loading the trials
    # alone left two queries per trial. The joinedload on the trials was also
    # fanning the rows out under the limit, so this asked for five runs and
    # got as few as one.
    recent_stmt = (
        sqlalchemy.select(Run)
        .options(*self.eager_options())
        .where(
            Run.agent_id == agent_id,
            Run.is_archived.is_not(True),
        )
        .order_by(Run.created_at.desc())
        .limit(5)
    )
    recent_runs = self.session.scalars(recent_stmt).unique().all()
    recent_evals = []
    for r in recent_runs:

      duration_str = "--"
      # From when the worker picked the run up, so a long queue does not read
      # as a slow run. Run.duration_ms measures it the same way.
      if r.completed_at and r.started_at:
        delta = r.completed_at - r.started_at
        total_seconds = int(delta.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        duration_str = f"{minutes}m {seconds}s"
      elif r.status == RunStatus.RUNNING:
        duration_str = "Running..."

      recent_evals.append({
          "id": r.id,
          "score": r.accuracy,
          "suite_name": r.snapshot_suite.name if r.snapshot_suite else "N/A",
          "suite_id": (
              r.snapshot_suite.original_suite_id if r.snapshot_suite else None
          ),
          "status": r.status.value,
          "duration": duration_str,
          "started_at": r.started_at,
      })

    # Daily chart metrics, aggregated in Python off Trial.score so these
    # points match the accuracy on the run page. The SQL version this replaces
    # averaged AssertionResult rows, and a FAILED trial has none, so it left
    # the denominator and the chart read higher than the run it came from.
    window_runs = (
        self.session.query(Run)
        .options(*self.eager_options())
        .filter(
            Run.agent_id == agent_id,
            Run.created_at >= start_date,
            Run.is_archived.is_not(True),
        )
        .all()
    )

    # Series key, and the name each one is drawn under. Grouped on
    # original_suite_id, not the name. The snapshot copies whatever the suite
    # was called at the time, so renaming a suite split its history into two
    # series on the chart. A snapshot with no suite behind it has nothing to
    # group with, so it keeps a series of its own.
    scores_by_day: dict[tuple[str, tuple[str, int]], list[float]] = {}
    durations_by_day: dict[tuple[str, tuple[str, int]], list[int]] = {}
    suite_names: dict[tuple[str, int], tuple[Any, str]] = {}
    for run in window_runs:
      if not run.snapshot_suite or not run.trials:
        continue
      snapshot = run.snapshot_suite
      if snapshot.original_suite_id is not None:
        series = ("suite", snapshot.original_suite_id)
      else:
        series = ("snapshot", snapshot.id)

      # Newest snapshot wins the name, the way
      # get_unique_suites_from_snapshots picks it. id breaks a tie between two
      # snapshots taken in the same clock tick.
      stamp = (snapshot.created_at, snapshot.id)
      if series not in suite_names or stamp > suite_names[series][0]:
        suite_names[series] = (stamp, snapshot.name)

      key = (str(run.created_at.date()), series)
      scores_by_day.setdefault(key, [])
      durations_by_day.setdefault(key, [])
      for trial in run.trials:
        if trial.status == RunStatus.FAILED:
          scores_by_day[key].append(0.0)
        elif trial.status == RunStatus.COMPLETED and trial.score is not None:
          scores_by_day[key].append(trial.score)
        if trial.duration_ms is not None:
          durations_by_day[key].append(trial.duration_ms)

    # The pivot below uses the name as the column, and two suites are allowed
    # to share one. Undisambiguated, whichever came second overwrote the first
    # on every day they both ran.
    display_names: dict[tuple[str, int], str] = {}
    taken: set[str] = set()
    for series in sorted(suite_names):
      name = suite_names[series][1]
      if name in taken:
        name = f"{name} (#{series[1]})"
      taken.add(name)
      display_names[series] = name

    # Pivot to wide format: a row per day, a column per suite name.
    daily_accuracy_map: dict[str, dict[str, Any]] = {}
    daily_duration_map: dict[str, dict[str, Any]] = {}
    all_datasets = set()

    for d_str, series in sorted(scores_by_day):
      if d_str not in daily_accuracy_map:
        daily_accuracy_map[d_str] = {"date": d_str}
        daily_duration_map[d_str] = {"date": d_str}

      suite_name = display_names[series]
      scores = scores_by_day[(d_str, series)]
      durations = durations_by_day[(d_str, series)]
      if scores:
        daily_accuracy_map[d_str][suite_name] = sum(scores) / len(scores)
      if durations:
        daily_duration_map[d_str][suite_name] = int(
            sum(durations) / len(durations)
        )

      all_datasets.add(suite_name)

    daily_accuracy = sorted(
        daily_accuracy_map.values(), key=lambda x: x["date"]
    )
    daily_duration = sorted(
        daily_duration_map.values(), key=lambda x: x["date"]
    )

    return {
        "execution_rate": exec_rate,
        "execution_rate_delta": exec_rate_delta,
        "avg_duration_ms": int(avg_duration),
        "avg_duration_delta": duration_delta,
        "active_suites": curr.active_suites or 0,
        "recent_evals": recent_evals,
        "daily_accuracy": daily_accuracy,
        "daily_duration": daily_duration,
        "suites": sorted(list(all_datasets)),
    }

  def get_run_history_for_agents(
      self, agent_ids: Sequence[int], limit: int = 10
  ) -> dict[int, list[dict[str, Any]]]:
    """Gets execution history for multiple agents.

    Each point is an accuracy and a created_at, and limit is per agent, not
    across all of them.
    """
    if not agent_ids:
      return {}

    subquery = (
        sqlalchemy.select(
            Run.id,
            Run.agent_id,
            Run.created_at,
            sqlalchemy.func.row_number()
            .over(partition_by=Run.agent_id, order_by=Run.created_at.desc())
            .label("rn"),
        )
        .where(
            sqlalchemy.and_(
                Run.agent_id.in_(agent_ids),
                Run.is_archived.is_not(True),
            )
        )
        .subquery()
    )

    recent_runs_stmt = sqlalchemy.select(
        subquery.c.id, subquery.c.agent_id, subquery.c.created_at
    ).where(subquery.c.rn <= limit)

    recent_runs = self.session.execute(recent_runs_stmt).all()

    if not recent_runs:
      return {}

    run_ids = [r.id for r in recent_runs]

    # Same one definition of accuracy as get_latest_runs_with_stats.
    accuracy_map = {
        run.id: run.accuracy
        for run in (
            self.session.query(Run)
            .options(*self.eager_options())
            .filter(Run.id.in_(run_ids))
            .all()
        )
    }

    result = {aid: [] for aid in agent_ids}

    # recent_runs comes back in mixed order. Sparklines read oldest to newest,
    # so sort each agent's list below.
    #
    # A run that has scored nothing keeps its None. Coerced to 0.0, a queued or
    # cancelled run plotted as 0% on the sparkline and turned the trend red,
    # while the "Last eval" text beside it read "--".
    for r in recent_runs:
      result[r.agent_id].append({
          "run_id": r.id,
          "created_at": r.created_at,
          "accuracy": accuracy_map.get(r.id),
      })

    for aid in result:
      result[aid].sort(key=lambda x: x["created_at"])

    return result

  def get_unique_suites_from_snapshots(self) -> list[dict[str, Any]]:
    """Gets unique suites that have been snapshotted for runs.

    The name is the one on the newest snapshot of each suite. This used to be
    max(name), which is the lexicographically greatest name the suite has ever
    had, so renaming "Sales QA" to "Adhoc Checks" left the run filter showing
    "Sales QA" for good.
    """
    results = (
        self.session.query(
            TestSuiteSnapshot.original_suite_id,
            TestSuiteSnapshot.name,
        )
        .filter(TestSuiteSnapshot.original_suite_id.is_not(None))
        .distinct(TestSuiteSnapshot.original_suite_id)
        # DISTINCT ON keeps the first row per suite, so the ordering is what
        # picks the name. id breaks a tie between two snapshots taken in the
        # same clock tick.
        .order_by(
            TestSuiteSnapshot.original_suite_id,
            TestSuiteSnapshot.created_at.desc(),
            TestSuiteSnapshot.id.desc(),
        )
        .all()
    )
    return [
        {"original_suite_id": r.original_suite_id, "name": r.name}
        for r in results
    ]
