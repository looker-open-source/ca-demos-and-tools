"""Add generate_suggestions to Run

Revision ID: a22be0585aee
Revises: 8c6080c6545f
Create Date: 2026-02-13 16:00:29.876634
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a22be0585aee'
down_revision = '8c6080c6545f'
branch_labels = None
depends_on = None


def upgrade():
  op.add_column(
      'runs',
      sa.Column(
          'generate_suggestions',
          sa.Boolean(),
          server_default=sa.text('false'),
          nullable=False,
      ),
  )


def downgrade():
  op.drop_column('runs', 'generate_suggestions')
