"""Tool/MCP integration component for agents."""

from typing import Any, Dict, List, Optional

from app.core.tool_registry import ToolRegistry, ToolMetadata


class ToolIntegration:
    """Integration with tools and Model Context Protocol servers."""

    def __init__(self, tool_registry: ToolRegistry):
        """Initialize tool integration.

        Args:
            tool_registry: Tool registry instance
        """
        self.tool_registry = tool_registry

    def get_tool(self, tool_name: str) -> Optional[ToolMetadata]:
        """Get a tool by name.

        Args:
            tool_name: Name of the tool

        Returns:
            ToolMetadata or None if not found
        """
        return self.tool_registry.get_tool(tool_name)

    def discover_tools(
        self,
        capabilities: List[str],
        limit: int = 10,
    ) -> List[ToolMetadata]:
        """Discover tools by capabilities.

        Args:
            capabilities: List of required capabilities
            limit: Maximum number of tools to return

        Returns:
            List of matching tools
        """
        all_tools = []
        for capability in capabilities:
            tools = self.tool_registry.get_tools_by_capability(capability)
            all_tools.extend(tools)

        # Remove duplicates
        seen = set()
        unique_tools = []
        for tool in all_tools:
            if tool.name not in seen:
                seen.add(tool.name)
                unique_tools.append(tool)

        return unique_tools[:limit]

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
    ) -> Any:
        """Execute a tool with given parameters.

        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or execution fails
        """
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' not found")

        # For now, this is a placeholder
        # Actual tool execution will be implemented based on tool type
        # (Composio tools, MCP tools, custom tools, etc.)
        raise NotImplementedError(
            f"Tool execution for '{tool_name}' not yet implemented. "
            "This will be implemented based on the tool type."
        )

    def get_available_tools(self) -> List[ToolMetadata]:
        """Get all available tools.

        Returns:
            List of all registered tools
        """
        return self.tool_registry.get_all_tools()


__all__ = ["ToolIntegration"]
