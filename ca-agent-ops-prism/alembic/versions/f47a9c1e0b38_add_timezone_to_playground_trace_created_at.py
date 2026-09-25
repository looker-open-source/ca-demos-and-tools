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

# pylint: disable=invalid-name
"""Add timezone to playground_traces.created_at

playground_traces.created_at was the one naive timestamp left in the schema.
Every other column is timestamptz, including modified_at on this same table, so
a trace read back came out naive and raised the moment it was compared with
anything else.

Revision ID: f47a9c1e0b38
Revises: d3f81a6c4b22
Create Date: 2026-09-19 11:12:47.884103
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f47a9c1e0b38'
down_revision = 'd3f81a6c4b22'
branch_labels = None
depends_on = None


def upgrade() -> None:
  # The model's default wrote these as UTC. Without the USING clause Postgres
  # reads each naive value as a wall clock time in the session's TimeZone, so
  # on a server left at a local zone every existing trace shifts by the offset.
  op.alter_column(
      'playground_traces',
      'created_at',
      existing_type=postgresql.TIMESTAMP(),
      type_=sa.DateTime(timezone=True),
      existing_nullable=False,
      postgresql_using="created_at AT TIME ZONE 'UTC'",
  )


def downgrade() -> None:
  op.alter_column(
      'playground_traces',
      'created_at',
      existing_type=sa.DateTime(timezone=True),
      type_=postgresql.TIMESTAMP(),
      existing_nullable=False,
      postgresql_using="created_at AT TIME ZONE 'UTC'",
  )
