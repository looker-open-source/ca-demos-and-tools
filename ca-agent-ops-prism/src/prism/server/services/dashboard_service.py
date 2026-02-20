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

"""Service for dashboard statistics."""

import datetime
from prism.common.schemas.dashboard import AgentStatusSchema
from prism.common.schemas.dashboard import DailyAccuracySchema
from prism.common.schemas.dashboard import DailyRunCountSchema
from prism.common.schemas.dashboard import DashboardStats
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.models.agent import Agent
from prism.server.models.run import Run
from prism.server.repositories.run_repository import RunRepository
import sqlalchemy
from sqlalchemy import orm


class DashboardService:
  """Service for dashboard statistics."""

  def __init__(self, session: orm.Session):
    self.session = session
    self.run_repo = RunRepository(session)

  def get_dashboard_stats(self) -> DashboardStats:
    """Calculates and returns dashboard statistics."""
    now = datetime.datetime.now(datetime.timezone.utc)
    seven_days_ago = now - datetime.timedelta(days=7)
    twenty_four_hours_ago = now - datetime.timedelta(hours=24)
    thirty_days_ago = now - datetime.timedelta(days=30)

    # 1. Total Agents
    total_agents = self.session.query(Agent).count()

    # 2. Active Agents (Last 7 Days)
    active_agents_7d = (
        self.session.query(
            sqlalchemy.func.count(sqlalchemy.distinct(Run.agent_id))
        )
        .filter(
            Run.started_at >= seven_days_ago,
            Run.is_archived.is_not(True),
        )
        .scalar()
        or 0
    )

    # 3. Active Agents (Last 24 Hours)
    active_agents_24h = (
        self.session.query(
            sqlalchemy.func.count(sqlalchemy.distinct(Run.agent_id))
        )
        .filter(
            Run.started_at >= twenty_four_hours_ago,
            Run.is_archived.is_not(True),
        )
        .scalar()
        or 0
    )

    # 4. Total Runs (Last 7 Days)
    total_runs_7d = (
        self.session.query(Run)
        .filter(
            Run.started_at >= seven_days_ago,
            Run.is_archived.is_not(True),
        )
        .count()
    )

    # 5. Average Accuracy (Last 7 Days)
    # Consider only COMPLETED runs to avoid skewing with 0s
    runs_7d = (
        self.session.query(Run)
        .options(*self.run_repo.eager_options())
        .filter(
            Run.started_at >= seven_days_ago,
            Run.status == RunStatus.COMPLETED,
            not Run.is_archived,
        )
        .all()
    )

    accuracies = [r.accuracy for r in runs_7d if r.accuracy is not None]
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else None
    # Format as percentage-like float if needed, schema expects float.
    # UI usually expects 0.88 for 88%.

    # Aggregation in Python for portability and simplicity.
    # SQL: SELECT date(started_at), avg(...) group by date
    runs_30d = (
        self.session.query(Run)
        .options(*self.run_repo.eager_options())
        .filter(
            Run.started_at >= thirty_days_ago,
            Run.status == RunStatus.COMPLETED,
            Run.is_archived.is_not(True),
        )
        .order_by(Run.started_at)
        .all()
    )

    daily_scores: dict[str, list[float]] = {}
    for r in runs_30d:
      if r.started_at and r.accuracy is not None:
        date_str = r.started_at.strftime("%Y-%m-%d")
        score = r.accuracy
        daily_scores.setdefault(date_str, []).append(score)

    accuracy_history = []
    # Sort dates
    sorted_dates = sorted(daily_scores.keys())
    for date_str in sorted_dates:
      scores = daily_scores[date_str]
      avg_score = sum(scores) / len(scores)
      accuracy_history.append(
          DailyAccuracySchema(date=date_str, accuracy=avg_score)
      )

    # 6.5 Run Volume History (Last 30 Days)
    # We include all runs (even FAILED/CANCELLED) for volume metrics
    all_runs_30d = (
        self.session.query(Run)
        .filter(
            Run.started_at >= thirty_days_ago,
            Run.is_archived.is_not(True),
        )
        .order_by(Run.started_at)
        .all()
    )

    daily_counts: dict[str, int] = {}
    for r in all_runs_30d:
      if r.started_at:
        date_str = r.started_at.strftime("%Y-%m-%d")
        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1

    run_volume_history = []
    sorted_volume_dates = sorted(daily_counts.keys())
    for date_str in sorted_volume_dates:
      run_volume_history.append(
          DailyRunCountSchema(date=date_str, count=daily_counts[date_str])
      )

    # 7. Recent Runs (Limit 5)
    recent_runs_orm = (
        self.session.query(Run)
        .options(*self.run_repo.eager_options())
        .filter(Run.is_archived.is_not(True))
        .order_by(Run.started_at.desc())
        .limit(5)
        .all()
    )
    recent_runs = [RunSchema.model_validate(r) for r in recent_runs_orm]

    # 8. Agent Statuses
    # We need to list ALL agents and determine their status.
    # Query all agents and join with recent run info?
    # Or just query agents, and check set of active_agent_ids.
    all_agents = self.session.query(Agent).all()
    # IDs of agents active in last 7 days
    active_agent_ids_7d = set(
        row[0]
        for row in (
            self.session.query(Run.agent_id)
            .filter(
                Run.started_at >= seven_days_ago,
                Run.is_archived.is_not(True),
            )
            .distinct()
            .all()
        )
    )

    agent_statuses = []
    for a in all_agents:
      status = "Online" if a.id in active_agent_ids_7d else "Offline"
      agent_statuses.append(
          AgentStatusSchema(
              id=a.id,
              name=a.name,
              status=status,
              # Version is not yet tracked, use placeholder if needed
              version="v1.0.0",
          )
      )

    return DashboardStats(
        total_agents=total_agents,
        active_agents_count=active_agents_7d,
        active_agents_24h=active_agents_24h,
        total_runs_7d=total_runs_7d,
        avg_accuracy_score=avg_accuracy,
        accuracy_history=accuracy_history,
        run_volume_history=run_volume_history,
        recent_runs=recent_runs,
        agent_statuses=agent_statuses,
    )
