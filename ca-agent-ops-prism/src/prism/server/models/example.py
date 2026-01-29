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

"""SQLAlchemy model for the Example entity."""

from typing import Any

from prism.server.db import Base
from prism.server.models.base_mixin import BaseMixin
import sqlalchemy
from sqlalchemy import orm


class BaseExample:
  """Mixin for Example fields shared between Live and Snapshot models."""

  logical_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String, nullable=False, index=True
  )
  question: orm.Mapped[str] = orm.mapped_column(sqlalchemy.Text, nullable=False)


class Example(Base, BaseMixin, BaseExample):
  """Represents a single input (e.g., question) within a TestSuite."""

  __tablename__ = "examples"

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  test_suite_id: orm.Mapped[int] = orm.mapped_column(
      sqlalchemy.ForeignKey("test_suites.id"), nullable=False
  )

  # Relationships
  # lazy='selectin' allows accessing suite.examples efficiently
  test_suite = orm.relationship("TestSuite", backref="examples")
  asserts = orm.relationship(
      "Assertion",
      back_populates="example",
      cascade="all, delete-orphan",
      order_by="Assertion.id",
  )
