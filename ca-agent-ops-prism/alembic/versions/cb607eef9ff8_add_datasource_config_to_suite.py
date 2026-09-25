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

"""add_datasource_config_to_suite

Revision ID: cb607eef9ff8
Revises: b61defd0d9b8
Create Date: 2025-12-30 23:50:00.536052
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cb607eef9ff8'
down_revision = 'b61defd0d9b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
      'test_suite_snapshots',
      sa.Column('datasource_config', sa.JSON(), nullable=True),
  )
  op.add_column(
      'test_suites', sa.Column('datasource_config', sa.JSON(), nullable=True)
  )


def downgrade() -> None:
  op.drop_column('test_suites', 'datasource_config')
  op.drop_column('test_suite_snapshots', 'datasource_config')
