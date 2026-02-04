"""Composio tool provider for agents when tools are not in the MCP pool."""

import logging
import os
from typing import Any, Dict, List, Optional, Set

from claude_agent_sdk import create_sdk_mcp_server
from composio import Composio
from composio_claude_agent_sdk import ClaudeAgentSDKProvider

logger = logging.getLogger(__name__)

# Mapping from Tool Registry tool names to Composio toolkit(s)
# When a required tool is not in our MCP pool, we use this to determine
# which Composio toolkit(s) to load
TOOL_TO_COMPOSIO_TOOLKIT: Dict[str, List[str]] = {
    "trello_create_card": ["trello"],
    "trello_create_list": ["trello"],
    "google_sheets_append": ["google_sheets"],
    "google_sheets_read": ["google_sheets"],
    "notion_create_page": ["notion"],
    "notion_add_page_content": ["notion"],
    "notion_add_multiple_page_content": ["notion"],
    "notion_append_block_children": ["notion"],
    "notion_search_notion_page": ["notion"],
    "notion_update_page": ["notion"],
    # Excel tools - we have our own MCP; include for completeness if Composio fallback needed
    "excel_write": ["google_sheets"],  # Composio may use Sheets as Excel alternative
    "excel_append": ["google_sheets"],
    "excel_read": ["google_sheets"],
    # Generic fallback - "composio" toolkit provides meta-tools
    "_default": ["composio"],
}


def get_toolkits_for_missing_tools(missing_tool_names: List[str]) -> List[str]:
    """Resolve Composio toolkits from missing tool names.

    Args:
        missing_tool_names: List of tool names not available in MCP pool

    Returns:
        Deduplicated list of Composio toolkit names to load
    """
    toolkits: Set[str] = set()
    for name in missing_tool_names:
        # Strip mcp__server__ prefix if present (e.g., mcp__excel__excel_write -> excel_write)
        base_name = name
        if "__" in name:
            parts = name.split("__")
            if len(parts) >= 3:
                base_name = f"{parts[1]}_{parts[2]}"
            elif len(parts) == 2:
                base_name = parts[1]

        if base_name in TOOL_TO_COMPOSIO_TOOLKIT:
            toolkits.update(TOOL_TO_COMPOSIO_TOOLKIT[base_name])
        else:
            toolkits.update(TOOL_TO_COMPOSIO_TOOLKIT["_default"])

    return list(toolkits)


def create_composio_mcp_server(
    user_id: str,
    toolkits: List[str],
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create an MCP server from Composio tools for the given user and toolkits.

    Args:
        user_id: External user ID for Composio session (e.g., user_guest_id)
        toolkits: List of Composio toolkit names (e.g., ["trello", "composio"])
        api_key: Optional Composio API key; falls back to COMPOSIO_API_KEY env

    Returns:
        MCP server dict for ClaudeAgentOptions.mcp_servers, or None if Composio
        is not configured or fails
    """
    key = api_key or os.getenv("COMPOSIO_API_KEY")
    if not key:
        logger.warning(
            "COMPOSIO_API_KEY not set; skipping Composio tool provider. "
            "Set COMPOSIO_API_KEY in .env to enable Composio fallback."
        )
        return None

    try:
        composio = Composio(
            api_key=key,
            provider=ClaudeAgentSDKProvider(),
        )

        session = composio.create(
            user_id=str(user_id),
            toolkits=toolkits if toolkits else ["composio"],
        )

        tools = session.tools()
        return create_sdk_mcp_server(
            name="composio",
            version="1.0.0",
            tools=tools,
        )
    except Exception as e:
        logger.exception("Failed to create Composio MCP server: %s", e)
        return None


__all__ = [
    "create_composio_mcp_server",
    "get_toolkits_for_missing_tools",
    "TOOL_TO_COMPOSIO_TOOLKIT",
]
