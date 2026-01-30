"""Agent registry for task routing."""

from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.core.task_types import TaskType

AgentHandler = Callable[..., Awaitable[Any]]


class AgentRegistry:
    """Simple registry mapping TaskType to agent handlers."""

    def __init__(self) -> None:
        self._agents: Dict[TaskType, AgentHandler] = {}

    def register_agent(self, task_type: TaskType, agent_func: AgentHandler) -> None:
        """Register an agent handler for a task type."""
        self._agents[task_type] = agent_func

    def get_agent(self, task_type: TaskType) -> Optional[AgentHandler]:
        """Get the agent handler for a task type."""
        return self._agents.get(task_type)

    def get_all_registered_types(self) -> List[TaskType]:
        """Get all task types that have registered agents."""
        return list(self._agents.keys())


__all__ = ["AgentRegistry", "AgentHandler"]
