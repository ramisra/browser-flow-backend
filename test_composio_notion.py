#!/usr/bin/env python3
"""Test script for creating a Notion note via Composio MCP + Claude.

Creates a note on Notion based on the page name and content prompted by the user.
Usage:
  python test_composio_notion.py
  python test_composio_notion.py "Meeting notes"
  python test_composio_notion.py "Meeting notes" "Discussed Q1 goals and roadmap."
"""

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


def _build_prompt(page_name: str, content: Optional[str]) -> str:
    if content:
        return (
            f"Create a new note in Notion with the page title '{page_name}' "
            f"and add the following content:\n\n{content}\n\n"
            "Use the available Notion tools to create the page and add the content "
            "as blocks (headings, paragraphs, bullets as appropriate)."
        )
    return (
        f"Create a new note in Notion with the page title '{page_name}'.\n\n"
        "Use the available Notion tools to create the page. "
        "If you have a default workspace or parent page, create it there."
    )


async def main() -> None:
    load_dotenv()

    composio_api_key = _required_env("COMPOSIO_API_KEY")
    _required_env("ANTHROPIC_API_KEY")
    user_id = _required_env("USER_ID")

    page_name = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.getenv("NOTION_PAGE_NAME", "Test note from Composio script")
    )
    content = sys.argv[2] if len(sys.argv) > 2 else os.getenv("NOTION_NOTE_CONTENT")

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
            "Create and organize notes in Notion: create pages, add content blocks, "
            "and structure content with headings and bullets when appropriate."
        ),
        permission_mode="bypassPermissions",
        mcp_servers={"composio": custom_server},
    )

    prompt = _build_prompt(page_name, content)
    preview = f"{prompt[:200]}..." if len(prompt) > 200 else prompt
    print(f"Prompt: {preview}\n")

    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            print(message)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print(f"Error: {exc}")
        sys.exit(1)
