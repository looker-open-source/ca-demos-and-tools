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

"""add_results_to_playground_traces

Revision ID: c67b9fdcae84
Revises: 6b60f6ea7e62
Create Date: 2025-12-31 19:27:18.267077
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c67b9fdcae84'
down_revision = '6b60f6ea7e62'
branch_labels = None
depends_on = None


def upgrade() -> None:
  # Added nullable, backfilled, then tightened. The two NOT NULL columns went
  # on with no default, which fails outright on a playground_traces table that
  # already has rows, and the preceding revision is what creates that table.
  # prod.py migrates at import and fails closed, so that is a deploy that
  # never starts. No server default survives the tightening, so the result
  # still matches the models.
  op.add_column(
      'playground_traces',
      sa.Column('assertion_results', sa.JSON(), nullable=True),
  )
  op.add_column(
      'playground_traces', sa.Column('score', sa.Float(), nullable=True)
  )
  op.add_column(
      'playground_traces', sa.Column('latency_ms', sa.Integer(), nullable=True)
  )
  op.add_column(
      'playground_traces', sa.Column('passed', sa.Boolean(), nullable=True)
  )
  op.execute(
      "UPDATE playground_traces SET assertion_results = '[]', passed = false"
      ' WHERE assertion_results IS NULL'
  )
  op.alter_column('playground_traces', 'assertion_results', nullable=False)
  op.alter_column('playground_traces', 'passed', nullable=False)


def downgrade() -> None:
  op.drop_column('playground_traces', 'passed')
  op.drop_column('playground_traces', 'latency_ms')
  op.drop_column('playground_traces', 'score')
  op.drop_column('playground_traces', 'assertion_results')
