#!/usr/bin/env python3
"""Test script for creating/appending notes in Google Docs via Composio MCP + Claude.

Selects the Google Doc mentioned by the user and appends the given content.

Authentication:
  Connections in Composio are tied to an entity (the user_id you pass). This script
  uses USER_ID from .env. If you already connected Google Docs in the Composio
  platform, USER_ID must match the entity ID you used there—otherwise Composio
  will ask for auth again. Set USER_ID to that same entity (e.g. from Composio
  dashboard / Connected accounts) and no runtime auth should be needed.

Usage:
  python test_composio_googledocs.py
  python test_composio_googledocs.py "My Meeting Notes"
  python test_composio_googledocs.py "My Meeting Notes" "Discussed Q1 goals and next steps."
  python test_composio_googledocs.py --doc-id "1abc..." "Content to append"

Environment (optional):
  GOOGLE_DOC_NAME  - Default doc name to find and append to
  GOOGLE_DOC_ID    - Specific document ID (if set, doc name is ignored)
  GOOGLE_DOC_NOTE_CONTENT - Default content to append
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


def _parse_args() -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse argv into (doc_name_or_id, content, doc_id_flag).

    Supports:
      script "Doc Name" "content"
      script --doc-id "id" "content"
    """
    argv = sys.argv[1:]
    doc_id = None
    if argv and argv[0] == "--doc-id":
        if len(argv) < 3:
            raise SystemExit("Usage: ... --doc-id <document_id> <content>")
        doc_id = argv[1]
        content = argv[2] if len(argv) > 2 else None
        return None, content, doc_id
    doc_name = argv[0] if len(argv) > 0 else None
    content = argv[1] if len(argv) > 1 else None
    return doc_name, content, doc_id


def _build_prompt(
    doc_name: Optional[str],
    content: Optional[str],
    doc_id: Optional[str],
) -> str:
    if doc_id:
        return (
            f"Using the Google Doc with document ID '{doc_id}', append the following "
            f"content to the end of the document:\n\n{content or '(no content)'}\n\n"
            "Use Composio Google Docs tools: get the document by ID, then insert or append "
            "the text at the end of the document."
        )
    if doc_name and content:
        return (
            f"Find the Google Doc named or titled '{doc_name}', then append the following "
            f"content to the end of that document:\n\n{content}\n\n"
            "Use the available Google Docs tools: search for the document by name, "
            "then insert/append the text at the end of the document."
        )
    if doc_name:
        return (
            f"Find the Google Doc named or titled '{doc_name}' and append a short test note "
            "to the end of it (e.g. 'Test append from Composio script'). "
            "Use search to find the doc, then insert text at the end."
        )
    return (
        "List or find one of my recent Google Docs, then append a short test note "
        "to the end of it (e.g. 'Test append from Composio script'). "
        "Use the Google Docs tools to search/list documents and insert text at the end."
    )


async def main() -> None:
    load_dotenv()

    composio_api_key = _required_env("COMPOSIO_API_KEY")
    _required_env("ANTHROPIC_API_KEY")
    user_id = _required_env("USER_ID")
    print(
        f"Using Composio entity/user_id: {user_id}\n"
        "If you see an auth link, ensure USER_ID matches the entity you used when "
        "connecting Google Docs in Composio (dashboard / Connected accounts).\n"
    )

    doc_name, content, doc_id = _parse_args()
    doc_name = doc_name or os.getenv("GOOGLE_DOC_NAME")
    if content is None:
        content = os.getenv("GOOGLE_DOC_NOTE_CONTENT")
    doc_id = doc_id or os.getenv("GOOGLE_DOC_ID")

    default_doc = os.getenv("GOOGLE_DOC_NAME", "Test note from Composio script")
    if not doc_name and not doc_id:
        doc_name = default_doc

    composio = Composio(
        api_key=composio_api_key,
        provider=ClaudeAgentSDKProvider(),
    )

    session = composio.create(
        user_id=user_id,
        toolkits=["googledocs", "composio"],
    )

    tools = session.tools()
    custom_server = create_sdk_mcp_server(
        name="composio",
        version="1.0.0",
        tools=tools,
    )

    options = ClaudeAgentOptions(
        system_prompt=(
            "You are a helpful assistant with access to Google Docs via Composio tools. "
            "Find or select the document the user specifies (by name or document ID), "
            "then append the given content to the end of that document. "
            "Use search/list to find docs by name; use get document by ID when an ID is provided. "
            "When appending, insert the new text at the end of the document."
        ),
        permission_mode="bypassPermissions",
        mcp_servers={"composio": custom_server},
    )

    prompt = _build_prompt(doc_name, content, doc_id)
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
