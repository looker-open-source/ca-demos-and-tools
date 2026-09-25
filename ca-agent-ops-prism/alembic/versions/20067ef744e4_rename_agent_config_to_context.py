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

"""rename_agent_config_to_context

Revision ID: 20067ef744e4
Revises: 827a40689071
Create Date: 2026-01-06 16:25:46.291327
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '20067ef744e4'
down_revision = '827a40689071'
branch_labels = None
depends_on = None


def upgrade() -> None:
  with op.batch_alter_table('runs', schema=None) as batch_op:
    batch_op.alter_column(
        'agent_config_snapshot', new_column_name='agent_context_snapshot'
    )


def downgrade() -> None:
  with op.batch_alter_table('runs', schema=None) as batch_op:
    batch_op.alter_column(
        'agent_context_snapshot', new_column_name='agent_config_snapshot'
    )
