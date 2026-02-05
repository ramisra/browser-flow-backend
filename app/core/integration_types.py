"""Supported integration tools and validation for user integration tokens."""

from typing import Any, Dict, List

# Canonical id used in API and DB (lowercase)
NOTION = "notion"

# Metadata for capabilities API: id, name, optional description
SUPPORTED_INTEGRATIONS: List[Dict[str, Any]] = [
    {
        "id": NOTION,
        "name": "Notion",
        "description": "Create and update pages, append blocks, and search in Notion.",
    },
]

_SUPPORTED_IDS = {item["id"] for item in SUPPORTED_INTEGRATIONS}


def is_supported_integration(integration_tool: str) -> bool:
    """Return True if integration_tool is a supported integration (case-insensitive for id)."""
    if not integration_tool or not isinstance(integration_tool, str):
        return False
    return integration_tool.strip().lower() in _SUPPORTED_IDS


def normalize_integration_tool(integration_tool: str) -> str:
    """Return canonical id (lowercase) for a supported integration, or raise ValueError."""
    if not is_supported_integration(integration_tool):
        raise ValueError(f"Unsupported integration_tool: {integration_tool}")
    return integration_tool.strip().lower()


def get_capabilities() -> List[Dict[str, Any]]:
    """Return list of supported integration capabilities for API response."""
    return [dict(item) for item in SUPPORTED_INTEGRATIONS]
