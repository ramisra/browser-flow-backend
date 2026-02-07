#!/usr/bin/env python3
"""Test creating a Notion page directly with NotionClient."""

import asyncio
import json
from app.core.tools.notion_client import NotionClient


async def main():
    client = NotionClient()
    result = await client.create_page(
        parent_page_id='0458964b3b4c448985ee35e0b5cf8702',
        title='Amazon Aruora - Browser Flow',
        children=[{
            'type': 'paragraph',
            'content': 'Amazon Aurora is a relational database service for OLTP workloads offered as part of Amazon Web Services (AWS). In this paper modern cloud applications expect from their database tier'
        }]
    )
    print("Result:")
    print(json.dumps(result, indent=2))
    print(f"\nPage ID: {result['page_id']}")
    print(f"URL: {result['url']}")


if __name__ == "__main__":
    asyncio.run(main())
