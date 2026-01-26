"""Add intent and workflow fields to user_tasks

Revision ID: 003_add_intent_workflow
Revises: 002_convert_embedding
Create Date: 2024-01-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_intent_workflow'
down_revision: Union[str, None] = '002_convert_embedding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add intent and workflow fields to user_tasks table."""
    # Add detected_intent column (JSONB)
    op.add_column(
        'user_tasks',
        sa.Column('detected_intent', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}')
    )
    
    # Add workflow_plan column (JSONB)
    op.add_column(
        'user_tasks',
        sa.Column('workflow_plan', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}')
    )
    
    # Add execution_status column (String)
    op.add_column(
        'user_tasks',
        sa.Column('execution_status', sa.String(), nullable=True, server_default='PENDING')
    )


def downgrade() -> None:
    """Remove intent and workflow fields from user_tasks table."""
    op.drop_column('user_tasks', 'execution_status')
    op.drop_column('user_tasks', 'workflow_plan')
    op.drop_column('user_tasks', 'detected_intent')
