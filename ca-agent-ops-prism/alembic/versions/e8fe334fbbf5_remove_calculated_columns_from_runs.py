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

"""remove calculated columns from runs

Revision ID: e8fe334fbbf5
Revises: 7cdc4df909dc
Create Date: 2026-01-04 01:50:39.363548
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e8fe334fbbf5'
down_revision = '7cdc4df909dc'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.drop_column('runs', 'passed_examples')
  op.drop_column('runs', 'total_examples')
  op.drop_column('runs', 'failed_examples')


def downgrade() -> None:
  # server_default, as on the two below. Without it this one line fails the
  # whole downgrade on any database that has runs.
  op.add_column(
      'runs',
      sa.Column(
          'failed_examples',
          sa.INTEGER(),
          server_default=sa.text('0'),
          nullable=False,
      ),
  )
  op.add_column(
      'runs',
      sa.Column(
          'total_examples',
          sa.INTEGER(),
          server_default=sa.text('0'),
          nullable=False,
      ),
  )
  op.add_column(
      'runs',
      sa.Column(
          'passed_examples',
          sa.INTEGER(),
          server_default=sa.text('0'),
          nullable=False,
      ),
  )
