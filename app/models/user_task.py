"""UserTask database model."""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import ARRAY, Column, DateTime, Enum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from app.core.task_types import TaskType
from app.db.session import Base


class ExecutionStatus(str, enum.Enum):
    """Execution status enumeration."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"


class UserTask(Base):
    """User task model for storing task information."""

    __tablename__ = "user_tasks"

    task_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    task_type = Column(Enum(TaskType, name='tasktype', native_enum=True, create_constraint=False), nullable=False, index=True)
    input = Column(JSONB, nullable=False, default=dict)
    output = Column(JSONB, nullable=True, default=dict)
    user_guest_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_contexts = Column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    # New fields for intent-to-output orchestration
    detected_intent = Column(JSONB, nullable=True, default=dict)
    workflow_plan = Column(JSONB, nullable=True, default=dict)
    execution_status = Column(String, nullable=True, default="PENDING")

    def __repr__(self) -> str:
        return f"<UserTask(task_id={self.task_id}, task_type={self.task_type.value})>"
