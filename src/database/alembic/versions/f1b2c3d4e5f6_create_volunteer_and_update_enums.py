"""create_volunteer_and_update_enums

Revision ID: f1b2c3d4e5f6
Revises: 42291e80ee26
Create Date: 2026-09-15 19:55:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'f1b2c3d4e5f6'
down_revision = '42291e80ee26'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create volunteers table
    op.create_table(
        'tg_bot_volunteers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('first_name', sa.VARCHAR(length=100), nullable=False),
        sa.Column('last_name', sa.VARCHAR(length=100), nullable=False),
        sa.Column('study_or_work', sa.VARCHAR(length=255), nullable=False),
        sa.Column('birth_year', sa.Integer(), server_default='2000', nullable=False),
        sa.Column('phone_number', sa.VARCHAR(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tg_bot_volunteers_user_id'), 'tg_bot_volunteers', ['user_id'], unique=True)

    # 2. Update InquiryMediaType enums to support 'document' and 'photo'
    bind = op.get_bind()
    if bind and bind.dialect.name in ('mysql', 'mariadb'):
        op.execute(
            "ALTER TABLE tg_bot_inquiries MODIFY COLUMN question_mediatype "
            "ENUM('text', 'voice', 'video_note', 'video', 'document', 'photo') NOT NULL DEFAULT 'text'"
        )
        op.execute(
            "ALTER TABLE tg_bot_inquiries MODIFY COLUMN answer_mediatype "
            "ENUM('text', 'voice', 'video_note', 'video', 'document', 'photo') NOT NULL DEFAULT 'text'"
        )
    else:
        new_enum = sa.Enum('text', 'voice', 'video_note', 'video', 'document', 'photo', name='inquirymediatype')
        old_enum = sa.Enum('text', 'voice', 'video_note', 'video', name='inquirymediatype')
        op.alter_column('tg_bot_inquiries', 'question_mediatype', type_=new_enum, existing_type=old_enum, nullable=False)
        op.alter_column('tg_bot_inquiries', 'answer_mediatype', type_=new_enum, existing_type=old_enum, nullable=False)


def downgrade():
    op.drop_index(op.f('ix_tg_bot_volunteers_user_id'), table_name='tg_bot_volunteers')
    op.drop_table('tg_bot_volunteers')

    bind = op.get_bind()
    if bind and bind.dialect.name in ('mysql', 'mariadb'):
        op.execute(
            "ALTER TABLE tg_bot_inquiries MODIFY COLUMN question_mediatype "
            "ENUM('text', 'voice', 'video_note', 'video') NOT NULL DEFAULT 'text'"
        )
        op.execute(
            "ALTER TABLE tg_bot_inquiries MODIFY COLUMN answer_mediatype "
            "ENUM('text', 'voice', 'video_note', 'video') NOT NULL DEFAULT 'text'"
        )
    else:
        new_enum = sa.Enum('text', 'voice', 'video_note', 'video', 'document', 'photo', name='inquirymediatype')
        old_enum = sa.Enum('text', 'voice', 'video_note', 'video', name='inquirymediatype')
        op.alter_column('tg_bot_inquiries', 'question_mediatype', type_=old_enum, existing_type=new_enum, nullable=False)
        op.alter_column('tg_bot_inquiries', 'answer_mediatype', type_=old_enum, existing_type=new_enum, nullable=False)
