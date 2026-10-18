"""add_guide_keywords_and_inquiry_benefit_id

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-10-06 17:00:00.000000

"""
from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e2f3a4b5c6d7'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        op.add_column('tg_bot_benefits', sa.Column('guide_uz', sa.Text(), nullable=True))
        op.add_column('tg_bot_benefits', sa.Column('guide_oz', sa.Text(), nullable=True))
        op.add_column('tg_bot_benefits', sa.Column('guide_ru', sa.Text(), nullable=True))
        op.add_column('tg_bot_benefits', sa.Column('mygov_url', sa.VARCHAR(length=500), nullable=True))
        op.add_column('tg_bot_benefits', sa.Column('lex_url', sa.VARCHAR(length=500), nullable=True))
        op.add_column('tg_bot_benefits', sa.Column('keywords', sa.Text(), nullable=True))

        op.add_column('tg_bot_inquiries', sa.Column('benefit_id', sa.Integer(), nullable=True))
        op.create_foreign_key(
            'fk_tg_bot_inquiries_benefit_id_tg_bot_benefits',
            'tg_bot_inquiries', 'tg_bot_benefits',
            ['benefit_id'], ['id'],
            ondelete='SET NULL'
        )
        op.create_index(op.f('ix_tg_bot_inquiries_benefit_id'), 'tg_bot_inquiries', ['benefit_id'], unique=False)
        return

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Add columns to tg_bot_benefits
    if 'tg_bot_benefits' in tables:
        benefit_cols = [c['name'] for c in inspector.get_columns('tg_bot_benefits')]
        if 'guide_uz' not in benefit_cols:
            op.add_column('tg_bot_benefits', sa.Column('guide_uz', sa.Text(), nullable=True))
        if 'guide_oz' not in benefit_cols:
            op.add_column('tg_bot_benefits', sa.Column('guide_oz', sa.Text(), nullable=True))
        if 'guide_ru' not in benefit_cols:
            op.add_column('tg_bot_benefits', sa.Column('guide_ru', sa.Text(), nullable=True))
        if 'mygov_url' not in benefit_cols:
            op.add_column('tg_bot_benefits', sa.Column('mygov_url', sa.VARCHAR(length=500), nullable=True))
        if 'lex_url' not in benefit_cols:
            op.add_column('tg_bot_benefits', sa.Column('lex_url', sa.VARCHAR(length=500), nullable=True))
        if 'keywords' not in benefit_cols:
            op.add_column('tg_bot_benefits', sa.Column('keywords', sa.Text(), nullable=True))

    # 2. Add benefit_id and foreign key to tg_bot_inquiries
    if 'tg_bot_inquiries' in tables:
        inquiry_cols = [c['name'] for c in inspector.get_columns('tg_bot_inquiries')]
        if 'benefit_id' not in inquiry_cols:
            op.add_column('tg_bot_inquiries', sa.Column('benefit_id', sa.Integer(), nullable=True))
            op.create_foreign_key(
                'fk_tg_bot_inquiries_benefit_id_tg_bot_benefits',
                'tg_bot_inquiries', 'tg_bot_benefits',
                ['benefit_id'], ['id'],
                ondelete='SET NULL'
            )
            op.create_index(op.f('ix_tg_bot_inquiries_benefit_id'), 'tg_bot_inquiries', ['benefit_id'], unique=False)


def downgrade():
    if context.is_offline_mode():
        op.drop_constraint('fk_tg_bot_inquiries_benefit_id_tg_bot_benefits', 'tg_bot_inquiries', type_='foreignkey')
        op.drop_index(op.f('ix_tg_bot_inquiries_benefit_id'), table_name='tg_bot_inquiries')
        op.drop_column('tg_bot_inquiries', 'benefit_id')

        op.drop_column('tg_bot_benefits', 'keywords')
        op.drop_column('tg_bot_benefits', 'lex_url')
        op.drop_column('tg_bot_benefits', 'mygov_url')
        op.drop_column('tg_bot_benefits', 'guide_ru')
        op.drop_column('tg_bot_benefits', 'guide_oz')
        op.drop_column('tg_bot_benefits', 'guide_uz')
        return

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    # 1. Drop foreign key, index and column from tg_bot_inquiries
    if 'tg_bot_inquiries' in tables:
        inquiry_cols = [c['name'] for c in inspector.get_columns('tg_bot_inquiries')]
        if 'benefit_id' in inquiry_cols:
            try:
                op.drop_constraint('fk_tg_bot_inquiries_benefit_id_tg_bot_benefits', 'tg_bot_inquiries', type_='foreignkey')
            except Exception:
                pass
            try:
                op.drop_index(op.f('ix_tg_bot_inquiries_benefit_id'), table_name='tg_bot_inquiries')
            except Exception:
                pass
            op.drop_column('tg_bot_inquiries', 'benefit_id')

    # 2. Drop columns from tg_bot_benefits
    if 'tg_bot_benefits' in tables:
        benefit_cols = [c['name'] for c in inspector.get_columns('tg_bot_benefits')]
        for col in ['keywords', 'lex_url', 'mygov_url', 'guide_ru', 'guide_oz', 'guide_uz']:
            if col in benefit_cols:
                op.drop_column('tg_bot_benefits', col)
