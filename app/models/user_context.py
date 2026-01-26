"""UserContext database model."""

import uuid
from datetime import datetime
from typing import List, Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Column, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.db.session import Base


class ContextType(str, enum.Enum):
    """Context type enumeration.
    
    Note: Database enum uses uppercase values (IMAGE, TEXT, VIDEO).
    """

    IMAGE = "IMAGE"
    TEXT = "TEXT"
    VIDEO = "VIDEO"


class UserContext(Base):
    """User context model for storing processed context data."""

    __tablename__ = "user_contexts"

    context_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    context_tags = Column(ARRAY(String), nullable=False, default=list)
    raw_content = Column(Text, nullable=False)
    user_defined_context = Column(Text, nullable=True)
    embedding = Column(Vector(1536), nullable=True)  # OpenAI text-embedding-3-small dimension
    url = Column(String, nullable=True)
    context_type = Column(Enum(ContextType, name='contexttype', native_enum=True, create_constraint=False), nullable=False, default=ContextType.TEXT)
    user_guest_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    parent_topic = Column(
        UUID(as_uuid=True),
        ForeignKey("user_contexts.context_id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    parent = relationship(
        "UserContext",
        remote_side=[context_id],
        backref="children",
    )

    def __repr__(self) -> str:
        return f"<UserContext(context_id={self.context_id}, url={self.url}, tags={self.context_tags})>"
