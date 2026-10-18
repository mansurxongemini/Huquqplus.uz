"""add_language_to_required_channels

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-02 19:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'tg_bot_required_channels' in tables:
        columns = [c['name'] for c in inspector.get_columns('tg_bot_required_channels')]
        if 'language' not in columns:
            op.add_column(
                'tg_bot_required_channels',
                sa.Column('language', sa.VARCHAR(length=10), nullable=False, server_default='all')
            )
            op.create_index(
                op.f('ix_tg_bot_required_channels_language'),
                'tg_bot_required_channels',
                ['language'],
                unique=False
            )


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'tg_bot_required_channels' in tables:
        columns = [c['name'] for c in inspector.get_columns('tg_bot_required_channels')]
        if 'language' in columns:
            try:
                op.drop_index(op.f('ix_tg_bot_required_channels_language'), table_name='tg_bot_required_channels')
            except Exception:
                pass
            op.drop_column('tg_bot_required_channels', 'language')
