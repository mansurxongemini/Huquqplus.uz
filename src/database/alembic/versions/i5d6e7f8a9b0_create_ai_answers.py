"""create ai answers table and inquiries.from_ai_answer_id

Revision ID: i5d6e7f8a9b0
Revises: h4c5d6e7f8a9
Create Date: 2026-10-18 00:00:00.000000

Fuqaroning oddiy savollariga berilgan avtomatik javoblar va ulardan qoniqmay
huquqshunosga o'tgan murojaatlar bog'lanishi.
"""
from alembic import op, context
import sqlalchemy as sa

revision = 'i5d6e7f8a9b0'
down_revision = 'h4c5d6e7f8a9'
branch_labels = None
depends_on = None


def _create_table():
    op.create_table(
        'tg_bot_ai_answers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('section_name', sa.VARCHAR(length=255), nullable=True),
        sa.Column('group_id', sa.VARCHAR(length=255), nullable=True),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('private_question_id', sa.Integer(), nullable=True),
        sa.Column('answer_html', sa.Text(), nullable=False),
        sa.Column('review_confidence', sa.Float(), nullable=True),
        sa.Column('escalated_inquiry_id', sa.Integer(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tg_bot_ai_answers_user_id'), 'tg_bot_ai_answers', ['user_id'], unique=False)
    op.create_index(op.f('ix_tg_bot_ai_answers_escalated_inquiry_id'), 'tg_bot_ai_answers', ['escalated_inquiry_id'], unique=False)
    op.create_index(op.f('ix_tg_bot_ai_answers_created_at'), 'tg_bot_ai_answers', ['created_at'], unique=False)


def _add_column():
    op.add_column('tg_bot_inquiries', sa.Column('from_ai_answer_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_tg_bot_inquiries_from_ai_answer_id'), 'tg_bot_inquiries', ['from_ai_answer_id'], unique=False)


def upgrade():
    if context.is_offline_mode():
        _create_table()
        _add_column()
        return
    inspector = sa.inspect(op.get_bind())
    if 'tg_bot_ai_answers' not in inspector.get_table_names():
        _create_table()
    if 'from_ai_answer_id' not in [c['name'] for c in inspector.get_columns('tg_bot_inquiries')]:
        _add_column()


def downgrade():
    op.drop_index(op.f('ix_tg_bot_inquiries_from_ai_answer_id'), table_name='tg_bot_inquiries')
    op.drop_column('tg_bot_inquiries', 'from_ai_answer_id')
    op.drop_index(op.f('ix_tg_bot_ai_answers_created_at'), table_name='tg_bot_ai_answers')
    op.drop_index(op.f('ix_tg_bot_ai_answers_escalated_inquiry_id'), table_name='tg_bot_ai_answers')
    op.drop_index(op.f('ix_tg_bot_ai_answers_user_id'), table_name='tg_bot_ai_answers')
    op.drop_table('tg_bot_ai_answers')
