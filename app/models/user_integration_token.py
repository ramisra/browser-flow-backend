"""UserIntegrationToken database model for per-user integration API keys."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.db.session import Base


class UserIntegrationToken(Base):
    """Per-user integration token (e.g. Notion API key). Soft-deleted via is_deleted."""

    __tablename__ = "user_integration_tokens"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_guest_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    integration_tool = Column(String(64), nullable=False, index=True)
    api_key = Column(Text, nullable=False)
    integration_metadata = Column(JSONB, nullable=True, default=dict, server_default="{}")
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_guest_id", "integration_tool", name="uq_user_guest_integration"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserIntegrationToken(id={self.id}, user_guest_id={self.user_guest_id}, "
            f"integration_tool={self.integration_tool}, is_deleted={self.is_deleted})>"
        )
