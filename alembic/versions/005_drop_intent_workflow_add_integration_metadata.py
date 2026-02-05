"""Drop intent/workflow from user_tasks, add integration_metadata to user_integration_tokens

Revision ID: 005_drop_intent_add_metadata
Revises: 004_user_integration_tokens
Create Date: 2024-01-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "005_drop_intent_add_metadata"
down_revision: Union[str, None] = "004_user_integration_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop detected_intent and workflow_plan from user_tasks
    op.drop_column("user_tasks", "detected_intent")
    op.drop_column("user_tasks", "workflow_plan")

    # Add integration_metadata JSONB to user_integration_tokens
    op.add_column(
        "user_integration_tokens",
        sa.Column(
            "integration_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    # Remove integration_metadata from user_integration_tokens
    op.drop_column("user_integration_tokens", "integration_metadata")

    # Restore detected_intent and workflow_plan on user_tasks
    op.add_column(
        "user_tasks",
        sa.Column(
            "detected_intent",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
    )
    op.add_column(
        "user_tasks",
        sa.Column(
            "workflow_plan",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            server_default="{}",
        ),
    )
