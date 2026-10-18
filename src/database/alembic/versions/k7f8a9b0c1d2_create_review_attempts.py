"""create review attempts history

Revision ID: k7f8a9b0c1d2
Revises: j6e7f8a9b0c1
Create Date: 2026-10-18 00:00:00.000000
"""
from alembic import op, context
import sqlalchemy as sa

revision = 'k7f8a9b0c1d2'
down_revision = 'j6e7f8a9b0c1'
branch_labels = None
depends_on = None


def _create():
    op.create_table(
        'tg_bot_review_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=True),
        sa.Column('inquiry_id', sa.Integer(), nullable=False),
        sa.Column('volunteer_user_id', sa.BigInteger(), nullable=False),
        sa.Column('verdict', sa.VARCHAR(length=20), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('scores_json', sa.Text(), nullable=True),
        sa.Column('issue_types', sa.VARCHAR(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    for col in ('assignment_id', 'inquiry_id', 'volunteer_user_id', 'created_at'):
        op.create_index(op.f(f'ix_tg_bot_review_attempts_{col}'), 'tg_bot_review_attempts', [col], unique=False)


def upgrade():
    if context.is_offline_mode():
        _create()
        return
    if 'tg_bot_review_attempts' not in sa.inspect(op.get_bind()).get_table_names():
        _create()


def downgrade():
    for col in ('assignment_id', 'inquiry_id', 'volunteer_user_id', 'created_at'):
        op.drop_index(op.f(f'ix_tg_bot_review_attempts_{col}'), table_name='tg_bot_review_attempts')
    op.drop_table('tg_bot_review_attempts')
