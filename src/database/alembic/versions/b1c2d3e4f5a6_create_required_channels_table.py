"""create_required_channels_table

Revision ID: b1c2d3e4f5a6
Revises: a1b2c3d4e5f7
Create Date: 2026-09-22 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1c2d3e4f5a6'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'tg_bot_required_channels' not in tables:
        op.create_table(
            'tg_bot_required_channels',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
            sa.Column('channel_id', sa.VARCHAR(length=100), nullable=False),
            sa.Column('channel_name', sa.VARCHAR(length=255), nullable=False),
            sa.Column('invite_link', sa.VARCHAR(length=500), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_tg_bot_required_channels_channel_id'), 'tg_bot_required_channels', ['channel_id'], unique=True)
        op.create_index(op.f('ix_tg_bot_required_channels_is_active'), 'tg_bot_required_channels', ['is_active'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'tg_bot_required_channels' in tables:
        op.drop_table('tg_bot_required_channels')
