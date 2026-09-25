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

"""fix_state

Revision ID: 2ef9abb9e513
Revises: 2bab71b9e3db
Create Date: 2026-01-25 23:21:27.004050
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2ef9abb9e513'
down_revision = '2bab71b9e3db'
branch_labels = None
depends_on = None


def upgrade():
  """Add process management columns to trials if they don't exist."""
  conn = op.get_bind()
  inspector = sa.inspect(conn)
  columns = [c['name'] for c in inspector.get_columns('trials')]

  if 'trial_pid' not in columns:
    op.add_column('trials', sa.Column('trial_pid', sa.Integer(), nullable=True))
  if 'retry_count' not in columns:
    op.add_column(
        'trials',
        sa.Column(
            'retry_count', sa.Integer(), server_default='0', nullable=False
        ),
    )
  if 'max_retries' not in columns:
    op.add_column(
        'trials',
        sa.Column(
            'max_retries', sa.Integer(), server_default='3', nullable=False
        ),
    )


def downgrade():
  """Remove process management columns."""
  op.drop_column('trials', 'max_retries')
  op.drop_column('trials', 'retry_count')
  op.drop_column('trials', 'trial_pid')
