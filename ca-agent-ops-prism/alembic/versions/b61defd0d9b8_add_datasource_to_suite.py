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

"""add_datasource_to_suite

Revision ID: b61defd0d9b8
Revises: e4761fe3887b
Create Date: 2025-12-30 23:15:41.711770
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b61defd0d9b8'
down_revision = 'e4761fe3887b'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
      'test_suite_snapshots',
      sa.Column('datasource_type', sa.String(), nullable=True),
  )
  op.add_column(
      'test_suite_snapshots',
      sa.Column('datasource_name', sa.String(), nullable=True),
  )
  op.add_column(
      'test_suites', sa.Column('datasource_type', sa.String(), nullable=True)
  )
  op.add_column(
      'test_suites', sa.Column('datasource_name', sa.String(), nullable=True)
  )
  op.add_column('trials', sa.Column('latency_ms', sa.Integer(), nullable=True))


def downgrade() -> None:
  op.drop_column('trials', 'latency_ms')
  op.drop_column('test_suites', 'datasource_name')
  op.drop_column('test_suites', 'datasource_type')
  op.drop_column('test_suite_snapshots', 'datasource_name')
  op.drop_column('test_suite_snapshots', 'datasource_type')
