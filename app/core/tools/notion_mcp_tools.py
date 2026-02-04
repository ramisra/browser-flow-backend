"""MCP tool wrappers for Notion operations (create page, append blocks, search)."""

import json
from typing import Any, Dict, List, Optional

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.core.tools.notion_client import NotionClient

NOTION_MCP_TOOL_NAMES = [
    "mcp__notion__notion_create_page",
    "mcp__notion__notion_append_blocks",
    "mcp__notion__notion_search",
]


def create_notion_mcp_server(
    notion_client: Optional[NotionClient] = None,
) -> Dict[str, Any]:
    """Create an SDK MCP server for Notion tools. Same pattern as Excel (no env check in factory)."""
    notion_client = notion_client or NotionClient()

    @tool(
        "notion_create_page",
        "Create a new page in Notion under a parent page. parent_page_id is optional; defaults to NOTION_PARENT_PAGE_ID from env. Returns page_id and url.",
        {"parent_page_id": str, "title": str, "children": list},
    )
    async def notion_create_page(args: Dict[str, Any]) -> Dict[str, Any]:
        parent_page_id: Optional[str] = args.get("parent_page_id") or None
        title: str = args.get("title") or ""
        children: Optional[List[Dict[str, Any]]] = args.get("children")
        result = await notion_client.create_page(
            parent_page_id=parent_page_id,
            title=title,
            children=children,
        )
        return {
            "content": [
                {"type": "text", "text": json.dumps(result)},
            ]
        }

    @tool(
        "notion_append_blocks",
        "Append blocks (paragraph, to_do, heading_1, etc.) to a Notion page. Use page_id as target. Returns page_id and block_ids.",
        {"page_id": str, "blocks": list, "position": dict},
    )
    async def notion_append_blocks(args: Dict[str, Any]) -> Dict[str, Any]:
        page_id: str = args.get("page_id") or ""
        blocks: List[Dict[str, Any]] = args.get("blocks") or []
        position: Optional[Dict[str, Any]] = args.get("position")
        result = await notion_client.append_block_children(
            block_id=page_id,
            children=blocks,
            position=position,
        )
        return {
            "content": [
                {"type": "text", "text": json.dumps(result)},
            ]
        }

    @tool(
        "notion_search",
        "Search Notion by query. Returns results, page_ids, most_relevant_page_id, most_relevant_url.",
        {"query": str, "filter": dict, "sort": dict},
    )
    async def notion_search(args: Dict[str, Any]) -> Dict[str, Any]:
        query: str = args.get("query") or ""
        filter_obj: Optional[Dict[str, Any]] = args.get("filter")
        sort: Optional[Dict[str, Any]] = args.get("sort")
        result = await notion_client.search(
            query=query,
            filter_obj=filter_obj,
            sort=sort,
        )
        return {
            "content": [
                {"type": "text", "text": json.dumps(result)},
            ]
        }

    return create_sdk_mcp_server(
        name="notion",
        version="1.0.0",
        tools=[notion_create_page, notion_append_blocks, notion_search],
    )


__all__ = ["create_notion_mcp_server", "NOTION_MCP_TOOL_NAMES"]
