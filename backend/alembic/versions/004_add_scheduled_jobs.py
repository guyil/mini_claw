"""add scheduled_jobs and scheduled_job_runs tables

Revision ID: 004
Revises: 003
Create Date: 2026-04-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'scheduled_jobs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('bot_id', sa.UUID(), nullable=True),
        sa.Column('conversation_id', sa.UUID(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('delete_after_run', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('schedule_type', sa.String(length=20), nullable=False),
        sa.Column('schedule_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('payload_message', sa.Text(), nullable=False),
        sa.Column('payload_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('delivery_mode', sa.String(length=20), nullable=False, server_default=sa.text("'chat'")),
        sa.Column('delivery_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(length=20), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('last_result_summary', sa.Text(), nullable=True),
        sa.Column('consecutive_errors', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('run_count', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['bot_id'], ['bots.id']),
        sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduled_jobs_user_id', 'scheduled_jobs', ['user_id'])
    op.create_index('ix_scheduled_jobs_next_run_at', 'scheduled_jobs', ['next_run_at'])
    op.create_index(
        'ix_scheduled_jobs_enabled_next_run',
        'scheduled_jobs',
        ['enabled', 'next_run_at'],
    )

    op.create_table(
        'scheduled_job_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_id', sa.UUID(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['scheduled_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_scheduled_job_runs_job_id', 'scheduled_job_runs', ['job_id'])


def downgrade() -> None:
    op.drop_index('ix_scheduled_job_runs_job_id', table_name='scheduled_job_runs')
    op.drop_table('scheduled_job_runs')
    op.drop_index('ix_scheduled_jobs_enabled_next_run', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_next_run_at', table_name='scheduled_jobs')
    op.drop_index('ix_scheduled_jobs_user_id', table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')
