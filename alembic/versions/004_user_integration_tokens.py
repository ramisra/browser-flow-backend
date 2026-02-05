"""User integration tokens table

Revision ID: 004_user_integration_tokens
Revises: 003_add_intent_workflow
Create Date: 2024-01-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_user_integration_tokens"
down_revision: Union[str, None] = "003_add_intent_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_integration_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_guest_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integration_tool", sa.String(64), nullable=False),
        sa.Column("api_key", sa.Text(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_user_integration_tokens_id", "user_integration_tokens", ["id"]
    )
    op.create_index(
        "ix_user_integration_tokens_user_guest_id",
        "user_integration_tokens",
        ["user_guest_id"],
    )
    op.create_index(
        "ix_user_integration_tokens_integration_tool",
        "user_integration_tokens",
        ["integration_tool"],
    )
    op.create_index(
        "ix_user_integration_tokens_is_deleted",
        "user_integration_tokens",
        ["is_deleted"],
    )
    op.create_unique_constraint(
        "uq_user_guest_integration",
        "user_integration_tokens",
        ["user_guest_id", "integration_tool"],
    )


def downgrade() -> None:
    op.drop_table("user_integration_tokens")
