"""create bot admins table

Revision ID: g3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-10-18 00:00:00.000000

Admin panel orqali Telegram ID bilan qo'shiladigan adminlar jadvali.
"""
from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'g3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def _create():
    op.create_table(
        'tg_bot_bot_admins',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('added_by', sa.BigInteger(), nullable=True),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('removed_by', sa.BigInteger(), nullable=True),
        sa.Column('removed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tg_bot_bot_admins_user_id'), 'tg_bot_bot_admins', ['user_id'], unique=True)
    op.create_index(op.f('ix_tg_bot_bot_admins_is_active'), 'tg_bot_bot_admins', ['is_active'], unique=False)


def upgrade():
    if context.is_offline_mode():
        _create()
        return
    inspector = sa.inspect(op.get_bind())
    if 'tg_bot_bot_admins' not in inspector.get_table_names():
        _create()


def downgrade():
    if context.is_offline_mode():
        op.drop_index(op.f('ix_tg_bot_bot_admins_is_active'), table_name='tg_bot_bot_admins')
        op.drop_index(op.f('ix_tg_bot_bot_admins_user_id'), table_name='tg_bot_bot_admins')
        op.drop_table('tg_bot_bot_admins')
        return
    inspector = sa.inspect(op.get_bind())
    if 'tg_bot_bot_admins' in inspector.get_table_names():
        op.drop_index(op.f('ix_tg_bot_bot_admins_is_active'), table_name='tg_bot_bot_admins')
        op.drop_index(op.f('ix_tg_bot_bot_admins_user_id'), table_name='tg_bot_bot_admins')
        op.drop_table('tg_bot_bot_admins')
