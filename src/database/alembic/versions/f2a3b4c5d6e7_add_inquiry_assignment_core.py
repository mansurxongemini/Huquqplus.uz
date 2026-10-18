"""add inquiry assignment core (A stage)

Revision ID: f2a3b4c5d6e7
Revises: e2f3a4b5c6d7
Create Date: 2026-10-18 00:00:00.000000

A bosqich: inquiries.assigned_* ustunlari, volunteer_sections va
inquiry_assignments jadvallari (review/reminder ustunlari bilan).
"""
from alembic import op, context
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e2f3a4b5c6d7'
branch_labels = None
depends_on = None


def upgrade():
    if context.is_offline_mode():
        op.add_column('tg_bot_inquiries', sa.Column('assigned_volunteer_id', sa.BigInteger(), nullable=True))
        op.create_index(op.f('ix_tg_bot_inquiries_assigned_volunteer_id'), 'tg_bot_inquiries', ['assigned_volunteer_id'], unique=False)
        op.add_column('tg_bot_inquiries', sa.Column('assigned_at', sa.DateTime(), nullable=True))
        op.add_column('tg_bot_inquiries', sa.Column('assign_source', sa.VARCHAR(length=20), nullable=True, server_default='admin'))
        op.add_column('tg_bot_inquiries', sa.Column('assign_message_id', sa.Integer(), nullable=True))

        op.create_table(
            'tg_bot_volunteer_sections',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('volunteer_user_id', sa.BigInteger(), nullable=False),
            sa.Column('section_name', sa.VARCHAR(length=255), nullable=False),
            sa.Column('added_by', sa.BigInteger(), nullable=True),
            sa.Column('added_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('volunteer_user_id', 'section_name', name='uq_volunteer_sections_pair'),
        )
        op.create_index(op.f('ix_tg_bot_volunteer_sections_volunteer_user_id'), 'tg_bot_volunteer_sections', ['volunteer_user_id'], unique=False)

        op.create_table(
            'tg_bot_inquiry_assignments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('inquiry_id', sa.Integer(), nullable=False),
            sa.Column('volunteer_user_id', sa.BigInteger(), nullable=False),
            sa.Column('section_name', sa.VARCHAR(length=255), nullable=True),
            sa.Column('assigned_by', sa.BigInteger(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.VARCHAR(length=20), nullable=True),
            sa.Column('notify_error', sa.Text(), nullable=True),
            sa.Column('notify_attempts', sa.Integer(), nullable=True),
            sa.Column('last_notify_at', sa.DateTime(), nullable=True),
            sa.Column('first_reminded_at', sa.DateTime(), nullable=True),
            sa.Column('last_reminded_at', sa.DateTime(), nullable=True),
            sa.Column('remind_count', sa.Integer(), nullable=True),
            sa.Column('review_status', sa.VARCHAR(length=20), nullable=True),
            sa.Column('review_draft_hash', sa.VARCHAR(length=64), nullable=True),
            sa.Column('review_passed_at', sa.DateTime(), nullable=True),
            sa.Column('review_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['inquiry_id'], ['tg_bot_inquiries.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_tg_bot_inquiry_assignments_inquiry_id'), 'tg_bot_inquiry_assignments', ['inquiry_id'], unique=False)
        op.create_index(op.f('ix_tg_bot_inquiry_assignments_volunteer_user_id'), 'tg_bot_inquiry_assignments', ['volunteer_user_id'], unique=False)
        op.create_index(op.f('ix_tg_bot_inquiry_assignments_status'), 'tg_bot_inquiry_assignments', ['status'], unique=False)
        return

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'tg_bot_inquiries' in tables:
        inquiry_cols = [c['name'] for c in inspector.get_columns('tg_bot_inquiries')]
        if 'assigned_volunteer_id' not in inquiry_cols:
            op.add_column('tg_bot_inquiries', sa.Column('assigned_volunteer_id', sa.BigInteger(), nullable=True))
            op.create_index(op.f('ix_tg_bot_inquiries_assigned_volunteer_id'), 'tg_bot_inquiries', ['assigned_volunteer_id'], unique=False)
        if 'assigned_at' not in inquiry_cols:
            op.add_column('tg_bot_inquiries', sa.Column('assigned_at', sa.DateTime(), nullable=True))
        if 'assign_source' not in inquiry_cols:
            op.add_column('tg_bot_inquiries', sa.Column('assign_source', sa.VARCHAR(length=20), nullable=True, server_default='admin'))
        if 'assign_message_id' not in inquiry_cols:
            op.add_column('tg_bot_inquiries', sa.Column('assign_message_id', sa.Integer(), nullable=True))

    if 'tg_bot_volunteer_sections' not in tables:
        op.create_table(
            'tg_bot_volunteer_sections',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('volunteer_user_id', sa.BigInteger(), nullable=False),
            sa.Column('section_name', sa.VARCHAR(length=255), nullable=False),
            sa.Column('added_by', sa.BigInteger(), nullable=True),
            sa.Column('added_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('volunteer_user_id', 'section_name', name='uq_volunteer_sections_pair'),
        )
        op.create_index(op.f('ix_tg_bot_volunteer_sections_volunteer_user_id'), 'tg_bot_volunteer_sections', ['volunteer_user_id'], unique=False)

    if 'tg_bot_inquiry_assignments' not in tables:
        op.create_table(
            'tg_bot_inquiry_assignments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('inquiry_id', sa.Integer(), nullable=False),
            sa.Column('section_name', sa.VARCHAR(length=255), nullable=True),
            sa.Column('volunteer_user_id', sa.BigInteger(), nullable=False),
            sa.Column('assigned_by', sa.BigInteger(), nullable=False),
            sa.Column('assigned_at', sa.DateTime(), nullable=True),
            sa.Column('status', sa.VARCHAR(length=20), nullable=True),
            sa.Column('notify_error', sa.Text(), nullable=True),
            sa.Column('notify_attempts', sa.Integer(), nullable=True),
            sa.Column('last_notify_at', sa.DateTime(), nullable=True),
            sa.Column('first_reminded_at', sa.DateTime(), nullable=True),
            sa.Column('last_reminded_at', sa.DateTime(), nullable=True),
            sa.Column('remind_count', sa.Integer(), nullable=True),
            sa.Column('review_status', sa.VARCHAR(length=20), nullable=True),
            sa.Column('review_draft_hash', sa.VARCHAR(length=64), nullable=True),
            sa.Column('review_passed_at', sa.DateTime(), nullable=True),
            sa.Column('review_json', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['inquiry_id'], ['tg_bot_inquiries.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index(op.f('ix_tg_bot_inquiry_assignments_inquiry_id'), 'tg_bot_inquiry_assignments', ['inquiry_id'], unique=False)
        op.create_index(op.f('ix_tg_bot_inquiry_assignments_volunteer_user_id'), 'tg_bot_inquiry_assignments', ['volunteer_user_id'], unique=False)
        op.create_index(op.f('ix_tg_bot_inquiry_assignments_status'), 'tg_bot_inquiry_assignments', ['status'], unique=False)


def downgrade():
    if context.is_offline_mode():
        op.drop_index(op.f('ix_tg_bot_inquiry_assignments_status'), table_name='tg_bot_inquiry_assignments')
        op.drop_index(op.f('ix_tg_bot_inquiry_assignments_volunteer_user_id'), table_name='tg_bot_inquiry_assignments')
        op.drop_index(op.f('ix_tg_bot_inquiry_assignments_inquiry_id'), table_name='tg_bot_inquiry_assignments')
        op.drop_table('tg_bot_inquiry_assignments')

        op.drop_index(op.f('ix_tg_bot_volunteer_sections_volunteer_user_id'), table_name='tg_bot_volunteer_sections')
        op.drop_table('tg_bot_volunteer_sections')

        op.drop_index(op.f('ix_tg_bot_inquiries_assigned_volunteer_id'), table_name='tg_bot_inquiries')
        op.drop_column('tg_bot_inquiries', 'assign_message_id')
        op.drop_column('tg_bot_inquiries', 'assign_source')
        op.drop_column('tg_bot_inquiries', 'assigned_at')
        op.drop_column('tg_bot_inquiries', 'assigned_volunteer_id')
        return

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'tg_bot_inquiry_assignments' in tables:
        op.drop_table('tg_bot_inquiry_assignments')

    if 'tg_bot_volunteer_sections' in tables:
        op.drop_table('tg_bot_volunteer_sections')

    if 'tg_bot_inquiries' in tables:
        inquiry_cols = [c['name'] for c in inspector.get_columns('tg_bot_inquiries')]
        for col in ['assign_message_id', 'assign_source', 'assigned_at', 'assigned_volunteer_id']:
            if col in inquiry_cols:
                try:
                    if col == 'assigned_volunteer_id':
                        op.drop_index(op.f('ix_tg_bot_inquiries_assigned_volunteer_id'), table_name='tg_bot_inquiries')
                except Exception:
                    pass
                op.drop_column('tg_bot_inquiries', col)
