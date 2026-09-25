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

"""create_playground_traces

Revision ID: 6b60f6ea7e62
Revises: cb607eef9ff8
Create Date: 2025-12-31 19:26:19.658819
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '6b60f6ea7e62'
down_revision = 'cb607eef9ff8'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
      'playground_traces',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('created_at', sa.DateTime(), nullable=False),
      sa.Column('question', sa.Text(), nullable=False),
      sa.Column('agent_id', sa.Integer(), nullable=False),
      sa.Column('trace_results', sa.JSON(), nullable=False),
      sa.Column('output_text', sa.Text(), nullable=True),
      sa.Column('error_message', sa.Text(), nullable=True),
      sa.Column(
          'modified_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column('is_archived', sa.Boolean(), nullable=False),
      sa.ForeignKeyConstraint(
          ['agent_id'],
          ['agents.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )


def downgrade() -> None:
  op.drop_table('playground_traces')
