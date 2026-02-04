"""Agent result models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    """Result from agent execution."""

    status: str = Field(
        ..., description="Execution status (completed, failed, partial)"
    )
    result: Dict[str, Any] = Field(
        ..., description="Main result data"
    )
    excel_file_path: Optional[str] = Field(
        default=None, description="Path to generated Excel file if applicable"
    )
    extracted_data: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Extracted structured data"
    )
    validation_errors: List[str] = Field(
        default_factory=list, description="List of validation errors"
    )
    execution_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional execution metadata"
    )
    error: Optional[str] = Field(
        default=None, description="Error message if execution failed"
    )


class TaskExecutionResult(BaseModel):
    """Result from task orchestration."""

    status: str = Field(
        ..., description="Execution status"
    )
    result: Dict[str, Any] = Field(
        ..., description="Execution result"
    )
    agent_results: List[AgentResult] = Field(
        default_factory=list, description="Results from individual agents"
    )
    workflow_plan: Optional[Dict[str, Any]] = Field(
        default=None, description="Workflow plan if non-atomic task"
    )


__all__ = ["AgentResult", "TaskExecutionResult"]
