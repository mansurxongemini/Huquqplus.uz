"""add_inquiry_id_to_appointments

Revision ID: a1b2c3d4e5f7
Revises: f1b2c3d4e5f6
Create Date: 2026-09-21 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f7'
down_revision = 'f1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tg_bot_appointments')]
    if 'inquiry_id' not in columns:
        op.add_column('tg_bot_appointments', sa.Column('inquiry_id', sa.Integer(), nullable=True))

    indices = [ix['name'] for ix in inspector.get_indexes('tg_bot_appointments')]
    ix_name = op.f('ix_tg_bot_appointments_inquiry_id')
    if ix_name not in indices and 'ix_tg_bot_appointments_inquiry_id' not in indices:
        try:
            op.create_index(ix_name, 'tg_bot_appointments', ['inquiry_id'], unique=False)
        except Exception:
            pass


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('tg_bot_appointments')]
    if 'inquiry_id' in columns:
        try:
            op.drop_index(op.f('ix_tg_bot_appointments_inquiry_id'), table_name='tg_bot_appointments')
        except Exception:
            pass
        op.drop_column('tg_bot_appointments', 'inquiry_id')
