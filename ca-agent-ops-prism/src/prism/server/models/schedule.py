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

"""SQLAlchemy model for Scheduled Evaluations."""

import datetime

from prism.common.schemas.execution import RunStatus
from prism.server.db import Base
from prism.server.models.base_mixin import BaseMixin
import sqlalchemy
from sqlalchemy import orm


class EvalSchedule(Base, BaseMixin):
  """Represents a recurring evaluation schedule pairing an Agent and Suite."""

  __tablename__ = "eval_schedules"

  __table_args__ = (
      sqlalchemy.Index("ix_eval_schedules_agent_id", "agent_id"),
      sqlalchemy.Index("ix_eval_schedules_test_suite_id", "test_suite_id"),
      sqlalchemy.Index(
          "ix_eval_schedules_due",
          "is_enabled",
          "is_archived",
          "next_run_at",
      ),
  )

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  name: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(200), nullable=False
  )
  agent_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("agents.id"), nullable=False
  )
  test_suite_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("test_suites.id"), nullable=False
  )

  cadence: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(32),
      default="DAILY",
      server_default="DAILY",
      nullable=False,
  )
  cron_expression: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(100), nullable=False
  )
  timezone: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String(64),
      default="UTC",
      server_default="UTC",
      nullable=False,
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
  is_enabled: orm.Mapped[bool] = orm.mapped_column(
      sqlalchemy.Boolean,
      default=True,
      server_default=sqlalchemy.sql.expression.true(),
      nullable=False,
  )

  next_run_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )
  last_run_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )
  last_run_id: orm.Mapped[int | None] = orm.mapped_column(
      sqlalchemy.Integer, nullable=True
  )
  last_error_message: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )
  # Set under the row lock before create_run and cleared once the run row is
  # committed. create_snapshot commits partway through create_run, which drops
  # the row lock while no Run exists yet, so has_active_run alone let a second
  # Run Now or the worker start a duplicate in that window.
  dispatch_started_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True), nullable=True
  )

  agent = orm.relationship("Agent")
  test_suite = orm.relationship("TestSuite")
  last_run = orm.relationship(
      "Run",
      foreign_keys=[last_run_id],
      primaryjoin="EvalSchedule.last_run_id == Run.id",
      viewonly=True,
  )

  @property
  def agent_name(self) -> str | None:
    """The agent's display name, or None if missing."""
    return self.agent.name if self.agent else None

  @property
  def suite_name(self) -> str | None:
    """The test suite's display name, or None if missing."""
    return self.test_suite.name if self.test_suite else None

  @property
  def last_run_status(self) -> RunStatus | None:
    """Status of the most recent run triggered by this schedule."""
    return self.last_run.status if self.last_run else None
