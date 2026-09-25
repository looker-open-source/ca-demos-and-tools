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

"""Add AI_JUDGE and DURATION_MAX_MS to assertiontype enum

Revision ID: 7d75673c8561
Revises: 499b6db4e31b
Create Date: 2026-01-22 02:31:40.160113
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7d75673c8561"
down_revision = "499b6db4e31b"
branch_labels = None
depends_on = None


def upgrade() -> None:
  # PostgreSQL doesn't allow using new enum values in the same transaction
  # they are created, so this migration only adds them.
  #
  # IF NOT EXISTS because the downgrade cannot take a label back out. Without
  # it, downgrading below this revision and upgrading again failed on the
  # duplicate label and left the database unable to reach head.
  op.execute("ALTER TYPE assertiontype ADD VALUE IF NOT EXISTS 'AI_JUDGE'")
  op.execute(
      "ALTER TYPE assertiontype ADD VALUE IF NOT EXISTS 'DURATION_MAX_MS'"
  )


def downgrade() -> None:
  # PostgreSQL has no way to drop a value from an enum type.
  pass
