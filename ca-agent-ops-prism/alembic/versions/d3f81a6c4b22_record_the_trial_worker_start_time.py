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
"""Record the start time of a trial's worker process next to its PID.

A PID on its own is not process identity. A container restart gives the worker
a fresh PID namespace, so its new children land on the PIDs the trials claimed
before the restart recorded. Those trials read as alive, held their run's
capacity for the full 30 minute timeout, and the kill that followed landed on
whatever healthy trial owned the PID by then. This column holds psutil's
create_time() for the process in trials.trial_pid, which tells a recycled PID
apart from the real one.

Revision ID: d3f81a6c4b22
Revises: 4f1c0a9d7b32
Create Date: 2026-09-19 09:41:26.503118
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd3f81a6c4b22'
down_revision = '4f1c0a9d7b32'
branch_labels = None
depends_on = None


def upgrade() -> None:
  op.add_column(
      'trials', sa.Column('trial_pid_started_at', sa.Float(), nullable=True)
  )


def downgrade() -> None:
  op.drop_column('trials', 'trial_pid_started_at')
