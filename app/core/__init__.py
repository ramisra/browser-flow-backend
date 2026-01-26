"""Core agent logic for URL context collection and action planning."""

# Note: ToolRegistry and ToolMetadata should be imported directly from app.core.tool_registry
# to avoid circular import issues with app.db.session