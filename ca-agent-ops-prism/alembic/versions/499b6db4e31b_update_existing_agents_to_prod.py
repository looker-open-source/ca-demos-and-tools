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

"""Update existing agents to PROD

Revision ID: 499b6db4e31b
Revises: e4c85eb95572
Create Date: 2026-01-22 02:09:55.546219
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "499b6db4e31b"
down_revision = "e4c85eb95572"
branch_labels = None
depends_on = None


def upgrade() -> None:
  # The previous revision added PROD and committed at its own boundary, so
  # this UPDATE can reference it.
  op.execute("UPDATE agents SET env = 'PROD' WHERE env = 'PUBLISHED'")


def downgrade() -> None:
  op.execute("UPDATE agents SET env = 'PUBLISHED' WHERE env = 'PROD'")
