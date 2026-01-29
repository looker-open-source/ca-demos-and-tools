"""Add AI_JUDGE and DURATION_MAX_MS to assertiontype enum

Revision ID: 7d75673c8561
Revises: 499b6db4e31b
Create Date: 2026-01-22 02:31:40.160113

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '7d75673c8561'
down_revision = '499b6db4e31b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL doesn't allow using new enum values in the same transaction
    # they are created. We'll add them here and update values separately.
    op.execute("ALTER TYPE assertiontype ADD VALUE 'AI_JUDGE'")
    op.execute("ALTER TYPE assertiontype ADD VALUE 'DURATION_MAX_MS'")


def downgrade() -> None:
    # Reverting enum changes is not straightforward in PG.
    pass
