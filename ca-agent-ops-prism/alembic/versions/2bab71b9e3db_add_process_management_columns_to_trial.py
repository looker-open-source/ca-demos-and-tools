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

"""add_process_management_columns_to_trial

Revision ID: 2bab71b9e3db
Revises: 5bfcd38eae39
Create Date: 2026-01-25 22:38:57.175532
"""

# revision identifiers, used by Alembic.
revision = '2bab71b9e3db'
down_revision = '5bfcd38eae39'
branch_labels = None
depends_on = None


def upgrade():
  # Empty. The columns are added by 2ef9abb9e513, which skips any that the
  # table already has.
  pass


def downgrade():
  pass
