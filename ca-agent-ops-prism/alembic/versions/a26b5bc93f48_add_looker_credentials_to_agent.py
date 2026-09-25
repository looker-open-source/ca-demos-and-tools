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

"""Add Looker credentials to Agent

Revision ID: a26b5bc93f48
Revises: c67b9fdcae84
Create Date: 2025-12-31 23:42:58.434421
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a26b5bc93f48'
down_revision = 'c67b9fdcae84'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
      'agents', sa.Column('looker_client_id', sa.String(), nullable=True)
  )
  op.add_column(
      'agents', sa.Column('looker_client_secret', sa.String(), nullable=True)
  )


def downgrade() -> None:
  op.drop_column('agents', 'looker_client_secret')
  op.drop_column('agents', 'looker_client_id')
