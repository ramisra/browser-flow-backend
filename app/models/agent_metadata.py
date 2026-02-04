"""Agent metadata models."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.core.task_types import TaskType


class AgentMetadata(BaseModel):
    """Metadata for an agent."""

    agent_id: str = Field(..., description="Unique agent identifier")
    agent_class: str = Field(
        ..., description="Fully qualified class name (e.g., app.agents.data_extraction_agent.DataExtractionAgent)"
    )
    task_types: List[TaskType] = Field(
        ..., description="List of task types this agent can handle"
    )
    capabilities: List[str] = Field(
        default_factory=list, description="List of agent capabilities"
    )
    required_tools: List[str] = Field(
        default_factory=list, description="List of required tool names"
    )
    required_mcp_servers: List[str] = Field(
        default_factory=list,
        description="List of required MCP server names",
    )
    composio_toolkits: Optional[List[str]] = Field(
        default=None,
        description="Explicit list of Composio toolkits (e.g., ['trello', 'composio'])",
    )
    use_composio_fallback: bool = Field(
        default=True,
        description="When True, use Composio to obtain tools not in the MCP pool",
    )
    prompt_template: Optional[str] = Field(
        default=None, description="Optional prompt template"
    )
    description: str = Field(
        ..., description="Agent description"
    )
    config: Dict[str, Any] = Field(
        default_factory=dict, description="Additional agent configuration"
    )


__all__ = ["AgentMetadata"]
