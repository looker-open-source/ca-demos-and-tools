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

  # Aggregated Stats
  @property
  def total_examples(self) -> int:
    """Returns total number of trials."""
    return len(self.trials)

  @property
  def failed_examples(self) -> int:
    """Returns number of failed trials."""
    # Derived from status counts if they are trustworthy, or just keep
    # iterating trials which is safer for sync.
    return sum(1 for t in self.trials if t.status == RunStatus.FAILED)

  @property
  def agent_name(self) -> str | None:
    """Returns the agent name."""
    return self.agent.name if self.agent else None

  @property
  def suite_name(self) -> str | None:
    """Returns the suite name."""
    return self.snapshot_suite.name if self.snapshot_suite else None

  @property
  def original_suite_id(self) -> int | None:
    """Returns the original suite ID from the snapshot."""
    return (
        self.snapshot_suite.original_suite_id if self.snapshot_suite else None
    )

  @property
  def accuracy(self) -> float | None:
    """Returns average accuracy for completed/failed trials."""
    # User requested: mean of trial accuracy for all trials with run_status
    # COMPLETED or FAILED.
    valid_trials = [
        t
        for t in self.trials
        if t.status in (RunStatus.COMPLETED, RunStatus.FAILED)
        and t.score is not None
    ]
    if not valid_trials:
      return None

    total_score = sum(t.score for t in valid_trials)
    return total_score / len(valid_trials)

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

  error_message: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
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
    # Only consider assertions with weight > 0
    scored_results = [
        r for r in self.assertion_results if r.assertion_snapshot.weight > 0
    ]
    if not scored_results:
      return None
    return sum(r.score for r in scored_results) / len(scored_results)

  @score.expression
  def score(cls):  # pylint: disable=no-self-argument
    """SQL expression for score to allow querying."""

    return (
        sqlalchemy.select(sqlalchemy.func.avg(AssertionResult.score))
        .where(AssertionResult.trial_id == cls.id)
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
    """Returns the time to first response in milliseconds, derived from trace."""
    if not self.trace_results:
      return None
    # Simple derivation: first event with system_message or data
    # (In a real scenario, this would use TimelineService logic)
    for event in self.trace_results:
      if "timestamp" in event:
        try:
          ts = datetime.datetime.fromisoformat(
              event["timestamp"].replace("Z", "+00:00")
          )
          baseline = self.started_at or self.created_at
          if baseline:
            # Shift baseline to TZ aware if needed
            if baseline.tzinfo is None:
              baseline = baseline.replace(tzinfo=datetime.timezone.utc)
            return int((ts - baseline).total_seconds() * 1000)
        except (ValueError, KeyError):
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

  # Relationships
  example_snapshot = orm.relationship("ExampleSnapshot")
