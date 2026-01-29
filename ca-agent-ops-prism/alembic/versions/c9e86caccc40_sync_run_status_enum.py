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
  # PostgreSQL doesn't allow adding enum values within a transaction easily in older versions,
  # but we can use ALTER TYPE.
  # We use a trick to make it idempotent.
  op.execute(
      'COMMIT'
  )  # ALTER TYPE ... ADD VALUE cannot run in a transaction block
  for value in ['EXECUTING', 'EVALUATING', 'PAUSED']:
    op.execute(f"ALTER TYPE runstatus ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
  # PostgreSQL doesn't easily support removing enum values.
  pass
