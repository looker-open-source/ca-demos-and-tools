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

"""Shared mixins for SQLAlchemy models."""

import datetime

import sqlalchemy
from sqlalchemy import orm


class BaseMixin:
  """Mixin class that adds standard timestamp and archive fields."""

  created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True),
      server_default=sqlalchemy.func.now(),
      nullable=False,
  )
  modified_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
      sqlalchemy.DateTime(timezone=True),
      server_default=sqlalchemy.func.now(),
      onupdate=sqlalchemy.func.now(),
      nullable=False,
  )
  is_archived: orm.Mapped[bool] = orm.mapped_column(
      sqlalchemy.Boolean, default=False, nullable=False
  )
