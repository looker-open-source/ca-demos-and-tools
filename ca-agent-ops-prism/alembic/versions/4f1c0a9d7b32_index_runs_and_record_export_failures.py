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
"""Index the runs list columns and record export failures on the run.

Revision ID: 4f1c0a9d7b32
Revises: 87d5db0c5bc2
Create Date: 2026-09-18 10:12:04.117832
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4f1c0a9d7b32'
down_revision = '87d5db0c5bc2'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
      'runs', sa.Column('bigquery_export_error', sa.Text(), nullable=True)
  )
  op.create_index('ix_runs_agent_id', 'runs', ['agent_id'], unique=False)
  op.create_index('ix_runs_status', 'runs', ['status'], unique=False)
  op.create_index('ix_runs_created_at', 'runs', ['created_at'], unique=False)
  op.create_index('ix_runs_is_archived', 'runs', ['is_archived'], unique=False)


def downgrade() -> None:
  op.drop_index('ix_runs_is_archived', table_name='runs')
  op.drop_index('ix_runs_created_at', table_name='runs')
  op.drop_index('ix_runs_status', table_name='runs')
  op.drop_index('ix_runs_agent_id', table_name='runs')
  op.drop_column('runs', 'bigquery_export_error')
