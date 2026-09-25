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

"""Add timezone to run and trial timestamps

Revision ID: 5bfcd38eae39
Revises: 7d75673c8561
Create Date: 2026-01-22 03:26:00.316625
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5bfcd38eae39'
down_revision = '7d75673c8561'
branch_labels = None
depends_on = None

# The rows these columns already hold were written as UTC. Without a USING
# clause Postgres reads each naive value as a wall clock time in the session's
# TimeZone, so on a server left at a local zone every historical timestamp
# shifted by the offset. Both columns shift together, so duration_ms stays
# right and the corruption never shows up where anyone would catch it.
_COLUMNS = (
    ('runs', 'started_at'),
    ('runs', 'completed_at'),
    ('trials', 'started_at'),
    ('trials', 'completed_at'),
)


def upgrade() -> None:
  for table, column in _COLUMNS:
    op.alter_column(
        table,
        column,
        existing_type=postgresql.TIMESTAMP(),
        type_=sa.DateTime(timezone=True),
        existing_nullable=True,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
  for table, column in reversed(_COLUMNS):
    op.alter_column(
        table,
        column,
        existing_type=sa.DateTime(timezone=True),
        type_=postgresql.TIMESTAMP(),
        existing_nullable=True,
        postgresql_using=f"{column} AT TIME ZONE 'UTC'",
    )
