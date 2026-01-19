"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('picture', sa.String(length=500), nullable=True),
        sa.Column('google_access_token', sa.Text(), nullable=True),
        sa.Column('google_refresh_token', sa.Text(), nullable=True),
        sa.Column('google_token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='America/New_York'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Create email_cache table
    op.create_table(
        'email_cache',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gmail_id', sa.String(length=255), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('history_id', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('sender_email', sa.String(length=255), nullable=False),
        sa.Column('sender_name', sa.String(length=255), nullable=True),
        sa.Column('to_emails', postgresql.ARRAY(sa.String(length=255)), nullable=True),
        sa.Column('cc_emails', postgresql.ARRAY(sa.String(length=255)), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('snippet', sa.String(length=500), nullable=True),
        sa.Column('labels', postgresql.ARRAY(sa.String(length=100)), nullable=True),
        sa.Column('is_unread', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('has_attachments', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('received_at', sa.DateTime(), nullable=False),
        sa.Column('category', sa.Enum('urgent', 'action_required', 'fyi', 'newsletter', 'personal', 'spam', 'unknown', name='emailcategory'), nullable=True),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='emailpriority'), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('action_items', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.String(length=50), nullable=True),
        sa.Column('requires_response', sa.Boolean(), nullable=True),
        sa.Column('qdrant_id', sa.String(length=255), nullable=True),
        sa.Column('synced_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('analyzed_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_cache_gmail_id', 'email_cache', ['gmail_id'], unique=True)
    op.create_index('ix_email_cache_thread_id', 'email_cache', ['thread_id'], unique=False)
    op.create_index('ix_email_cache_sender_email', 'email_cache', ['sender_email'], unique=False)
    op.create_index('ix_email_cache_received_at', 'email_cache', ['received_at'], unique=False)
    op.create_index('ix_email_cache_received_sender', 'email_cache', ['received_at', 'sender_email'], unique=False)

    # Create contacts table
    op.create_table(
        'contacts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('category', sa.Enum('team', 'investor', 'vendor', 'family', 'client', 'partner', 'other', name='contactcategory'), nullable=False, server_default='other'),
        sa.Column('reports_to_id', sa.Integer(), nullable=True),
        sa.Column('supervisor_email', sa.String(length=255), nullable=True),
        sa.Column('expected_response_days', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('ai_context', sa.Text(), nullable=True),
        sa.Column('last_email_at', sa.DateTime(), nullable=True),
        sa.Column('last_meeting_at', sa.DateTime(), nullable=True),
        sa.Column('email_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['reports_to_id'], ['contacts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_contacts_email', 'contacts', ['email'], unique=True)

    # Create followups table
    op.create_table(
        'followups',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=True),
        sa.Column('gmail_id', sa.String(length=255), nullable=False),
        sa.Column('thread_id', sa.String(length=255), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('pending', 'reminded', 'escalated', 'completed', 'cancelled', name='followupstatus'), nullable=False, server_default='pending'),
        sa.Column('priority', sa.Enum('low', 'normal', 'high', 'urgent', name='followuppriority'), nullable=False, server_default='normal'),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('ai_summary', sa.Text(), nullable=True),
        sa.Column('escalation_email', sa.String(length=255), nullable=True),
        sa.Column('escalation_days', sa.Integer(), nullable=False, server_default='7'),
        sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
        sa.Column('escalated_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('completed_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['email_id'], ['email_cache.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_followups_user_id', 'followups', ['user_id'], unique=False)
    op.create_index('ix_followups_gmail_id', 'followups', ['gmail_id'], unique=False)
    op.create_index('ix_followups_thread_id', 'followups', ['thread_id'], unique=False)
    op.create_index('ix_followups_contact_email', 'followups', ['contact_email'], unique=False)
    op.create_index('ix_followups_status', 'followups', ['status'], unique=False)
    op.create_index('ix_followups_due_date', 'followups', ['due_date'], unique=False)
    op.create_index('ix_followups_status_due', 'followups', ['status', 'due_date'], unique=False)
    op.create_index('ix_followups_user_status', 'followups', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_table('followups')
    op.drop_table('contacts')
    op.drop_table('email_cache')
    op.drop_table('users')

    # Drop enums
    op.execute('DROP TYPE IF EXISTS followupstatus')
    op.execute('DROP TYPE IF EXISTS followuppriority')
    op.execute('DROP TYPE IF EXISTS emailcategory')
    op.execute('DROP TYPE IF EXISTS emailpriority')
    op.execute('DROP TYPE IF EXISTS contactcategory')
