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

"""Rename latency to duration in playground_traces

Revision ID: 125b06883c8d
Revises: ed2ab69fa339
Create Date: 2026-01-14 15:53:05.878139
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '125b06883c8d'
down_revision = 'ed2ab69fa339'
branch_labels = None
depends_on = None


def upgrade() -> None:
  with op.batch_alter_table('playground_traces', schema=None) as batch_op:
    batch_op.alter_column('latency_ms', new_column_name='duration_ms')


def downgrade() -> None:
  with op.batch_alter_table('playground_traces', schema=None) as batch_op:
    batch_op.alter_column('duration_ms', new_column_name='latency_ms')
