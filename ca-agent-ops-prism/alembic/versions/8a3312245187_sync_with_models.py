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

"""Sync with models.

Adds trials.error_traceback and trials.failed_stage, and nothing else.

This revision used to also alter runs.status and trials.status from
VARCHAR(9) to the runstatus enum. The VARCHAR(9) was an autogenerate artifact
from a SQLite-era run: on PostgreSQL both columns were created as the native
runstatus enum by e4761fe3887b, so the upgrade emitted an identity cast that
did nothing, and the enum widening this revision looked like it was doing
arrived six revisions later, in c9e86caccc40. The downgrade was worse than a
no-op. It emitted ALTER COLUMN status TYPE VARCHAR(9) with no USING clause and
failed, and a USING would not have saved it either, because EVALUATING is ten
characters. Both directions are gone rather than rewritten, so the downgrade
runs.

Revision ID: 8a3312245187
Revises: e8fe334fbbf5
Create Date: 2026-01-05 15:51:04.363512
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8a3312245187'
down_revision = 'e8fe334fbbf5'
branch_labels = None
depends_on = None


def upgrade() -> None:
  with op.batch_alter_table('trials', schema=None) as batch_op:
    batch_op.add_column(sa.Column('error_traceback', sa.Text(), nullable=True))
    batch_op.add_column(
        sa.Column('failed_stage', sa.String(length=50), nullable=True)
    )


def downgrade() -> None:
  with op.batch_alter_table('trials', schema=None) as batch_op:
    batch_op.drop_column('failed_stage')
    batch_op.drop_column('error_traceback')
