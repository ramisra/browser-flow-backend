"""Notion Data API client for create page, append blocks, and search."""

import json
import os
from typing import Any, Dict, List, Optional

import httpx

NOTION_VERSION = "2025-09-03"
BASE_URL = "https://api.notion.com/v1"

# Default sort for search: last_edited_time descending (API expects object, not string)
DEFAULT_SEARCH_SORT: Dict[str, Any] = {
    "direction": "descending",
    "timestamp": "last_edited_time",
}


def _normalize_dict_param(value: Any, allow_empty: bool = False) -> Optional[Dict[str, Any]]:
    """Ensure a param is a dict or None. Parse JSON string; reject empty dict unless allow_empty."""
    if value is None:
        return None
    if isinstance(value, dict):
        if not value and not allow_empty:
            return None
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(parsed, dict):
            return None
        if not parsed and not allow_empty:
            return None
        return parsed
    return None


def _rich_text(content: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}]


def _simplified_block_to_notion(block: Dict[str, Any]) -> Dict[str, Any]:
    """Convert simplified block { type, content, checked?, language? } to Notion API block."""
    block_type = (block.get("type") or "paragraph").lower()
    content = block.get("content") or ""
    out: Dict[str, Any] = {"object": "block", "type": block_type}
    rt = _rich_text(content)
    if block_type == "paragraph":
        out["paragraph"] = {"rich_text": rt}
    elif block_type == "to_do":
        out["to_do"] = {"rich_text": rt, "checked": bool(block.get("checked", False))}
    elif block_type in ("heading_1", "heading_2", "heading_3"):
        out[block_type] = {"rich_text": rt}
    elif block_type == "bulleted_list_item":
        out["bulleted_list_item"] = {"rich_text": rt}
    elif block_type == "numbered_list_item":
        out["numbered_list_item"] = {"rich_text": rt}
    elif block_type == "quote":
        out["quote"] = {"rich_text": rt}
    elif block_type == "divider":
        out["divider"] = {}
    elif block_type == "code":
        out["code"] = {
            "rich_text": rt,
            "language": block.get("language") or "plain text",
        }
    else:
        out["paragraph"] = {"rich_text": rt}
    return out


class NotionClientError(Exception):
    """Raised when a Notion API request fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class NotionClient:
    """Client for Notion Data API (pages, blocks, search)."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Notion client.

        Args:
            api_key: Notion integration token. Defaults to NOTION_TOKEN env var at request time.
        """
        self._api_key = api_key or os.getenv("NOTION_TOKEN")
        self._headers = {
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        }

    def _ensure_token(self) -> None:
        key = self._api_key or os.getenv("NOTION_TOKEN")
        if not key:
            raise NotionClientError(
                "NOTION_TOKEN is not set. Set it in .env or pass api_key to NotionClient."
            )
        self._headers["Authorization"] = f"Bearer {key}"

    async def create_page(
        self,
        parent_page_id: Optional[str] = None,
        title: str = "",
        children: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Create a page under a parent. Returns normalized { page_id, url, created_time?, title_plain? }.

        parent_page_id: Optional. If not provided, uses NOTION_PARENT_PAGE_ID from env.
        """
        resolved_parent = (parent_page_id or "").strip() or os.getenv("NOTION_PARENT_PAGE_ID") or ""
        if not resolved_parent:
            raise NotionClientError(
                "parent_page_id is required. Pass it to create_page or set NOTION_PARENT_PAGE_ID in .env."
            )
        payload: Dict[str, Any] = {
            "parent": {"type": "page_id", "page_id": resolved_parent},
            "properties": {
                "title": {
                    "type": "title",
                    "title": _rich_text(title),
                }
            },
        }
        if children:
            payload["children"] = [_simplified_block_to_notion(b) for b in children]
        self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/pages",
                headers=self._headers,
                json=payload,
            )
            print(f"Notion create_page response: {resp.json()}")
        if resp.status_code >= 400:
            raise NotionClientError(
                f"Notion create_page failed: {resp.status_code}",
                status_code=resp.status_code,
                body=resp.json() if resp.content else None,
            )
        data = resp.json()
        title_arr = (data.get("properties") or {}).get("title") or {}
        title_list = title_arr.get("title") or []
        title_plain = title_list[0].get("plain_text") if title_list else None
        return {
            "page_id": data["id"],
            "url": data.get("url"),
            "created_time": data.get("created_time"),
            "title_plain": title_plain,
        }

    async def search(
        self,
        query: str,
        filter_obj: Optional[Dict[str, Any]] = None,
        sort: Optional[Dict[str, Any]] = None,
        page_size: int = 100,
        start_cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search Notion. Returns normalized { results, page_ids, most_relevant_page_id, most_relevant_url, has_more?, next_cursor? }.

        filter and sort can be dicts or JSON strings; empty dicts/strings are omitted. sort defaults to
        { "direction": "descending", "timestamp": "last_edited_time" } so the body matches Notion API expectations.
        """
        payload: Dict[str, Any] = {"query": query}
        filter_normalized = _normalize_dict_param(filter_obj, allow_empty=True)
        if filter_normalized is not None:
            payload["filter"] = filter_normalized
        sort_normalized = _normalize_dict_param(sort, allow_empty=False)
        # API requires sort to be an object or undefined; use default object when not provided
        payload["sort"] = sort_normalized if sort_normalized is not None else DEFAULT_SEARCH_SORT
        if page_size is not None:
            payload["page_size"] = page_size
        if start_cursor is not None:
            payload["start_cursor"] = start_cursor
        self._ensure_token()
        print(f"search payload: {payload}")
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/search",
                headers=self._headers,
                json=payload,
            )
            print(f"Notion search response: {resp.json()}")
        if resp.status_code >= 400:
            raise NotionClientError(
                f"Notion search failed: {resp.status_code}",
                status_code=resp.status_code,
                body=resp.json() if resp.content else None,
            )
        data = resp.json()
        raw_results = data.get("results") or []
        results: List[Dict[str, Any]] = []
        page_ids: List[str] = []
        for item in raw_results:
            pid = item.get("id")
            if not pid:
                continue
            page_ids.append(pid)
            props = item.get("properties") or {}
            title_prop = props.get("title") or props.get("Name") or {}
            title_list = title_prop.get("title") or []
            title_plain = title_list[0].get("plain_text") if title_list else None
            results.append({
                "page_id": pid,
                "url": item.get("url"),
                "title_plain": title_plain,
            })
        first = results[0] if results else None
        return {
            "results": results,
            "page_ids": page_ids,
            "most_relevant_page_id": first["page_id"] if first else None,
            "most_relevant_url": first.get("url") if first else None,
            "has_more": data.get("has_more"),
            "next_cursor": data.get("next_cursor"),
        }

    async def append_block_children(
        self,
        block_id: str,
        children: List[Dict[str, Any]],
        position: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Append block children to a page (use page id as block_id). Returns { page_id, block_ids }."""
        notion_children = [_simplified_block_to_notion(b) for b in children]
        payload: Dict[str, Any] = {"children": notion_children}
        if position is not None:
            payload["position"] = position
        self._ensure_token()
        async with httpx.AsyncClient() as client:
            resp = await client.patch(
                f"{BASE_URL}/blocks/{block_id}/children",
                headers=self._headers,
                json=payload,
            )
            print(f"Notion append_block_children response: {resp.json()}")
        if resp.status_code >= 400:
            raise NotionClientError(
                f"Notion append_block_children failed: {resp.status_code}",
                status_code=resp.status_code,
                body=resp.json() if resp.content else None,
            )
        data = resp.json()
        block_ids = [b.get("id") for b in (data.get("results") or []) if b.get("id")]
        return {
            "page_id": block_id,
            "block_ids": block_ids,
        }


__all__ = ["NotionClient", "NotionClientError", "NOTION_VERSION"]
