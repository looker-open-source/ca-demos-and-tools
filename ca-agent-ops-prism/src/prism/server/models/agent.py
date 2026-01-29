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

"""SQLAlchemy model for the Agent entity."""

from typing import Any

from prism.server.db import Base
from prism.server.models.base_mixin import BaseMixin
import sqlalchemy
from sqlalchemy import orm


class Agent(Base, BaseMixin):
  """Represents the system under test (e.g., 'Data Analyst Bot')."""

  __tablename__ = "agents"

  id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
  name: orm.Mapped[str] = orm.mapped_column(sqlalchemy.String, nullable=False)

  # Exploded Config Fields
  project_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String, nullable=False
  )
  location: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String, nullable=False
  )
  agent_resource_id: orm.Mapped[str] = orm.mapped_column(
      sqlalchemy.String, nullable=False
  )

  # Variable Config (Datasource) stored as JSON
  datasource_config: orm.Mapped[dict[str, Any] | None] = orm.mapped_column(
      sqlalchemy.JSON, nullable=True
  )

  # Looker Credentials
  looker_client_id: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.String, nullable=True
  )
  looker_client_secret: orm.Mapped[str | None] = orm.mapped_column(
      sqlalchemy.String, nullable=True
  )
