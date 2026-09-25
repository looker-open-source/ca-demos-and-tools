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

"""remove_asserts_column_from_examples

Revision ID: 0d306800fe55
Revises: a26b5bc93f48
Create Date: 2026-01-02 20:26:15.803470
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0d306800fe55'
down_revision = 'a26b5bc93f48'
branch_labels = None
depends_on = None


def upgrade() -> None:
  with op.batch_alter_table('examples') as batch_op:
    batch_op.drop_column('asserts')


def downgrade() -> None:
  with op.batch_alter_table('examples') as batch_op:
    batch_op.add_column(sa.Column('asserts', sa.JSON(), nullable=True))
