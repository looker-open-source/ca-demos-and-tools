"""add_baseline_data_match_to_assertiontype_enum

Revision ID: 10b0ee94ea81
Revises: 53caba6952b0
Create Date: 2026-04-12 14:42:44.997285

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '10b0ee94ea81'
down_revision = '53caba6952b0'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL doesn't allow using new enum values in the same transaction
    # they are created. We add them here; no data migration needed.
    op.execute("ALTER TYPE assertiontype ADD VALUE 'BASELINE_DATA_MATCH'")
    op.execute("ALTER TYPE assertiontype ADD VALUE 'QUERY_BASELINE_DATA_MATCH'")


def downgrade():
    # Reverting enum values in PostgreSQL requires recreating the type; skip.
    pass
