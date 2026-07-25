"""add celery_task_id and FK indexes

Revision ID: add_celery_task_id
Revises: cac79e1caadb
Create Date: 2026-07-25 12:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_celery_task_id'
down_revision: Union[str, Sequence[str], None] = 'cac79e1caadb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('executions', sa.Column('celery_task_id', sa.String(255), nullable=True))
    op.create_index('ix_error_logs_execution_id', 'error_logs', ['execution_id'], if_not_exists=True)
    op.create_index('ix_execution_logs_execution_id', 'execution_logs', ['execution_id'], if_not_exists=True)


def downgrade() -> None:
    op.drop_index('ix_execution_logs_execution_id', table_name='execution_logs', if_exists=True)
    op.drop_index('ix_error_logs_execution_id', table_name='error_logs', if_exists=True)
    op.drop_column('executions', 'celery_task_id')
