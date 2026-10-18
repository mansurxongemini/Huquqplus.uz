"""create_benefits_table

Revision ID: d1e2f3a4b5c6
Revises: c2d3e4f5a6b7
Create Date: 2026-10-04 10:35:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'tg_bot_benefits' not in tables:
        op.create_table(
            'tg_bot_benefits',
            sa.Column('id', sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
            sa.Column('category', sa.VARCHAR(length=50), nullable=False, server_default='other'),
            sa.Column('for_first_group', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('for_second_group', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('for_third_group', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('for_child', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('for_parent', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('is_for_organization', sa.Boolean(), nullable=False, server_default=sa.text('0')),
            sa.Column('min_age', sa.Integer(), nullable=True),
            sa.Column('max_age', sa.Integer(), nullable=True),
            sa.Column('gender', sa.VARCHAR(length=20), nullable=True),
            sa.Column('disability_state', sa.VARCHAR(length=50), nullable=True),
            sa.Column('title_uz', sa.Text(), nullable=False),
            sa.Column('description_uz', sa.Text(), nullable=False),
            sa.Column('amount_uz', sa.Text(), nullable=True),
            sa.Column('organization_uz', sa.Text(), nullable=True),
            sa.Column('legal_basis_uz', sa.Text(), nullable=True),
            sa.Column('title_oz', sa.Text(), nullable=False),
            sa.Column('description_oz', sa.Text(), nullable=False),
            sa.Column('amount_oz', sa.Text(), nullable=True),
            sa.Column('organization_oz', sa.Text(), nullable=True),
            sa.Column('legal_basis_oz', sa.Text(), nullable=True),
            sa.Column('title_ru', sa.Text(), nullable=True),
            sa.Column('description_ru', sa.Text(), nullable=True),
            sa.Column('amount_ru', sa.Text(), nullable=True),
            sa.Column('organization_ru', sa.Text(), nullable=True),
            sa.Column('legal_basis_ru', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('order_index', sa.Integer(), nullable=False, server_default=sa.text('0')),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_tg_bot_benefits_category'), 'tg_bot_benefits', ['category'], unique=False)
        op.create_index(op.f('ix_tg_bot_benefits_is_active'), 'tg_bot_benefits', ['is_active'], unique=False)


def downgrade():
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()
    if 'tg_bot_benefits' in tables:
        op.drop_table('tg_bot_benefits')
