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

# pylint: disable=invalid-name
"""Normalize agent locations.

Revision ID: 87d5db0c5bc2
Revises: 53caba6952b0
Create Date: 2026-09-11 20:57:47.830702
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = '87d5db0c5bc2'
down_revision = '53caba6952b0'
branch_labels = None
depends_on = None


def upgrade():
  op.alter_column('agents', 'location', server_default='global')
  op.execute(
      "UPDATE agents SET location = 'global' WHERE location = '' OR location"
      ' IS NULL'
  )
  op.execute('UPDATE agents SET location = LOWER(TRIM(location))')


def downgrade():
  op.alter_column('agents', 'location', server_default=None)
