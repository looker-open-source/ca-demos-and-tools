"""Update existing agents to PROD

Revision ID: 499b6db4e31b
Revises: e4c85eb95572
Create Date: 2026-01-22 02:09:55.546219

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "499b6db4e31b"
down_revision = "e4c85eb95572"
branch_labels = None
depends_on = None


def upgrade() -> None:
  # Now that PROD value is committed, we can safely use it.
  op.execute("COMMIT")
  op.execute("UPDATE agents SET env = 'PROD' WHERE env = 'PUBLISHED'")


def downgrade() -> None:
    # Revert PROD back to PUBLISHED if needed
    op.execute("UPDATE agents SET env = 'PUBLISHED' WHERE env = 'PROD'")
