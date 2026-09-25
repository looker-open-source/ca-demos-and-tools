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

"""add_execution_engine.

Revision ID: e4761fe3887b
Revises:
Create Date: 2025-12-29 23:50:12.818053
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e4761fe3887b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.create_table(
      'agents',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('name', sa.String(), nullable=False),
      sa.Column('project_id', sa.String(), nullable=False),
      sa.Column('location', sa.String(), nullable=False),
      sa.Column('agent_resource_id', sa.String(), nullable=False),
      sa.Column(
          'env',
          sa.Enum('STAGING', 'PUBLISHED', name='agentenv'),
          nullable=False,
      ),
      sa.Column('datasource_config', sa.JSON(), nullable=True),
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
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_table(
      'test_suite_snapshots',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('original_suite_id', sa.Integer(), nullable=True),
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
      sa.Column('name', sa.String(), nullable=False),
      sa.Column('description', sa.Text(), nullable=True),
      sa.Column('tags', sa.JSON(), nullable=False),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_test_suite_snapshots_original_suite_id'),
      'test_suite_snapshots',
      ['original_suite_id'],
      unique=False,
  )
  op.create_table(
      'test_suites',
      sa.Column('id', sa.Integer(), nullable=False),
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
      sa.Column('name', sa.String(), nullable=False),
      sa.Column('description', sa.Text(), nullable=True),
      sa.Column('tags', sa.JSON(), nullable=False),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_table(
      'example_snapshots',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('snapshot_suite_id', sa.Integer(), nullable=False),
      sa.Column('original_example_id', sa.Integer(), nullable=True),
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
      sa.Column('logical_id', sa.String(), nullable=False),
      sa.Column('question', sa.Text(), nullable=False),
      sa.Column('asserts', sa.JSON(), nullable=False),
      sa.ForeignKeyConstraint(
          ['snapshot_suite_id'],
          ['test_suite_snapshots.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_example_snapshots_logical_id'),
      'example_snapshots',
      ['logical_id'],
      unique=False,
  )
  op.create_index(
      op.f('ix_example_snapshots_original_example_id'),
      'example_snapshots',
      ['original_example_id'],
      unique=False,
  )
  op.create_table(
      'examples',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('test_suite_id', sa.Integer(), nullable=False),
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
      sa.Column('logical_id', sa.String(), nullable=False),
      sa.Column('question', sa.Text(), nullable=False),
      sa.Column('asserts', sa.JSON(), nullable=False),
      sa.ForeignKeyConstraint(
          ['test_suite_id'],
          ['test_suites.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(
      op.f('ix_examples_logical_id'), 'examples', ['logical_id'], unique=False
  )
  op.create_table(
      'runs',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('test_suite_snapshot_id', sa.Integer(), nullable=False),
      sa.Column('agent_id', sa.Integer(), nullable=False),
      sa.Column('agent_config_snapshot', sa.JSON(), nullable=True),
      sa.Column(
          'status',
          sa.Enum(
              'PENDING',
              'RUNNING',
              'COMPLETED',
              'FAILED',
              'CANCELLED',
              name='runstatus',
          ),
          nullable=False,
      ),
      sa.Column('started_at', sa.DateTime(), nullable=True),
      sa.Column('completed_at', sa.DateTime(), nullable=True),
      sa.Column('total_examples', sa.Integer(), nullable=False),
      sa.Column('passed_examples', sa.Integer(), nullable=False),
      sa.Column('failed_examples', sa.Integer(), nullable=False),
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
          ['agent_id'],
          ['agents.id'],
      ),
      sa.ForeignKeyConstraint(
          ['test_suite_snapshot_id'],
          ['test_suite_snapshots.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_table(
      'trials',
      sa.Column('id', sa.Integer(), nullable=False),
      sa.Column('run_id', sa.Integer(), nullable=False),
      sa.Column('example_snapshot_id', sa.Integer(), nullable=False),
      sa.Column(
          'status',
          sa.Enum(
              'PENDING',
              'RUNNING',
              'COMPLETED',
              'FAILED',
              'CANCELLED',
              name='runstatus',
          ),
          nullable=False,
      ),
      sa.Column('started_at', sa.DateTime(), nullable=True),
      sa.Column('completed_at', sa.DateTime(), nullable=True),
      sa.Column('output_text', sa.Text(), nullable=True),
      sa.Column('error_message', sa.Text(), nullable=True),
      sa.Column('trace_results', sa.JSON(), nullable=True),
      sa.Column('score', sa.Float(), nullable=True),
      sa.Column('assertion_results', sa.JSON(), nullable=False),
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
          ['example_snapshot_id'],
          ['example_snapshots.id'],
      ),
      sa.ForeignKeyConstraint(
          ['run_id'],
          ['runs.id'],
      ),
      sa.PrimaryKeyConstraint('id'),
  )
  op.create_index(op.f('ix_trials_run_id'), 'trials', ['run_id'], unique=False)


def downgrade() -> None:
  op.drop_index(op.f('ix_trials_run_id'), table_name='trials')
  op.drop_table('trials')
  op.drop_table('runs')
  op.drop_index(op.f('ix_examples_logical_id'), table_name='examples')
  op.drop_table('examples')
  op.drop_index(
      op.f('ix_example_snapshots_original_example_id'),
      table_name='example_snapshots',
  )
  op.drop_index(
      op.f('ix_example_snapshots_logical_id'), table_name='example_snapshots'
  )
  op.drop_table('example_snapshots')
  op.drop_table('test_suites')
  op.drop_index(
      op.f('ix_test_suite_snapshots_original_suite_id'),
      table_name='test_suite_snapshots',
  )
  op.drop_table('test_suite_snapshots')
  op.drop_table('agents')
  # drop_table emits no DROP TYPE, because it is given no column arguments to
  # read the enum off. Both types outlived `downgrade base` and the next
  # `upgrade head` died here on `type "runstatus" already exists`.
  #
  # agentenv is dropped here rather than in 8c6080c6545f, which drops the
  # column. That revision's downgrade adds the column back and alembic does
  # not re-create the type for it, so the type has to survive until the table
  # itself goes.
  op.execute('DROP TYPE IF EXISTS runstatus')
  op.execute('DROP TYPE IF EXISTS agentenv')
