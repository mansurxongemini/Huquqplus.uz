"""add language and blocking fields to user

Revision ID: e1a2b3c4d5e6
Revises: 496add647bec
Create Date: 2026-09-12 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5e6'
down_revision = '496add647bec'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tg_bot_users', sa.Column('language', sa.String(length=10), server_default='uz', nullable=False))
    op.add_column('tg_bot_users', sa.Column('is_blocked', sa.Boolean(), server_default='0', nullable=False))
    op.add_column('tg_bot_users', sa.Column('blocked_at', sa.DateTime(), nullable=True))
    op.add_column('tg_bot_users', sa.Column('blocked_by', sa.BigInteger(), nullable=True))
    op.add_column('tg_bot_users', sa.Column('block_reason', sa.String(length=255), nullable=True))


def downgrade():
    op.drop_column('tg_bot_users', 'block_reason')
    op.drop_column('tg_bot_users', 'blocked_by')
    op.drop_column('tg_bot_users', 'blocked_at')
    op.drop_column('tg_bot_users', 'is_blocked')
    op.drop_column('tg_bot_users', 'language')
