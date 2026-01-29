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
  # they are created. We'll add them here and update values separately.
  op.execute("COMMIT")
  op.execute("ALTER TYPE agentenv ADD VALUE IF NOT EXISTS 'PROD'")
  op.execute("ALTER TYPE agentenv ADD VALUE IF NOT EXISTS 'AUTOPUSH'")
  op.execute("COMMIT")


def downgrade() -> None:
    # Reverting enum changes is not straightforward in PG.
    pass
