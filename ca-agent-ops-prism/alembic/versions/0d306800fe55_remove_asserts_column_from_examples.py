"""remove_asserts_column_from_examples

Revision ID: 0d306800fe55
Revises: a26b5bc93f48
Create Date: 2026-01-02 20:26:15.803470
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0d306800fe55'
down_revision = 'a26b5bc93f48'
branch_labels = None
depends_on = None


def upgrade() -> None:
  # Drop the 'asserts' column from 'examples' table
  with op.batch_alter_table('examples') as batch_op:
    batch_op.drop_column('asserts')


def downgrade() -> None:
  # Re-add the 'asserts' column to 'examples' table
  with op.batch_alter_table('examples') as batch_op:
    batch_op.add_column(sa.Column('asserts', sa.JSON(), nullable=True))
