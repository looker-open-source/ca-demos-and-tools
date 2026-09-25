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

"""Add generate_suggestions to Run

Revision ID: a22be0585aee
Revises: 8c6080c6545f
Create Date: 2026-02-13 16:00:29.876634
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a22be0585aee'
down_revision = '8c6080c6545f'
branch_labels = None
depends_on = None


def upgrade():
  op.add_column(
      'runs',
      sa.Column(
          'generate_suggestions',
          sa.Boolean(),
          server_default=sa.text('false'),
          nullable=False,
      ),
  )


def downgrade():
  op.drop_column('runs', 'generate_suggestions')
