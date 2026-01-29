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

"""SQLAlchemy models for Snapshot entities (History)."""

from prism.server.db import Base
from prism.server.models.base_mixin import BaseMixin
from prism.server.models.example import BaseExample
from prism.server.models.suite import BaseSuite
import sqlalchemy
from sqlalchemy import orm


class TestSuiteSnapshot(Base, BaseMixin, BaseSuite):
  """Immutable snapshot of a Test Suite at a point in time."""

  __test__ = False
  __tablename__ = "test_suite_snapshots"

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  # Reference to the original suite (optional, suite might be deleted)
  original_suite_id: orm.Mapped[int | None] = orm.mapped_column(
      sqlalchemy.Integer, nullable=True, index=True
  )


class ExampleSnapshot(Base, BaseMixin, BaseExample):
  """Immutable snapshot of an Example at a point in time."""

  __tablename__ = "example_snapshots"

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  snapshot_suite_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("test_suite_snapshots.id"), nullable=False
  )
  # Reference to the original example (for history tracing)
  original_example_id: orm.Mapped[int | None] = orm.mapped_column(
      sqlalchemy.Integer, nullable=True, index=True
  )

  # Relationships
  snapshot_suite = orm.relationship(
      "TestSuiteSnapshot",
      backref=orm.backref("examples", order_by="ExampleSnapshot.id"),
  )
  asserts = orm.relationship(
      "AssertionSnapshot",
      back_populates="example_snapshot",
      cascade="all, delete-orphan",
      order_by="AssertionSnapshot.id",
  )
