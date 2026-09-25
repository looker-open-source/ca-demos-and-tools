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

"""Sync agentenv enum values

Revision ID: e4c85eb95572
Revises: c9e86caccc40
Create Date: 2026-01-22 02:09:02.746106
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "e4c85eb95572"
down_revision = "c9e86caccc40"
branch_labels = None
depends_on = None


def upgrade() -> None:
  # PostgreSQL doesn't allow using new enum values in the same transaction
  # they are created, so the UPDATE that needs PROD is its own revision. With
  # transaction_per_migration in env.py that revision starts after this one
  # commits, which is what the bare COMMITs here used to arrange by hand.
  op.execute("ALTER TYPE agentenv ADD VALUE IF NOT EXISTS 'PROD'")
  op.execute("ALTER TYPE agentenv ADD VALUE IF NOT EXISTS 'AUTOPUSH'")


def downgrade() -> None:
  # PostgreSQL has no way to drop a value from an enum type.
  pass
