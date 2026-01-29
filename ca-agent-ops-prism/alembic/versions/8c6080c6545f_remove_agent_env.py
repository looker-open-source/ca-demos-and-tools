"""Remove agent_env

Revision ID: 8c6080c6545f
Revises: 2ef9abb9e513
Create Date: 2026-01-29 02:56:25.555314
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '8c6080c6545f'
down_revision = '2ef9abb9e513'
branch_labels = None
depends_on = None


def upgrade():
  op.drop_column('agents', 'env')


def downgrade():
  from sqlalchemy.dialects import postgresql

  op.add_column(
      'agents',
      sa.Column(
          'env',
          postgresql.ENUM(
              'STAGING', 'PUBLISHED', 'PROD', 'AUTOPUSH', name='agentenv'
          ),
          autoincrement=False,
          nullable=False,
      ),
  )
