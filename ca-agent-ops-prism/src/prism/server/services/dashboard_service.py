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
from prism.common.schemas.dashboard import DailyAccuracySchema
from prism.common.schemas.dashboard import DailyRunCountSchema
from prism.common.schemas.dashboard import DashboardStats
from prism.common.schemas.execution import RunSchema
from prism.common.schemas.execution import RunStatus
from prism.server.models.run import Run
from prism.server.repositories.run_repository import RunRepository
from sqlalchemy import orm


class DashboardService:
  """Builds the home page figures from the Run table."""

  def __init__(self, session: orm.Session):
    self.session = session
    self.run_repo = RunRepository(session)

  def get_dashboard_stats(self) -> DashboardStats:
    """Calculates and returns dashboard statistics."""
    now = datetime.datetime.now(datetime.timezone.utc)
    thirty_days_ago = now - datetime.timedelta(days=30)

    # Bucketed in Python because accuracy is not a column. Run.accuracy is a
    # property over the run's trials, and a GROUP BY would have to rebuild
    # that whole weighted average in SQL to report the same number the run
    # detail page does.
    #
    # On created_at, the same field the volume series below uses. This one was
    # on started_at, so a run created at 23:50 and picked up by the worker
    # after midnight drew its accuracy point on one day and its bar on the day
    # before, and a day holding one run showed an accuracy over a volume of 0.
    # created_at is also the field that is never NULL.
    runs_30d = (
        self.session.query(Run)
        .options(*self.run_repo.eager_options())
        .filter(
            Run.created_at >= thirty_days_ago,
            Run.status == RunStatus.COMPLETED,
            Run.is_archived.is_not(True),
        )
        .order_by(Run.created_at)
        .all()
    )

    daily_scores: dict[str, list[float]] = {}
    for r in runs_30d:
      if r.accuracy is not None:
        date_str = r.created_at.strftime("%Y-%m-%d")
        score = r.accuracy
        daily_scores.setdefault(date_str, []).append(score)

    accuracy_history = []

    sorted_dates = sorted(daily_scores.keys())
    for date_str in sorted_dates:
      scores = daily_scores[date_str]
      avg_score = sum(scores) / len(scores)
      accuracy_history.append(
          DailyAccuracySchema(date=date_str, accuracy=avg_score)
      )

    # Volume counts every run, including FAILED and CANCELLED ones. Also on
    # created_at: started_at is NULL until the worker promotes the run, so a
    # queued run was counted on no day at all.
    all_runs_30d = (
        self.session.query(Run)
        .filter(
            Run.created_at >= thirty_days_ago,
            Run.is_archived.is_not(True),
        )
        .order_by(Run.created_at)
        .all()
    )

    daily_counts: dict[str, int] = {}
    for r in all_runs_30d:
      date_str = r.created_at.strftime("%Y-%m-%d")
      daily_counts[date_str] = daily_counts.get(date_str, 0) + 1

    run_volume_history = []
    sorted_volume_dates = sorted(daily_counts.keys())
    for date_str in sorted_volume_dates:
      run_volume_history.append(
          DailyRunCountSchema(date=date_str, count=daily_counts[date_str])
      )

    recent_runs_orm = (
        self.session.query(Run)
        .options(*self.run_repo.eager_options())
        .filter(Run.is_archived.is_not(True))
        # nullslast because started_at is NULL until a run is promoted and
        # Postgres sorts NULLs first on DESC. Queue five runs and the whole
        # panel filled up with runs that had never executed.
        .order_by(Run.started_at.desc().nullslast())
        .limit(5)
        .all()
    )
    recent_runs = [RunSchema.model_validate(r) for r in recent_runs_orm]

    return DashboardStats(
        accuracy_history=accuracy_history,
        run_volume_history=run_volume_history,
        recent_runs=recent_runs,
    )
