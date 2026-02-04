"""Agent context management."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.task_identification import TaskIdentificationResult


class AgentContext(BaseModel):
    """Context for agent execution."""

    user_context: str = Field(
        ..., description="User context text"
    )
    task_identification: TaskIdentificationResult = Field(
        ..., description="Task identification result"
    )
    context_metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Context metadata (urls, tags, etc.)"
    )
    context_result: Optional[Dict[str, Any]] = Field(
        default=None, description="Processed context result if available"
    )
    shared_state: Dict[str, Any] = Field(
        default_factory=dict, description="Shared state for multi-agent workflows"
    )
    user_guest_id: Optional[UUID] = Field(
        default=None, description="User guest ID"
    )
    context_ids: List[UUID] = Field(
        default_factory=list, description="List of context IDs"
    )

    def update_shared_state(self, updates: Dict[str, Any]) -> None:
        """Update shared state.

        Args:
            updates: Dictionary of updates to apply
        """
        self.shared_state.update(updates)

    def get_shared_state(self, key: str, default: Any = None) -> Any:
        """Get a value from shared state.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self.shared_state.get(key, default)

    def merge_context(self, additional_context: Dict[str, Any]) -> None:
        """Merge additional context into context_metadata.

        Args:
            additional_context: Additional context to merge
        """
        self.context_metadata.update(additional_context)


__all__ = ["AgentContext"]
