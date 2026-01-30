"""Task identification data models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.task_types import TaskType


class TaskIdentificationMetadata(BaseModel):
    """Additional metadata about task identification."""

    model: Optional[str] = Field(default=None, description="Model identifier")
    raw_response: Optional[Dict[str, Any]] = Field(
        default=None, description="Raw model response payload"
    )


class TaskIdentificationResult(BaseModel):
    """Task identification result."""

    task_type: TaskType = Field(..., description="Identified task type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")
    reasoning: str = Field(..., description="Explanation for task type selection")
    alternative_types: List[TaskType] = Field(
        default_factory=list, description="Other possible task types"
    )
    input: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured input parameters for the task (key-value dictionary)"
    )
    output: Optional[Dict[str, Any]] = Field(
        default=None, description="Expected output structure for the task (key-value dictionary)"
    )
    metadata: Optional[TaskIdentificationMetadata] = Field(
        default=None, description="Additional identification metadata"
    )


__all__ = ["TaskIdentificationResult", "TaskIdentificationMetadata"]
