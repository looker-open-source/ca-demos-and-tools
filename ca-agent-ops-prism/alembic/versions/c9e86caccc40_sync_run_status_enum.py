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

"""sync_run_status_enum

Revision ID: c9e86caccc40
Revises: 125b06883c8d
Create Date: 2026-01-15 21:41:32.532205
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = 'c9e86caccc40'
down_revision = '125b06883c8d'
branch_labels = None
depends_on = None


def upgrade() -> None:
  # IF NOT EXISTS keeps this rerunnable against a database that already has
  # the values.
  #
  # This used to COMMIT first, to get ALTER TYPE out of a transaction block.
  # Postgres 12 allows it inside one as long as the new label is not used in
  # the same transaction, and nothing here uses them. The COMMIT also ended
  # the transaction for every later revision in the same upgrade, so a
  # failure after this point could not be rolled back.
  for value in ['EXECUTING', 'EVALUATING', 'PAUSED']:
    op.execute(f"ALTER TYPE runstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
  # PostgreSQL doesn't easily support removing enum values.
  pass
