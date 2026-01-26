"""Tool registry for discovering and managing available tools."""

from typing import Any, Dict, List, Optional, Protocol

from app.models.intent_classification import IntentCategory


class Tool(Protocol):
    """Protocol for tool interface."""

    name: str
    description: str
    parameters: Dict[str, Any]
    capabilities: List[str]


class ToolMetadata:
    """Metadata for a tool."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        capabilities: List[str],
        supported_intents: List[IntentCategory],
        dependencies: Optional[List[str]] = None,
    ):
        """Initialize tool metadata.

        Args:
            name: Tool name/identifier
            description: Tool description
            parameters: Parameter schema
            capabilities: List of capabilities this tool provides
            supported_intents: Intent categories this tool can handle
            dependencies: Optional list of other tools this depends on
        """
        self.name = name
        self.description = description
        self.parameters = parameters
        self.capabilities = capabilities
        self.supported_intents = supported_intents
        self.dependencies = dependencies or []

    def matches_intent(self, intent: IntentCategory) -> bool:
        """Check if tool supports the given intent."""
        return intent in self.supported_intents

    def matches_requirement(self, requirement_keywords: List[str]) -> float:
        """Calculate match score based on requirement keywords.

        Args:
            requirement_keywords: Keywords from requirement extraction

        Returns:
            Match score between 0.0 and 1.0
        """
        if not requirement_keywords:
            return 0.5  # Neutral score if no keywords

        # Simple keyword matching
        description_lower = self.description.lower()
        capabilities_lower = " ".join(self.capabilities).lower()

        matches = 0
        for keyword in requirement_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in description_lower or keyword_lower in capabilities_lower:
                matches += 1

        return min(matches / len(requirement_keywords), 1.0)


class ToolRegistry:
    """Central registry for all available tools."""

    def __init__(self):
        """Initialize the tool registry."""
        self._tools: Dict[str, ToolMetadata] = {}
        self._initialize_default_tools()

    def _initialize_default_tools(self):
        """Initialize default tools (Composio, etc.)."""
        # Trello tools
        self.register_tool(
            ToolMetadata(
                name="trello_create_card",
                description="Create a new card in Trello board",
                parameters={
                    "board_name": {"type": "string", "required": True},
                    "list_name": {"type": "string", "required": True},
                    "card_title": {"type": "string", "required": True},
                    "card_description": {"type": "string", "required": False},
                    "checklist_items": {"type": "array", "required": False},
                },
                capabilities=["task_creation", "project_management", "todo_management"],
                supported_intents=[
                    IntentCategory.TASK_CREATION,
                    IntentCategory.AUTOMATION,
                ],
            )
        )

        self.register_tool(
            ToolMetadata(
                name="trello_create_list",
                description="Create a new list in Trello board",
                parameters={
                    "board_name": {"type": "string", "required": True},
                    "list_name": {"type": "string", "required": True},
                },
                capabilities=["task_creation", "project_management"],
                supported_intents=[IntentCategory.TASK_CREATION],
            )
        )

        # Google Sheets tools
        self.register_tool(
            ToolMetadata(
                name="google_sheets_append",
                description="Append data to a Google Sheets spreadsheet",
                parameters={
                    "spreadsheet_id": {"type": "string", "required": True},
                    "sheet_name": {"type": "string", "required": True},
                    "values": {"type": "array", "required": True},
                },
                capabilities=["data_storage", "spreadsheet_management"],
                supported_intents=[
                    IntentCategory.DATA_COLLECTION,
                    IntentCategory.INTEGRATION,
                ],
            )
        )

        # Note-taking tools (conceptual - would use context storage)
        self.register_tool(
            ToolMetadata(
                name="save_to_context",
                description="Save information to user context/knowledge base",
                parameters={
                    "content": {"type": "string", "required": True},
                    "tags": {"type": "array", "required": False},
                    "url": {"type": "string", "required": False},
                },
                capabilities=["knowledge_storage", "context_management"],
                supported_intents=[
                    IntentCategory.DOCUMENTATION,
                    IntentCategory.DATA_COLLECTION,
                ],
            )
        )

        # Web search/fetch tools
        self.register_tool(
            ToolMetadata(
                name="web_fetch",
                description="Fetch content from a URL",
                parameters={
                    "url": {"type": "string", "required": True},
                },
                capabilities=["information_retrieval", "web_scraping"],
                supported_intents=[IntentCategory.INFORMATION_RETRIEVAL],
            )
        )

    def register_tool(self, tool: ToolMetadata):
        """Register a new tool.

        Args:
            tool: Tool metadata to register
        """
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> Optional[ToolMetadata]:
        """Get a tool by name.

        Args:
            name: Tool name

        Returns:
            ToolMetadata or None if not found
        """
        return self._tools.get(name)

    def discover_tools(
        self,
        intent: IntentCategory,
        requirement_keywords: List[str],
        limit: int = 5,
    ) -> List[ToolMetadata]:
        """Discover tools that match the intent and requirements.

        Args:
            intent: Intent category
            requirement_keywords: Keywords from requirement extraction
            limit: Maximum number of tools to return

        Returns:
            List of matching tools, sorted by relevance
        """
        candidates = []

        for tool in self._tools.values():
            if not tool.matches_intent(intent):
                continue

            score = tool.matches_requirement(requirement_keywords)
            candidates.append((score, tool))

        # Sort by score (descending)
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Return top N tools
        return [tool for _, tool in candidates[:limit]]

    def get_all_tools(self) -> List[ToolMetadata]:
        """Get all registered tools.

        Returns:
            List of all tools
        """
        return list(self._tools.values())

    def get_tools_by_capability(self, capability: str) -> List[ToolMetadata]:
        """Get tools that provide a specific capability.

        Args:
            capability: Capability name

        Returns:
            List of tools with the capability
        """
        return [
            tool
            for tool in self._tools.values()
            if capability in tool.capabilities
        ]


__all__ = ["ToolRegistry", "ToolMetadata", "Tool"]
