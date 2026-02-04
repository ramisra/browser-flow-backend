"""MCP tool wrappers for Excel operations."""

import json
from typing import Any, Dict, List, Optional

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.core.tools.excel_tools import ExcelTools

EXCEL_MCP_TOOL_NAME = "mcp__excel__excel_write"


def create_excel_mcp_server(
    excel_tools: Optional[ExcelTools] = None,
) -> Dict[str, Any]:
    """Create an SDK MCP server for Excel tools."""
    excel_tools = excel_tools or ExcelTools()

    @tool(
        "excel_write",
        "Create an Excel file with the given data and columns.",
        {"data": list, "columns": list, "file_name": str},
    )
    async def excel_write(
        args: Dict[str, Any]
    ) -> Dict[str, Any]:
        data: List[Dict[str, Any]] = args.get("data") or []
        columns: Optional[List[str]] = args.get("columns")
        file_name: Optional[str] = args.get("file_name")

        file_path = await excel_tools.create_excel_file(
            data=data,
            columns=columns,
            file_name=file_name,
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({"file_path": file_path}),
                }
            ]
        }

    return create_sdk_mcp_server(
        name="excel",
        version="1.0.0",
        tools=[excel_write],
    )


__all__ = ["create_excel_mcp_server", "EXCEL_MCP_TOOL_NAME"]
