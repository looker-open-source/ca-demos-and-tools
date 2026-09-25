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

"""SQLAlchemy models for Execution entities (Runs, Trials)."""

import datetime
from typing import Any

from prism.common.schemas.execution import RunStatus
from prism.server.db import Base
from prism.server.models.assertion import AssertionResult
from prism.server.models.assertion import AssertionSnapshot
from prism.server.models.base_mixin import BaseMixin
import sqlalchemy
from sqlalchemy import orm
from sqlalchemy.ext.hybrid import hybrid_property


class Run(Base, BaseMixin):
  """Represents an execution of a Test Suite (Snapshot) against an Agent."""

  __tablename__ = "runs"

  # Every list query filters on the archive flag, most add the agent or the
  # status, and they all order by created_at. None of those columns was
  # indexed, so the evaluations page scanned the whole table.
  __table_args__ = (
      sqlalchemy.Index("ix_runs_agent_id", "agent_id"),
      sqlalchemy.Index("ix_runs_status", "status"),
      sqlalchemy.Index("ix_runs_created_at", "created_at"),
      sqlalchemy.Index("ix_runs_is_archived", "is_archived"),
  )

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)

  # Configuration
  test_suite_snapshot_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("test_suite_snapshots.id"), nullable=False
  )
  agent_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("agents.id"), nullable=False
  )
  # JSON snapshot of the full agent context (published context)
  # to allow reproducing the run even if the agent is updated.
  agent_context_snapshot: orm.Mapped[dict[str, Any] | None] = orm.mapped_column(
      sqlalchemy.JSON, nullable=True
  )

  # Execution State
  status: orm.Mapped[RunStatus] = orm.mapped_column(
      sqlalchemy.Enum(RunStatus), default=RunStatus.PENDING, nullable=False
  )
  started_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )
  completed_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )
  generate_suggestions: orm.Mapped[bool] = orm.mapped_column(
      sqlalchemy.Boolean,
      default=False,
      server_default=sqlalchemy.sql.expression.false(),
      nullable=False,
  )
  concurrency: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.Integer, default=2, server_default="2", nullable=False
  )
  error_message: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )
  # Why the last BigQuery export of this run failed, cleared by a clean one.
  # On the row rather than in the exporter, which kept it in a process global:
  # a restart mid-export lost the failure and the badge went green over a
  # half-written warehouse, and two server processes disagreed about it.
  bigquery_export_error: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )

  @property
  def agent_name(self) -> str | None:
    """The agent's name, or None if the agent row is gone."""
    return self.agent.name if self.agent else None

  @property
  def suite_name(self) -> str | None:
    """The snapshotted suite's name, or None if the snapshot is gone."""
    return self.snapshot_suite.name if self.snapshot_suite else None

  @property
  def original_suite_id(self) -> int | None:
    """The live suite this run's snapshot came from, if it still exists."""
    return (
        self.snapshot_suite.original_suite_id if self.snapshot_suite else None
    )

  @property
  def accuracy(self) -> float | None:
    """Returns average accuracy for completed/failed trials."""
    # Mean over every trial that finished, whether it succeeded or errored.
    #
    # A FAILED trial never produces assertion results, so its ``score`` is None.
    # Skipping those drops errored trials out of the denominator and reports a
    # run where half the trials crashed as 100% accurate. An errored trial
    # answered nothing, so it scores 0.
    #
    # A COMPLETED trial with a None score is different: its example has no
    # weighted assertions, so there was nothing to be right or wrong about. It
    # stays excluded.
    scores = []
    for trial in self.trials:
      if trial.status == RunStatus.FAILED:
        scores.append(0.0)
      elif trial.status == RunStatus.COMPLETED and trial.score is not None:
        scores.append(trial.score)

    if not scores:
      return None

    return sum(scores) / len(scores)

  @hybrid_property
  def duration_ms(self) -> int | None:
    """Returns the wall-clock duration of the run in milliseconds."""
    if self.started_at and self.completed_at:
      return int((self.completed_at - self.started_at).total_seconds() * 1000)
    return None

  @duration_ms.expression
  def duration_ms(cls):  # pylint: disable=no-self-argument
    """SQL expression for duration in milliseconds (PostgreSQL only)."""
    return sqlalchemy.cast(
        sqlalchemy.func.extract(
            "EPOCH", sqlalchemy.func.age(cls.completed_at, cls.started_at)
        )
        * 1000,
        sqlalchemy.Integer,
    )

  # Relationships
  snapshot_suite = orm.relationship("TestSuiteSnapshot")
  agent = orm.relationship("Agent")
  trials = orm.relationship(
      "Trial", backref="run", cascade="all, delete-orphan", order_by="Trial.id"
  )


class Trial(Base, BaseMixin):
  """Represents a single execution of an Example within a Run."""

  __tablename__ = "trials"

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  run_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("runs.id"), nullable=False, index=True
  )

  # The specific version of the example used
  example_snapshot_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("example_snapshots.id"), nullable=False
  )

  # Execution State
  status: orm.Mapped[RunStatus] = orm.mapped_column(
      sqlalchemy.Enum(RunStatus), default=RunStatus.PENDING, nullable=False
  )
  started_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )
  completed_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )

  # Result Data
  output_text: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )
  error_message: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )
  error_traceback: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )
  failed_stage: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.String(50), nullable=True
  )
  trial_pid: orm.Mapped[int | None] = orm.mapped_column(
      sqlalchemy.Integer, nullable=True
  )
  # psutil's create_time() for the process in trial_pid, which is the other
  # half of its identity. A container restart gives the worker a fresh PID
  # namespace and its new children land on the PIDs the pre-restart trials
  # recorded, so those trials read as alive, held their run's capacity for the
  # full 30 minute timeout, and were then killed off a PID that by that point
  # belonged to a healthy trial.
  trial_pid_started_at: orm.Mapped[float | None] = orm.mapped_column(
      sqlalchemy.Float, nullable=True
  )
  retry_count: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.Integer, default=0, server_default="0", nullable=False
  )
  max_retries: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.Integer, default=3, server_default="3", nullable=False
  )
  # JSON storage for trace details
  trace_results: orm.Mapped[list[dict[str, Any]] | None] = orm.mapped_column(
      sqlalchemy.JSON, nullable=True
  )

  @property
  def agent_name(self) -> str | None:
    """Returns the agent name via the run relationship."""
    return self.run.agent.name if self.run and self.run.agent else None

  # Scoring
  @hybrid_property
  def score(self) -> float | None:
    """Calculates accuracy based on assertion results."""
    # Weighted, not a plain mean over the weight > 0 rows. The UI only ever
    # writes 0 or 1, so the two agree today, but the column is a float and
    # anything that writes a real weight would have been silently ignored.
    scored_results = [
        r for r in self.assertion_results if r.assertion_snapshot.weight > 0
    ]
    if not scored_results:
      return None
    total_weight = sum(r.assertion_snapshot.weight for r in scored_results)
    return (
        sum(r.score * r.assertion_snapshot.weight for r in scored_results)
        / total_weight
    )

  @score.expression
  def score(cls):  # pylint: disable=no-self-argument
    """SQL expression for score to allow querying."""

    return (
        sqlalchemy.select(
            sqlalchemy.func.sum(
                AssertionResult.score * AssertionSnapshot.weight
            )
            / sqlalchemy.func.sum(AssertionSnapshot.weight)
        )
        .where(AssertionResult.trial_id == cls.id)
        # select_from because the weight in the select list already puts
        # AssertionSnapshot in the FROM. Without it the join has two candidate
        # left sides and raises at compile time.
        .select_from(AssertionResult)
        .join(
            AssertionSnapshot,
            AssertionResult.assertion_snapshot_id == AssertionSnapshot.id,
        )
        .where(AssertionSnapshot.weight > 0)
        .correlate_except(AssertionResult)
        .scalar_subquery()
    )

  @hybrid_property
  def duration_ms(self) -> int | None:
    """Returns the wall-clock duration of the trial in milliseconds."""
    if self.started_at and self.completed_at:
      return int((self.completed_at - self.started_at).total_seconds() * 1000)
    return None

  @duration_ms.expression
  def duration_ms(cls):  # pylint: disable=no-self-argument
    """SQL expression for duration in milliseconds (PostgreSQL only)."""
    return sqlalchemy.cast(
        sqlalchemy.func.extract("EPOCH", (cls.completed_at - cls.started_at))
        * 1000,
        sqlalchemy.Integer,
    )

  @property
  def ttfr_ms(self) -> int | None:
    """Returns the time to first response in ms, derived from the trace."""
    if not self.trace_results:
      return None
    # Approximates first response with the first trace event that carries a
    # timestamp. The real measurement is taken live in
    # GeminiDataAnalyticsClient.ask_question and is not stored.
    for event in self.trace_results:
      if "timestamp" in event:
        try:
          ts = datetime.datetime.fromisoformat(
              event["timestamp"].replace("Z", "+00:00")
          )
          baseline = self.started_at or self.created_at
          if baseline:
            if baseline.tzinfo is None:
              baseline = baseline.replace(tzinfo=datetime.timezone.utc)
            return int((ts - baseline).total_seconds() * 1000)
        except ValueError:
          continue
    return None

  # Relationships
  assertion_results = orm.relationship(
      "AssertionResult",
      backref="trial",
      cascade="all, delete-orphan",
      order_by="AssertionResult.id",
  )
  suggested_asserts = orm.relationship(
      "SuggestedAssertion",
      back_populates="trial",
      cascade="all, delete-orphan",
      order_by="SuggestedAssertion.id",
  )

  example_snapshot = orm.relationship("ExampleSnapshot")
