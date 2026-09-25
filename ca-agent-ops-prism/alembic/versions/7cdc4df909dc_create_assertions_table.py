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

"""create_assertions_table

Revision ID: 7cdc4df909dc
Revises: 0d306800fe55
Create Date: 2026-01-02 20:27:47.009565
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '7cdc4df909dc'
down_revision = '0d306800fe55'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
      'assertion_snapshots',
      sa.Column('example_snapshot_id', sa.Integer(), nullable=False),
      sa.Column('original_assertion_id', sa.Integer(), nullable=True),
      sa.Column(
          'created_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column(
          'modified_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column('is_archived', sa.Boolean(), nullable=False),
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column(
          'type',
          sa.Enum(
              'DATA_CHECK_ROW',
              'DATA_CHECK_ROW_COUNT',
              'QUERY_CONTAINS',
              'TEXT_CONTAINS',
              'CHART_CHECK_TYPE',
              'LATENCY_MAX_MS',
              'LOOKER_QUERY_MATCH',
              name='assertiontype',
          ),
          nullable=False,
      ),
      sa.Column('weight', sa.Float(), nullable=False),
      sa.Column('params', sa.JSON(), nullable=False),
      sa.ForeignKeyConstraint(
          ['example_snapshot_id'],
          ['example_snapshots.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_assertion_snapshots_example_snapshot_id'),
      'assertion_snapshots',
      ['example_snapshot_id'],
      unique=False,
  )
  op.create_table(
      'assertions',
      sa.Column('example_id', sa.Integer(), nullable=False),
      sa.Column(
          'created_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column(
          'modified_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column('is_archived', sa.Boolean(), nullable=False),
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column(
          'type',
          sa.Enum(
              'DATA_CHECK_ROW',
              'DATA_CHECK_ROW_COUNT',
              'QUERY_CONTAINS',
              'TEXT_CONTAINS',
              'CHART_CHECK_TYPE',
              'LATENCY_MAX_MS',
              'LOOKER_QUERY_MATCH',
              name='assertiontype',
          ),
          nullable=False,
      ),
      sa.Column('weight', sa.Float(), nullable=False),
      sa.Column('params', sa.JSON(), nullable=False),
      sa.ForeignKeyConstraint(
          ['example_id'],
          ['examples.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_assertions_example_id'),
      'assertions',
      ['example_id'],
      unique=False,
  )
  op.create_table(
      'assertion_results',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('trial_id', sa.Integer(), nullable=False),
      sa.Column('assertion_snapshot_id', sa.Integer(), nullable=False),
      sa.Column('passed', sa.Boolean(), nullable=False),
      sa.Column('score', sa.Float(), nullable=False),
      sa.Column('reasoning', sa.Text(), nullable=True),
      sa.Column('error_message', sa.Text(), nullable=True),
      sa.Column(
          'created_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column(
          'modified_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column('is_archived', sa.Boolean(), nullable=False),
      sa.ForeignKeyConstraint(
          ['assertion_snapshot_id'],
          ['assertion_snapshots.id'],
      ),
      sa.ForeignKeyConstraint(
          ['trial_id'],
          ['trials.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_assertion_results_trial_id'),
      'assertion_results',
      ['trial_id'],
      unique=False,
  )
  op.create_table(
      'suggested_assertions',
      sa.Column('trial_id', sa.Integer(), nullable=False),
      sa.Column('reasoning', sa.Text(), nullable=True),
      sa.Column(
          'created_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column(
          'modified_at',
          sa.DateTime(timezone=True),
          server_default=sa.text('(CURRENT_TIMESTAMP)'),
          nullable=False,
      ),
      sa.Column('is_archived', sa.Boolean(), nullable=False),
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column(
          'type',
          sa.Enum(
              'DATA_CHECK_ROW',
              'DATA_CHECK_ROW_COUNT',
              'QUERY_CONTAINS',
              'TEXT_CONTAINS',
              'CHART_CHECK_TYPE',
              'LATENCY_MAX_MS',
              'LOOKER_QUERY_MATCH',
              name='assertiontype',
          ),
          nullable=False,
      ),
      sa.Column('weight', sa.Float(), nullable=False),
      sa.Column('params', sa.JSON(), nullable=False),
      sa.ForeignKeyConstraint(
          ['trial_id'],
          ['trials.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_suggested_assertions_trial_id'),
      'suggested_assertions',
      ['trial_id'],
      unique=False,
  )
  op.drop_column('example_snapshots', 'asserts')
  op.drop_column('trials', 'assertion_results')


def downgrade() -> None:
  # Both NOT NULL with a server default. Autogenerate wrote them against a
  # SQLite dialect and with no default, so the downgrade failed on any
  # database that had ever run a trial.
  op.add_column(
      'trials',
      sa.Column(
          'assertion_results',
          sa.JSON(),
          server_default=sa.text("'[]'"),
          nullable=False,
      ),
  )
  op.add_column(
      'example_snapshots',
      sa.Column(
          'asserts',
          sa.JSON(),
          server_default=sa.text("'[]'"),
          nullable=False,
      ),
  )
  op.drop_index(
      op.f('ix_suggested_assertions_trial_id'),
      table_name='suggested_assertions',
  )
  op.drop_table('suggested_assertions')
  op.drop_index(
      op.f('ix_assertion_results_trial_id'), table_name='assertion_results'
  )
  op.drop_table('assertion_results')
  op.drop_index(op.f('ix_assertions_example_id'), table_name='assertions')
  op.drop_table('assertions')
  op.drop_index(
      op.f('ix_assertion_snapshots_example_snapshot_id'),
      table_name='assertion_snapshots',
  )
  op.drop_table('assertion_snapshots')
  # drop_table takes no column arguments, so it emits no DROP TYPE. The type
  # outlived `downgrade base` and the next `upgrade head` died on
  # `type "assertiontype" already exists`. The three tables above are the only
  # users of it, so it goes once they are gone.
  op.execute('DROP TYPE IF EXISTS assertiontype')
