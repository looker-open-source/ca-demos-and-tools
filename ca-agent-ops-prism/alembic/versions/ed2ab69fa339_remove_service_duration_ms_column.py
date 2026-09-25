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

"""Remove service_duration_ms column

Revision ID: ed2ab69fa339
Revises: 3ca5b4628874
Create Date: 2026-01-14 15:51:35.224945
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ed2ab69fa339'
down_revision = '3ca5b4628874'
branch_labels = None
depends_on = None


def upgrade() -> None:
  with op.batch_alter_table('trials', schema=None) as batch_op:
    batch_op.drop_column('service_duration_ms')


def downgrade() -> None:
  with op.batch_alter_table('trials', schema=None) as batch_op:
    batch_op.add_column(
        sa.Column('service_duration_ms', sa.INTEGER(), nullable=True)
    )
