"""add citizen_notice_message_id to appointments

Revision ID: h4c5d6e7f8a9
Revises: g3b4c5d6e7f8
Create Date: 2026-10-18 00:00:00.000000

Fuqaroga yuborilgan oxirgi qabul xabarnomasini o'chirish uchun citizen_notice_message_id ustuni.
"""
from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'h4c5d6e7f8a9'
down_revision = 'g3b4c5d6e7f8'
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        op.add_column('tg_bot_appointments', sa.Column('citizen_notice_message_id', sa.BigInteger(), nullable=True))
        return
    inspector = sa.inspect(op.get_bind())
    if 'tg_bot_appointments' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('tg_bot_appointments')]
        if 'citizen_notice_message_id' not in cols:
            op.add_column('tg_bot_appointments', sa.Column('citizen_notice_message_id', sa.BigInteger(), nullable=True))


def downgrade():
    if context.is_offline_mode():
        op.drop_column('tg_bot_appointments', 'citizen_notice_message_id')
        return
    inspector = sa.inspect(op.get_bind())
    if 'tg_bot_appointments' in inspector.get_table_names():
        cols = [c['name'] for c in inspector.get_columns('tg_bot_appointments')]
        if 'citizen_notice_message_id' in cols:
            op.drop_column('tg_bot_appointments', 'citizen_notice_message_id')
