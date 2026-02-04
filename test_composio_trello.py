#!/usr/bin/env python3
"""Test script for creating a Trello task via Composio MCP + Claude."""

import asyncio
import os
import sys
from typing import Optional

from composio import Composio
from composio_claude_agent_sdk import ClaudeAgentSDKProvider
from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, create_sdk_mcp_server
from dotenv import load_dotenv


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _build_prompt(
    title: str, board_name: Optional[str], list_name: Optional[str]
) -> str:
    if board_name and list_name:
        return (
            "Create a new Trello card with the title "
            f"'{title}' in the list '{list_name}' on the board '{board_name}'."
        )
    if board_name:
        return (
            "Create a new Trello card with the title "
            f"'{title}' in the first list on the board '{board_name}'."
        )
    return (
        "Create a new Trello card with the title "
        f"'{title}' in the first list of my first Trello board."
    )


async def main() -> None:
    load_dotenv()

    composio_api_key = _required_env("COMPOSIO_API_KEY")
    _required_env("ANTHROPIC_API_KEY")
    user_id = _required_env("USER_ID")

    title = sys.argv[1] if len(sys.argv) > 1 else "Test task from Composio script"
    board_name = os.getenv("TRELLO_BOARD_NAME")
    list_name = os.getenv("TRELLO_LIST_NAME")

    composio = Composio(
        api_key=composio_api_key,
        provider=ClaudeAgentSDKProvider(),
    )

    session = composio.create(
        user_id=user_id,
        toolkits=["notion", "composio"],
    )

    tools = session.tools()
    custom_server = create_sdk_mcp_server(
        name="composio",
        version="1.0.0",
        tools=tools,
    )

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a helpful assistant with access to Notion via Composio tools. "
        ),
        permission_mode="bypassPermissions",
        mcp_servers={"composio": custom_server},
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.query(_build_prompt(title, board_name, list_name))
        async for message in client.receive_response():
            print(message)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
