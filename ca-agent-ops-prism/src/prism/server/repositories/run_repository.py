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
from typing import Any, Sequence, TypedDict

from prism.common.schemas.execution import RunStatus
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.run import Run
from prism.server.models.run import Trial
from prism.server.models.snapshot import TestSuiteSnapshot
import sqlalchemy
from sqlalchemy import orm


class RunStats(TypedDict):
  run: Run
  accuracy: float | None


class RunRepository:
  """Repository for Run entities."""

  def __init__(self, session: orm.Session):
    self.session = session

  def eager_options(self):
    """Common eager loading options for Run details."""

    return [
        orm.joinedload(Run.snapshot_suite),
        orm.joinedload(Run.agent),
        orm.selectinload(Run.trials)
        .selectinload(Trial.assertion_results)
        .joinedload(AssertionResult.assertion_snapshot),
    ]

  def create(
      self,
      test_suite_snapshot_id: int,
      agent_id: int,
      agent_context_snapshot: dict[str, Any] | None = None,
  ) -> Run:
    """Creates a new Run."""
    run = Run(
        test_suite_snapshot_id=test_suite_snapshot_id,
        agent_id=agent_id,
        agent_context_snapshot=agent_context_snapshot,
        status=RunStatus.PENDING,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    self.session.add(run)
    self.session.commit()
    return run

  def get_by_id(self, run_id: int) -> Run | None:
    """Gets a Run by ID."""
    stmt = (
        sqlalchemy.select(Run)
        .options(*self.eager_options())
        .where(Run.id == run_id)
    )
    return self.session.scalars(stmt).unique().first()

  def list_active(self) -> Sequence[Run]:
    """Lists all active (non-completed) runs."""
    stmt = sqlalchemy.select(Run).where(
        Run.status.in_([RunStatus.PENDING, RunStatus.RUNNING])
    )
    return self.session.scalars(stmt).all()

  def get_latest_for_agent(self, agent_id: int) -> Run | None:
    """Gets the latest run for an agent."""
    stmt = (
        sqlalchemy.select(Run)
        .where(Run.agent_id == agent_id)
        .order_by(Run.created_at.desc())
        .limit(1)
    )
    return self.session.scalars(stmt).first()

  def list_all(
      self,
      limit: int = 50,
      offset: int = 0,
      agent_id: int | None = None,
      original_suite_id: int | None = None,
      status: RunStatus | None = None,
  ) -> Sequence[Run]:
    """Lists recent runs with optional filtering."""
    stmt = sqlalchemy.select(Run).options(*self.eager_options())

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

  def count(self) -> int:
    """Counts total number of runs."""
    stmt = sqlalchemy.select(sqlalchemy.func.count()).select_from(Run)
    return self.session.scalar(stmt) or 0

  def get_latest_runs_with_stats(
      self, agent_ids: Sequence[int]
  ) -> dict[int, RunStats]:
    """Gets the latest run for multiple agents, including average accuracy.

    Args:
      agent_ids: List of agent IDs to fetch runs for.

    Returns:
      A dictionary mapping agent_id to a dict containing "run" (Run object)
      and "accuracy" (float or None).
    """
    if not agent_ids:
      return {}

    # Rank runs by created_at desc for each agent
    subquery = (
        sqlalchemy.select(
            Run.id,
            sqlalchemy.func.row_number()
            .over(partition_by=Run.agent_id, order_by=Run.created_at.desc())
            .label("rn"),
        )
        .where(Run.agent_id.in_(agent_ids))
        .subquery()
    )

    # Filter for the latest run (rn=1)
    latest_run_ids_stmt = sqlalchemy.select(subquery.c.id).where(
        subquery.c.rn == 1
    )

    # Let's do it cleanly:
    # 1. Get latest Run IDs
    latest_run_ids = self.session.scalars(latest_run_ids_stmt).all()

    if not latest_run_ids:
      return {}

    # 2. Fetch Runs eagerly loading snapshot
    runs = (
        self.session.query(Run)
        .options(orm.joinedload(Run.snapshot_suite))
        .filter(Run.id.in_(latest_run_ids))
        .all()
    )

    # 3. Calculate Accuracy for these runs (Average of Trial Averages)
    # First, get average score per trial
    trial_scores_subquery = (
        sqlalchemy.select(
            Trial.run_id,
            Trial.id.label("trial_id"),
            sqlalchemy.func.avg(AssertionResult.score).label("trial_score"),
        )
        .join(AssertionResult, Trial.id == AssertionResult.trial_id)
        .join(
            AssertionSnapshot,
            AssertionResult.assertion_snapshot_id == AssertionSnapshot.id,
        )
        .where(AssertionSnapshot.weight > 0)
        .where(Trial.run_id.in_(latest_run_ids))
        .group_by(Trial.run_id, Trial.id)
        .subquery()
    )

    # Then, average those trial scores per run
    accuracy_stmt = sqlalchemy.select(
        trial_scores_subquery.c.run_id,
        sqlalchemy.func.avg(trial_scores_subquery.c.trial_score),
    ).group_by(trial_scores_subquery.c.run_id)
    accuracy_map = dict(self.session.execute(accuracy_stmt).all())

    result = {}
    for run in runs:
      result[run.agent_id] = {
          "run": run,
          "accuracy": accuracy_map.get(run.id),
      }

    return result

  def get_agent_dashboard_stats(
      self, agent_id: int, days: int = 30
  ) -> dict[str, Any]:
    """Calculates dashboard statistics for an agent.

    Args:
      agent_id: The ID of the agent.
      days: Number of days to look back.

    Returns:
      A dictionary containing KPI metrics and charts data.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    start_date = now - datetime.timedelta(days=days)
    prev_start_date = start_date - datetime.timedelta(days=days)

    # Helper to get stats for a period
    def _get_period_stats(start, end):
      stmt = (
          sqlalchemy.select(
              sqlalchemy.func.count(Run.id).label("total_runs"),
              sqlalchemy.func.sum(
                  sqlalchemy.case(
                      (Run.status == RunStatus.COMPLETED, 1), else_=0
                  )
              ).label("completed_runs"),
              sqlalchemy.func.avg(Trial.duration_ms).label("avg_duration"),
              sqlalchemy.func.count(
                  sqlalchemy.distinct(Run.test_suite_snapshot_id)
              ).label("active_suites"),
              # Approximate total test cases (trials)
              sqlalchemy.func.count(Trial.id).label("total_trials"),
          )
          .join(Trial, Trial.run_id == Run.id, isouter=True)
          .where(
              Run.agent_id == agent_id,
              Run.created_at >= start,
              Run.created_at < end,
          )
      )
      return self.session.execute(stmt).one()

    curr = _get_period_stats(start_date, now)
    prev = _get_period_stats(prev_start_date, start_date)

    # 1. Execution Rate
    exec_rate = (curr.completed_runs or 0) / (curr.total_runs or 1)
    prev_exec_rate = (prev.completed_runs or 0) / (prev.total_runs or 1)
    exec_rate_delta = exec_rate - prev_exec_rate

    # 2. Duration
    avg_duration = float(curr.avg_duration or 0)
    prev_duration = float(prev.avg_duration or 0)
    duration_delta = avg_duration - prev_duration

    # 3. Recent Evaluations (Top 5)
    recent_stmt = (
        sqlalchemy.select(Run)
        .options(
            orm.joinedload(Run.trials),
            orm.joinedload(Run.snapshot_suite),
        )
        .where(Run.agent_id == agent_id)
        .order_by(Run.created_at.desc())
        .limit(5)
    )
    recent_runs = self.session.scalars(recent_stmt).unique().all()
    recent_evals = []
    for r in recent_runs:
      # Duration Logic
      duration_str = "--"
      if r.completed_at and r.created_at:
        delta = r.completed_at - r.created_at
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
          "created_at": r.created_at,
      })

    # 4. Daily Metrics (for Charts)
    # Average of Trial Averages

    # First, get trial-level stats
    trial_stats_subquery = (
        sqlalchemy.select(
            sqlalchemy.func.date(Run.created_at).label("date"),
            Run.id.label("run_id"),
            Trial.id.label("trial_id"),
            TestSuiteSnapshot.name.label("suite_name"),
            sqlalchemy.func.avg(AssertionResult.score).label("trial_score"),
            sqlalchemy.func.max(Trial.duration_ms).label("trial_duration"),
        )
        .join(Trial, Trial.run_id == Run.id)
        .join(
            AssertionResult, Trial.id == AssertionResult.trial_id, isouter=True
        )
        .join(
            AssertionSnapshot,
            AssertionResult.assertion_snapshot_id == AssertionSnapshot.id,
            isouter=True,
        )
        .join(
            TestSuiteSnapshot,
            Run.test_suite_snapshot_id == TestSuiteSnapshot.id,
        )
        .where(
            Run.agent_id == agent_id,
            Run.created_at >= start_date,
            sqlalchemy.or_(
                AssertionSnapshot.weight > 0, AssertionSnapshot.id.is_(None)
            ),
        )
        .group_by(
            sqlalchemy.func.date(Run.created_at),
            Run.id,
            Trial.id,
            TestSuiteSnapshot.name,
        )
        .subquery()
    )

    # Then, aggregate to daily/suite level
    chart_stmt = (
        sqlalchemy.select(
            trial_stats_subquery.c.date,
            trial_stats_subquery.c.suite_name,
            sqlalchemy.func.avg(trial_stats_subquery.c.trial_score).label(
                "daily_score"
            ),
            sqlalchemy.func.avg(trial_stats_subquery.c.trial_duration).label(
                "daily_duration"
            ),
        )
        .group_by(
            trial_stats_subquery.c.date, trial_stats_subquery.c.suite_name
        )
        .order_by(trial_stats_subquery.c.date)
    )
    daily_results = self.session.execute(chart_stmt).all()

    # pivot to wide format
    daily_accuracy_map: dict[str, dict[str, Any]] = {}
    daily_duration_map: dict[str, dict[str, Any]] = {}
    all_datasets = set()

    for row in daily_results:
      d_str = str(row.date)
      if d_str not in daily_accuracy_map:
        daily_accuracy_map[d_str] = {"date": d_str}
        daily_duration_map[d_str] = {"date": d_str}

      if row.daily_score is not None:
        daily_accuracy_map[d_str][row.suite_name] = row.daily_score
      if row.daily_duration is not None:
        daily_duration_map[d_str][row.suite_name] = int(row.daily_duration)

      all_datasets.add(row.suite_name)

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

    Args:
      agent_ids: List of agent IDs.
      limit: Max number of history points per agent.

    Returns:
      Dict mapping agent_id to list of history points (accuracy, created_at).
    """
    if not agent_ids:
      return {}

    # 1. Fetch recent runs for these agents
    # We want top N per agent. Window functions again.
    subquery = (
        sqlalchemy.select(
            Run.id,
            Run.agent_id,
            Run.created_at,
            sqlalchemy.func.row_number()
            .over(partition_by=Run.agent_id, order_by=Run.created_at.desc())
            .label("rn"),
        )
        .where(Run.agent_id.in_(agent_ids))
        .subquery()
    )

    recent_runs_stmt = sqlalchemy.select(
        subquery.c.id, subquery.c.agent_id, subquery.c.created_at
    ).where(subquery.c.rn <= limit)

    recent_runs = self.session.execute(recent_runs_stmt).all()

    if not recent_runs:
      return {}

    run_ids = [r.id for r in recent_runs]

    # 2. Calculate accuracy for these runs (Average of Trial Averages)
    trial_scores_subquery = (
        sqlalchemy.select(
            Trial.run_id,
            sqlalchemy.func.avg(AssertionResult.score).label("trial_score"),
        )
        .join(AssertionResult, Trial.id == AssertionResult.trial_id)
        .join(
            AssertionSnapshot,
            AssertionResult.assertion_snapshot_id == AssertionSnapshot.id,
        )
        .where(AssertionSnapshot.weight > 0)
        .where(Trial.run_id.in_(run_ids))
        .group_by(Trial.run_id, Trial.id)
        .subquery()
    )

    accuracy_stmt = sqlalchemy.select(
        trial_scores_subquery.c.run_id,
        sqlalchemy.func.avg(trial_scores_subquery.c.trial_score),
    ).group_by(trial_scores_subquery.c.run_id)
    accuracy_map = dict(self.session.execute(accuracy_stmt).all())

    # 3. Assemble result
    result = {aid: [] for aid in agent_ids}

    # Process in reverse temporal order (oldest first) if we want a timeline?
    # Usually sparklines want left-to-right (old -> new).
    # recent_runs is mixed order, let's sort locally.

    # Map run_id -> details
    run_details = {}
    for r in recent_runs:
      run_details[r.id] = {
          "run_id": r.id,
          "agent_id": r.agent_id,
          "created_at": r.created_at,
          "accuracy": accuracy_map.get(
              r.id, 0.0
          ),  # Default to 0 if no score? or None?
      }

    for details in run_details.values():
      # Only include if accuracy is not None (i.e. has trials)?
      # Or include 0? Let's include what we have.
      # If score is None (no trials), maybe average is None.
      score = details["accuracy"]
      if score is None:
        score = 0.0

      result[details["agent_id"]].append({
          "run_id": details["run_id"],
          "created_at": details["created_at"],
          "accuracy": score,
      })

    # Sort each agent's list by date ascending
    for aid in result:
      result[aid].sort(key=lambda x: x["created_at"])

    return result

  def get_unique_suites_from_snapshots(self) -> list[dict[str, Any]]:
    """Gets unique suites that have been snapshotted for runs."""
    results = (
        self.session.query(
            TestSuiteSnapshot.original_suite_id,
            sqlalchemy.func.max(TestSuiteSnapshot.name).label("name"),
        )
        .group_by(TestSuiteSnapshot.original_suite_id)
        .all()
    )
    return [
        {"original_suite_id": r.original_suite_id, "name": r.name}
        for r in results
        if r.original_suite_id is not None
    ]
