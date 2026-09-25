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

"""Remove agent_env

Revision ID: 8c6080c6545f
Revises: 2ef9abb9e513
Create Date: 2026-01-29 02:56:25.555314
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8c6080c6545f'
down_revision = '2ef9abb9e513'
branch_labels = None
depends_on = None


def upgrade():
  op.drop_column('agents', 'env')


def downgrade():
  # PROD is what 499b6db4e31b moved every PUBLISHED agent to, so it is the
  # value to restore. Without a default the column cannot go back NOT NULL
  # on a database that has agents, and the downgrade fails.
  op.add_column(
      'agents',
      sa.Column(
          'env',
          postgresql.ENUM(
              'STAGING', 'PUBLISHED', 'PROD', 'AUTOPUSH', name='agentenv'
          ),
          server_default='PROD',
          autoincrement=False,
          nullable=False,
      ),
  )
