"""appointment attendance confirmation by citizen

Revision ID: l8a9b0c1d2e3
Revises: k7f8a9b0c1d2
Create Date: 2026-10-18 00:00:00.000000
"""
from alembic import op, context
import sqlalchemy as sa

revision = 'l8a9b0c1d2e3'
down_revision = 'k7f8a9b0c1d2'
branch_labels = None
depends_on = None

COLUMNS = [
    sa.Column('confirm_asked_at', sa.DateTime(), nullable=True),
    sa.Column('citizen_confirmation', sa.VARCHAR(length=10), nullable=True),
]


def upgrade():
    existing = [] if context.is_offline_mode() else [
        c['name'] for c in sa.inspect(op.get_bind()).get_columns('tg_bot_appointments')]
    for col in COLUMNS:
        if col.name not in existing:
            op.add_column('tg_bot_appointments', col.copy())


def downgrade():
    for col in reversed(COLUMNS):
        op.drop_column('tg_bot_appointments', col.name)
