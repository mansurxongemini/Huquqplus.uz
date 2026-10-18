"""ai answer rating, rag answer id and per-section auto-answer settings

Revision ID: j6e7f8a9b0c1
Revises: i5d6e7f8a9b0
Create Date: 2026-10-18 00:00:00.000000
"""
from alembic import op, context
import sqlalchemy as sa

revision = 'j6e7f8a9b0c1'
down_revision = 'i5d6e7f8a9b0'
branch_labels = None
depends_on = None

NEW_COLUMNS = [
    sa.Column('rag_answer_id', sa.VARCHAR(length=64), nullable=True),
    sa.Column('rating', sa.Integer(), nullable=True),
    sa.Column('rated_at', sa.DateTime(), nullable=True),
]


def _create_settings():
    op.create_table(
        'tg_bot_ai_section_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('section_name', sa.VARCHAR(length=255), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('updated_by', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tg_bot_ai_section_settings_section_name'), 'tg_bot_ai_section_settings', ['section_name'], unique=True)


def upgrade():
    if context.is_offline_mode():
        for col in NEW_COLUMNS:
            op.add_column('tg_bot_ai_answers', col.copy())
        _create_settings()
        return
    inspector = sa.inspect(op.get_bind())
    existing = [c['name'] for c in inspector.get_columns('tg_bot_ai_answers')]
    for col in NEW_COLUMNS:
        if col.name not in existing:
            op.add_column('tg_bot_ai_answers', col.copy())
    if 'tg_bot_ai_section_settings' not in inspector.get_table_names():
        _create_settings()


def downgrade():
    op.drop_index(op.f('ix_tg_bot_ai_section_settings_section_name'), table_name='tg_bot_ai_section_settings')
    op.drop_table('tg_bot_ai_section_settings')
    for col in reversed(NEW_COLUMNS):
        op.drop_column('tg_bot_ai_answers', col.name)
