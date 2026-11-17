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
"""Add eval_schedules table and runs.schedule_id foreign key.

Revision ID: 9c41b2e8a710
Revises: f47a9c1e0b38
Create Date: 2026-10-30 16:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "9c41b2e8a710"
down_revision = "f47a9c1e0b38"
branch_labels = None
depends_on = None


def upgrade() -> None:
  """Creates eval_schedules table and adds runs.schedule_id foreign key."""
  op.create_table(
      "eval_schedules",
      sa.Column("id", sa.Integer(), nullable=False),
      sa.Column("name", sa.String(length=200), nullable=False),
      sa.Column("agent_id", sa.Integer(), nullable=False),
      sa.Column("test_suite_id", sa.Integer(), nullable=False),
      sa.Column(
          "cadence",
          sa.String(length=32),
          server_default="DAILY",
          nullable=False,
      ),
      sa.Column("cron_expression", sa.String(length=100), nullable=False),
      sa.Column(
          "timezone",
          sa.String(length=64),
          server_default="UTC",
          nullable=False,
      ),
      sa.Column(
          "generate_suggestions",
          sa.Boolean(),
          server_default=sa.sql.expression.false(),
          nullable=False,
      ),
      sa.Column(
          "concurrency", sa.Integer(), server_default="2", nullable=False
      ),
      sa.Column(
          "is_enabled",
          sa.Boolean(),
          server_default=sa.sql.expression.true(),
          nullable=False,
      ),
      sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
      sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
      sa.Column("last_run_id", sa.Integer(), nullable=True),
      sa.Column("last_error_message", sa.Text(), nullable=True),
      sa.Column(
          "dispatch_started_at", sa.DateTime(timezone=True), nullable=True
      ),
      sa.Column(
          "created_at",
          sa.DateTime(timezone=True),
          server_default=sa.func.now(),
          nullable=False,
      ),
      sa.Column(
          "modified_at",
          sa.DateTime(timezone=True),
          server_default=sa.func.now(),
          nullable=False,
      ),
      sa.Column("is_archived", sa.Boolean(), nullable=False),
      sa.ForeignKeyConstraint(["agent_id"], ["agents.id"]),
      sa.ForeignKeyConstraint(["test_suite_id"], ["test_suites.id"]),
      sa.PrimaryKeyConstraint("id"),
  )
  op.create_index(
      "ix_eval_schedules_agent_id",
      "eval_schedules",
      ["agent_id"],
      unique=False,
  )
  op.create_index(
      "ix_eval_schedules_test_suite_id",
      "eval_schedules",
      ["test_suite_id"],
      unique=False,
  )
  op.create_index(
      "ix_eval_schedules_due",
      "eval_schedules",
      ["is_enabled", "is_archived", "next_run_at"],
      unique=False,
  )

  op.add_column("runs", sa.Column("schedule_id", sa.Integer(), nullable=True))
  op.create_foreign_key(
      "fk_runs_schedule_id_eval_schedules",
      "runs",
      "eval_schedules",
      ["schedule_id"],
      ["id"],
      ondelete="SET NULL",
  )
  op.create_index("ix_runs_schedule_id", "runs", ["schedule_id"], unique=False)


def downgrade() -> None:
  """Drops runs.schedule_id foreign key and eval_schedules table."""
  op.drop_index("ix_runs_schedule_id", table_name="runs")
  op.drop_constraint(
      "fk_runs_schedule_id_eval_schedules", "runs", type_="foreignkey"
  )
  op.drop_column("runs", "schedule_id")
  op.drop_index("ix_eval_schedules_due", table_name="eval_schedules")
  op.drop_index("ix_eval_schedules_test_suite_id", table_name="eval_schedules")
  op.drop_index("ix_eval_schedules_agent_id", table_name="eval_schedules")
  op.drop_table("eval_schedules")
