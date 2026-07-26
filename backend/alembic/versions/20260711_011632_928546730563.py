"""create initial tables

Revision ID: 928546730563
Revises: 
Create Date: 2026-07-11 01:16:32.549744

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '928546730563'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('executions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=500), nullable=False),
    sa.Column('semester', sa.String(length=10), nullable=False),
    sa.Column('mode', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('metrics', sa.JSON(), nullable=True),
    sa.Column('errors_count', sa.Integer(), nullable=True),
    sa.Column('report_dir', sa.String(length=500), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('duration_seconds', sa.Float(), nullable=True),
    sa.Column('current_phase', sa.String(length=100), nullable=True),
    sa.Column('progress_pct', sa.Float(), nullable=True),
    sa.Column('progress_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('current_step', sa.Integer(), nullable=True),
    sa.Column('moodle_version', sa.String(length=10), nullable=True),
    sa.Column('modalidad', sa.String(length=20), nullable=True),
    sa.Column('phase_checkpoint', sa.JSON(), nullable=True),
    sa.Column('celery_task_id', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_executions_id'), 'executions', ['id'], unique=False)
    op.create_index(op.f('ix_executions_created_at'), 'executions', ['created_at'], unique=False)
    op.create_index(op.f('ix_executions_semester'), 'executions', ['semester'], unique=False)
    op.create_index(op.f('ix_executions_status'), 'executions', ['status'], unique=False)
    op.create_index(op.f('ix_executions_modalidad'), 'executions', ['modalidad'], unique=False)
    op.create_index(op.f('ix_executions_celery_task_id'), 'executions', ['celery_task_id'], unique=False)

    op.create_table('error_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('execution_id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('identifier', sa.String(length=255), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_error_logs_id'), 'error_logs', ['id'], unique=False)
    op.create_index(op.f('ix_error_logs_execution_id'), 'error_logs', ['execution_id'], unique=False)

    op.create_table('execution_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('execution_id', sa.Integer(), nullable=False),
    sa.Column('phase', sa.String(length=10), nullable=False),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('identifier', sa.String(length=255), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['execution_id'], ['executions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_execution_logs_id'), 'execution_logs', ['id'], unique=False)
    op.create_index(op.f('ix_execution_logs_execution_id'), 'execution_logs', ['execution_id'], unique=False)

    op.create_table('operation_batches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=20), nullable=False),
    sa.Column('action', sa.String(length=20), nullable=False),
    sa.Column('total', sa.Integer(), nullable=True),
    sa.Column('completed', sa.Integer(), nullable=True),
    sa.Column('failed', sa.Integer(), nullable=True),
    sa.Column('modalidad', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('batch_id')
    )
    op.create_index(op.f('ix_operation_batches_id'), 'operation_batches', ['id'], unique=False)
    op.create_index(op.f('ix_operation_batches_batch_id'), 'operation_batches', ['batch_id'], unique=False)
    op.create_index(op.f('ix_operation_batches_created_at'), 'operation_batches', ['created_at'], unique=False)

    op.create_table('operation_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.String(length=64), nullable=False),
    sa.Column('identifier', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['operation_batches.batch_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_operation_items_id'), 'operation_items', ['id'], unique=False)
    op.create_index(op.f('ix_operation_items_batch_id'), 'operation_items', ['batch_id'], unique=False)
    op.create_index(op.f('ix_operation_items_status'), 'operation_items', ['status'], unique=False)

    op.create_table('query_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.String(length=64), nullable=False),
    sa.Column('entity', sa.String(length=20), nullable=False),
    sa.Column('params', sa.JSON(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('result_json', sa.JSON(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('total_count', sa.Integer(), nullable=True),
    sa.Column('modalidad', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('task_id')
    )
    op.create_index(op.f('ix_query_results_id'), 'query_results', ['id'], unique=False)
    op.create_index(op.f('ix_query_results_task_id'), 'query_results', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_table('query_results')
    op.drop_table('operation_items')
    op.drop_table('operation_batches')
    op.drop_table('execution_logs')
    op.drop_table('error_logs')
    op.drop_table('executions')
