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

"""SQLAlchemy models for Assertion entities."""

from typing import Any

from prism.common.schemas.assertion import AssertionType
from prism.server.db import Base
from prism.server.models.base_mixin import BaseMixin
import sqlalchemy
from sqlalchemy import orm


class BaseAssertion:
  """Mixin for Assertion fields shared between Live, Snapshot and Suggested models."""

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)

  type: orm.Mapped[AssertionType] = orm.mapped_column(
      sqlalchemy.Enum(AssertionType), nullable=False
  )
  weight: orm.Mapped[float] = orm.mapped_column(
      sqlalchemy.Float, default=1.0, nullable=False
  )
  # JSON storage for type-specific parameters (e.g., value, columns, max_ms)
  params: orm.Mapped[dict[str, Any]] = orm.mapped_column(
      sqlalchemy.JSON, default=dict, nullable=False
  )


class Assertion(Base, BaseMixin, BaseAssertion):
  """Represents a single assertion rule within an Example."""

  __tablename__ = "assertions"

  example_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("examples.id"), nullable=False, index=True
  )

  # Relationships
  example = orm.relationship("Example", back_populates="asserts")


class AssertionSnapshot(Base, BaseMixin, BaseAssertion):
  """Immutable snapshot of an Assertion at a point in time."""

  __tablename__ = "assertion_snapshots"

  example_snapshot_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("example_snapshots.id"), nullable=False, index=True
  )
  # Reference to the original assertion (optional, might be deleted)
  original_assertion_id: orm.Mapped[int | None] = orm.mapped_column(
      sqlalchemy.Integer, nullable=True
  )

  # Relationships
  example_snapshot = orm.relationship(
      "ExampleSnapshot", back_populates="asserts"
  )
  assertion_results = orm.relationship(
      "AssertionResult", back_populates="assertion_snapshot"
  )


class AssertionResult(Base, BaseMixin):
  """Result of an assertion evaluation for a specific Trial."""

  __tablename__ = "assertion_results"

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  trial_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("trials.id"), nullable=False, index=True
  )
  assertion_snapshot_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("assertion_snapshots.id"), nullable=False
  )

  passed: orm.Mapped[bool] = orm.mapped_column(
      sqlalchemy.Boolean, nullable=False
  )
  score: orm.Mapped[float] = orm.mapped_column(
      sqlalchemy.Float, nullable=False, default=0.0
  )
  reasoning: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )
  error_message: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )

  # Relationships
  # trial is backref-ed from Trial model
  assertion_snapshot = orm.relationship(
      "AssertionSnapshot", back_populates="assertion_results"
  )

  @property
  def assertion(self):
    """Alias for assertion_snapshot to satisfy Pydantic schema."""
    return self.assertion_snapshot


class SuggestedAssertion(Base, BaseMixin, BaseAssertion):
  """A suggested assertion generated from a Trial trace."""

  __tablename__ = "suggested_assertions"

  trial_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("trials.id"), nullable=False, index=True
  )

  reasoning: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.Text, nullable=True
  )

  # Relationships
  trial = orm.relationship("Trial", back_populates="suggested_asserts")
