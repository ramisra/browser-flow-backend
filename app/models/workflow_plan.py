"""Workflow plan data models."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Step execution status."""

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExecutionMode(str, Enum):
    """Execution mode for workflow steps."""

    SEQUENTIAL = "SEQUENTIAL"
    PARALLEL = "PARALLEL"


class WorkflowStep(BaseModel):
    """A single step in a workflow."""

    step_id: str = Field(..., description="Unique identifier for this step")
    tool_name: str = Field(..., description="Name of the tool to execute")
    tool_params: Dict[str, Any] = Field(default_factory=dict, description="Parameters for the tool")
    dependencies: List[str] = Field(default_factory=list, description="Step IDs this step depends on")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Current execution status")
    result: Optional[Dict[str, Any]] = Field(default=None, description="Result after execution")
    error: Optional[str] = Field(default=None, description="Error message if step failed")
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SEQUENTIAL, description="How this step should be executed"
    )


class WorkflowPlan(BaseModel):
    """Complete workflow execution plan."""

    plan_id: str = Field(..., description="Unique identifier for this plan")
    steps: List[WorkflowStep] = Field(..., description="Ordered list of workflow steps")
    estimated_duration: Optional[float] = Field(
        default=None, description="Estimated duration in seconds"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional plan metadata")


__all__ = ["WorkflowPlan", "WorkflowStep", "StepStatus", "ExecutionMode"]
