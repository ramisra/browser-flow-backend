"""Agent registry for task routing with file-based storage."""

import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type, Tuple

from app.core.task_types import TaskType
from app.models.agent_metadata import AgentMetadata

AgentHandler = Callable[..., Awaitable[Any]]


class AgentRegistry:
    """Registry with dictionary/file-based storage for agent metadata."""

    def __init__(self, registry_file: Optional[str] = None) -> None:
        """Initialize the agent registry.

        Args:
            registry_file: Optional path to registry JSON file
        """
        self._agents: Dict[TaskType, AgentHandler] = {}
        self._agent_metadata: Dict[str, AgentMetadata] = {}
        self._agent_classes: Dict[str, Type] = {}
        self._registry_file = registry_file or "app/config/agents_registry.json"
        self._load_from_file()

    def _load_from_file(self) -> None:
        """Load agent metadata from JSON file."""
        registry_path = Path(self._registry_file)
        if not registry_path.exists():
            # Create directory if it doesn't exist
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            return

        try:
            with open(registry_path, "r") as f:
                data = json.load(f)
                agents_data = data.get("agents", {})
                for agent_id, agent_data in agents_data.items():
                    try:
                        metadata = AgentMetadata(**agent_data)
                        self._agent_metadata[agent_id] = metadata
                    except Exception as e:
                        print(f"Error loading agent metadata for {agent_id}: {e}")
        except Exception as e:
            print(f"Error loading agent registry from file: {e}")

    def _save_to_file(self) -> None:
        """Save agent metadata to JSON file."""
        registry_path = Path(self._registry_file)
        registry_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            agents_data = {
                agent_id: metadata.model_dump()
                for agent_id, metadata in self._agent_metadata.items()
            }
            data = {"agents": agents_data}
            with open(registry_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving agent registry to file: {e}")

    def register_agent(
        self, task_type: TaskType, agent_func: AgentHandler
    ) -> None:
        """Register an agent handler for a task type (legacy method).

        Args:
            task_type: Task type
            agent_func: Agent handler function
        """
        self._agents[task_type] = agent_func

    def register_agent_metadata(self, metadata: AgentMetadata) -> None:
        """Register agent with metadata.

        Args:
            metadata: Agent metadata
        """
        self._agent_metadata[metadata.agent_id] = metadata
        self._save_to_file()

    def register_agent_class(
        self, agent_id: str, agent_class: Type
    ) -> None:
        """Register an agent class.

        Args:
            agent_id: Agent ID
            agent_class: Agent class
        """
        self._agent_classes[agent_id] = agent_class

    def get_agent(self, task_type: TaskType) -> Optional[AgentHandler]:
        """Get the agent handler for a task type (legacy method).

        Args:
            task_type: Task type

        Returns:
            Agent handler or None
        """
        return self._agents.get(task_type)

    def get_agent_class(
        self, task_type: TaskType
    ) -> Optional[Type]:
        """Get agent class for task type.

        Args:
            task_type: Task type

        Returns:
            Agent class or None if not found
        """
        # Find agent metadata that handles this task type
        for metadata in self._agent_metadata.values():
            if task_type in metadata.task_types:
                agent_id = metadata.agent_id
                # Try to get class from registry
                if agent_id in self._agent_classes:
                    return self._agent_classes[agent_id]
                # Try to import class from agent_class path
                try:
                    class_path = metadata.agent_class.split(".")
                    module_path = ".".join(class_path[:-1])
                    class_name = class_path[-1]
                    module = __import__(module_path, fromlist=[class_name])
                    agent_class = getattr(module, class_name)
                    self._agent_classes[agent_id] = agent_class
                    return agent_class
                except Exception as e:
                    print(f"Error importing agent class {metadata.agent_class}: {e}")
                    continue
        return None

    def get_agent_class_and_metadata(
        self, task_type: TaskType
    ) -> Optional[Tuple[Type, AgentMetadata]]:
        """Get agent class and metadata for task type.

        Args:
            task_type: Task type

        Returns:
            Tuple of (agent class, metadata) or None if not found
        """
        for metadata in self._agent_metadata.values():
            if task_type in metadata.task_types:
                agent_id = metadata.agent_id
                if agent_id in self._agent_classes:
                    return self._agent_classes[agent_id], metadata
                try:
                    class_path = metadata.agent_class.split(".")
                    module_path = ".".join(class_path[:-1])
                    class_name = class_path[-1]
                    module = __import__(module_path, fromlist=[class_name])
                    agent_class = getattr(module, class_name)
                    self._agent_classes[agent_id] = agent_class
                    return agent_class, metadata
                except Exception as e:
                    print(f"Error importing agent class {metadata.agent_class}: {e}")
                    continue
        return None

    def get_agent_metadata(self, agent_id: str) -> Optional[AgentMetadata]:
        """Get agent metadata by ID.

        Args:
            agent_id: Agent ID

        Returns:
            AgentMetadata or None
        """
        return self._agent_metadata.get(agent_id)

    def discover_agents(
        self, requirements: Dict[str, Any]
    ) -> List[AgentMetadata]:
        """Discover agents matching requirements.

        Args:
            requirements: Dictionary of requirements (capabilities, task_types, etc.)

        Returns:
            List of matching agent metadata
        """
        matches = []
        required_capabilities = requirements.get("capabilities", [])
        required_task_types = requirements.get("task_types", [])

        for metadata in self._agent_metadata.values():
            # Check capabilities
            if required_capabilities:
                if not any(
                    cap in metadata.capabilities
                    for cap in required_capabilities
                ):
                    continue

            # Check task types
            if required_task_types:
                if not any(
                    task_type in metadata.task_types
                    for task_type in required_task_types
                ):
                    continue

            matches.append(metadata)

        return matches

    def get_all_registered_types(self) -> List[TaskType]:
        """Get all task types that have registered agents."""
        return list(self._agents.keys())


__all__ = ["AgentRegistry", "AgentHandler"]
