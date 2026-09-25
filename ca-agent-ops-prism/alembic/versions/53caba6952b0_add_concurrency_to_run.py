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

"""add concurrency to run

Revision ID: 53caba6952b0
Revises: a22be0585aee
Create Date: 2026-02-19 18:26:25.800608
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '53caba6952b0'
down_revision = 'a22be0585aee'
branch_labels = None
depends_on = None


def upgrade():
  op.add_column(
      'runs',
      sa.Column(
          'concurrency', sa.Integer(), server_default='2', nullable=False
      ),
  )


def downgrade():
  op.drop_column('runs', 'concurrency')
