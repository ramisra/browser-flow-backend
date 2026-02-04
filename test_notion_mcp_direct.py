#!/usr/bin/env python3
"""Test script for creating a Notion note via direct Notion MCP (no Composio).

Uses the open-source @notionhq/notion-mcp-server with NOTION_TOKEN.
Requires: Node.js/npx, NOTION_TOKEN in .env (create integration at notion.so/profile/integrations).

IMPORTANT: Share at least one page with your integration (page -> ... -> Connections ->
Add connections -> select your integration). Set NOTION_PARENT_PAGE_ID to that page's
ID if you want notes created under it (optional; Claude can also use search results).

Usage:
  python test_notion_mcp_direct.py
  python test_notion_mcp_direct.py "Meeting notes"
  python test_notion_mcp_direct.py "Meeting notes" "Discussed Q1 goals and roadmap."
"""

import asyncio
import os
import sys
from typing import Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient
from dotenv import load_dotenv


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"For NOTION_TOKEN: create an integration at notion.so/profile/integrations, "
            "copy the token, and add it to .env. Connect target pages to the integration."
        )
    return value


def _build_prompt(
    page_name: str, content: Optional[str], parent_page_id: Optional[str] = None
) -> str:
    base = (
        f"Create a new note in Notion with the page title '{page_name}'"
        + (f" and add the following content:\n\n{content}\n\n" if content else ".\n\n")
    )
    base += (
        "Use the available Notion tools to create the page and add the content "
        "as blocks (headings, paragraphs, bullets as appropriate).\n\n"
    )
    if parent_page_id:
        base += (
            f"Use page_id '{parent_page_id}' as the parent. "
            "When calling API-post-page, pass parent as a JSON object: "
            '{"type": "page_id", "page_id": "<uuid>"} — do NOT pass it as a string.\n\n'
        )
    base += (
        "CRITICAL: For API-post-page, the parent parameter must be a JSON object "
        '(e.g. {"type": "page_id", "page_id": "actual-uuid"}), never a JSON string.\n'
        "If search returns no pages, the user must share a page with the integration first."
    )
    return base


async def main() -> None:
    load_dotenv()

    notion_token = _required_env("NOTION_TOKEN")
    _required_env("ANTHROPIC_API_KEY")

    page_name = (
        sys.argv[1]
        if len(sys.argv) > 1
        else os.getenv("NOTION_PAGE_NAME", "Test note from direct Notion MCP script")
    )
    content = sys.argv[2] if len(sys.argv) > 2 else os.getenv("NOTION_NOTE_CONTENT")
    parent_page_id = os.getenv("NOTION_PARENT_PAGE_ID") or None

    notion_mcp_server = {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@notionhq/notion-mcp-server"],
        "env": {"NOTION_TOKEN": notion_token},
    }

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a helpful assistant with access to Notion via the Notion MCP server. "
            "Create and organize notes in Notion: create pages, add content blocks, "
            "and structure content with headings and bullets when appropriate. "
            "Use search to find a parent page, or use the parent_page_id from the prompt. "
            "CRITICAL for API-post-page: pass parent as a JSON object "
            '{"type": "page_id", "page_id": "<uuid>"}, never as a string. '
            "If search returns empty, the user must share a page with the integration first."
        ),
        permission_mode="bypassPermissions",
        mcp_servers={"notion": notion_mcp_server},
    )

    prompt = _build_prompt(page_name, content, parent_page_id)
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
