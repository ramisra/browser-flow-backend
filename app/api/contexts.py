"""API endpoints for user contexts."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_async_session
from app.models.user_context import ContextType, UserContext
from app.repositories.user_context_repository import UserContextRepository
from app.services.embedding import EmbeddingService
from app.services.parent_topic_mapper import ParentTopicMapper


class ContextListItem(BaseModel):
    """Context item for list view."""

    context_id: str
    url: Optional[str]
    context_tags: List[str]
    raw_content: str
    user_defined_context: Optional[str]
    context_type: str
    timestamp: datetime
    parent_topic: Optional[str]
    has_children: bool = False

    class Config:
        from_attributes = True


class ContextGraphNode(BaseModel):
    """Node for graphical/hierarchical view."""

    id: str
    label: str
    url: Optional[str]
    tags: List[str]
    content_preview: str
    context_type: str
    timestamp: datetime
    parent_id: Optional[str] = None
    children: List["ContextGraphNode"] = []

    class Config:
        from_attributes = True


class ContextsListResponse(BaseModel):
    """Response for list view."""

    contexts: List[ContextListItem]
    total: int
    page: int
    page_size: int


class ContextsGraphResponse(BaseModel):
    """Response for graphical/hierarchical view."""

    nodes: List[ContextGraphNode]
    edges: List[Dict[str, str]]  # [{"source": "id1", "target": "id2"}]
    root_nodes: List[str]  # IDs of nodes without parents


router = APIRouter(tags=["contexts"])


async def get_user_guest_id(
    x_user_guest_id: Optional[str] = Header(None, alias="X-User-Guest-ID"),
) -> uuid.UUID:
    """Extract and validate user_guest_id from header.

    Args:
        x_user_guest_id: User guest ID from X-User-Guest-ID header

    Returns:
        UUID of the user guest ID

    Raises:
        HTTPException: If header is missing or invalid
    """
    if not x_user_guest_id:
        raise HTTPException(
            status_code=400,
            detail="X-User-Guest-ID header is required",
        )

    try:
        return uuid.UUID(x_user_guest_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user_guest_id format: {x_user_guest_id}",
        )


def _get_context_repository(session: AsyncSession) -> UserContextRepository:
    """Create a context repository instance."""
    embedding_service = EmbeddingService()
    parent_topic_mapper = ParentTopicMapper(embedding_service)
    return UserContextRepository(session, embedding_service, parent_topic_mapper)


@router.get("/contexts", response_model=ContextsListResponse)
async def get_contexts_list(
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    context_type: Optional[ContextType] = Query(None, description="Filter by context type"),
    tags: Optional[str] = Query(None, description="Comma-separated tags to filter by"),
    search: Optional[str] = Query(None, description="Search in content and tags"),
) -> ContextsListResponse:
    """
    Get all user contexts in list format.

    Supports pagination, filtering by type/tags, and search.
    """
    context_repo = _get_context_repository(session)

    # Get all contexts for the user
    all_contexts = await context_repo.get_user_contexts_by_guest_id(user_guest_id)

    # Apply filters
    filtered_contexts = all_contexts

    if context_type:
        filtered_contexts = [c for c in filtered_contexts if c.context_type == context_type]

    if tags:
        tag_list = [tag.strip().lower() for tag in tags.split(",")]
        filtered_contexts = [
            c
            for c in filtered_contexts
            if any(tag in [t.lower() for t in c.context_tags] for tag in tag_list)
        ]

    if search:
        search_lower = search.lower()
        filtered_contexts = [
            c
            for c in filtered_contexts
            if search_lower in c.raw_content.lower()
            or search_lower in (c.user_defined_context or "").lower()
            or any(search_lower in tag.lower() for tag in c.context_tags)
        ]

    # Create a set of context IDs that have children
    context_ids_with_children = {
        c.parent_topic for c in all_contexts if c.parent_topic is not None
    }

    # Apply pagination
    total = len(filtered_contexts)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_contexts = filtered_contexts[start:end]

    # Convert to response models
    context_items = [
        ContextListItem(
            context_id=str(c.context_id),
            url=c.url,
            context_tags=c.context_tags,
            raw_content=c.raw_content[:500] + "..." if len(c.raw_content) > 500 else c.raw_content,  # Truncate for list view
            user_defined_context=c.user_defined_context,
            context_type=c.context_type.value.lower(),  # Convert to lowercase for API
            timestamp=c.timestamp,
            parent_topic=str(c.parent_topic) if c.parent_topic else None,
            has_children=str(c.context_id) in context_ids_with_children,
        )
        for c in paginated_contexts
    ]

    return ContextsListResponse(
        contexts=context_items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/contexts/graph", response_model=ContextsGraphResponse)
async def get_contexts_graph(
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
    max_depth: Optional[int] = Query(None, ge=1, le=10, description="Maximum depth for graph traversal"),
) -> ContextsGraphResponse:
    """
    Get all user contexts in hierarchical/graph format.

    Returns nodes and edges suitable for graphical visualization (e.g., D3.js, vis.js).
    """
    context_repo = _get_context_repository(session)

    # Get all contexts for the user
    all_contexts = await context_repo.get_user_contexts_by_guest_id(user_guest_id)

    # Build a map of context_id -> context for quick lookup
    context_map: Dict[uuid.UUID, UserContext] = {c.context_id: c for c in all_contexts}

    # Build nodes and edges
    nodes: List[ContextGraphNode] = []
    edges: List[Dict[str, str]] = []
    root_node_ids: List[str] = []
    node_map: Dict[str, ContextGraphNode] = {}

    # First pass: Create all nodes
    for context in all_contexts:
        # Create content preview (first 200 chars)
        content_preview = (
            context.raw_content[:200] + "..."
            if len(context.raw_content) > 200
            else context.raw_content
        )

        # Create label from URL, title, or first part of content
        label = context.url or content_preview[:50] or "Untitled"

        node = ContextGraphNode(
            id=str(context.context_id),
            label=label,
            url=context.url,
            tags=context.context_tags,
            content_preview=content_preview,
            context_type=context.context_type.value.lower(),  # Convert to lowercase for API
            timestamp=context.timestamp,
            parent_id=str(context.parent_topic) if context.parent_topic else None,
            children=[],
        )

        nodes.append(node)
        node_map[str(context.context_id)] = node

        # Track root nodes
        if not context.parent_topic:
            root_node_ids.append(str(context.context_id))

    # Second pass: Build edges and parent-child relationships
    for context in all_contexts:
        context_id_str = str(context.context_id)
        node = node_map[context_id_str]

        # Add edge if there's a parent
        if context.parent_topic:
            parent_id_str = str(context.parent_topic)
            edges.append({"source": parent_id_str, "target": context_id_str})

            # Add to parent's children list if parent exists
            if parent_id_str in node_map:
                node_map[parent_id_str].children.append(node)

    return ContextsGraphResponse(
        nodes=nodes,
        edges=edges,
        root_nodes=root_node_ids,
    )


@router.get("/contexts/{context_id}")
async def get_context_detail(
    context_id: str,
    user_guest_id: uuid.UUID = Depends(get_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """
    Get detailed information about a specific context.

    Includes full content and related contexts.
    """
    try:
        context_uuid = uuid.UUID(context_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid context_id format")

    context_repo = _get_context_repository(session)

    context = await context_repo.get_user_context(context_uuid)

    if not context:
        raise HTTPException(status_code=404, detail="Context not found")

    # Verify ownership
    if context.user_guest_id != user_guest_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Get related contexts (parent and children)
    all_contexts = await context_repo.get_user_contexts_by_guest_id(user_guest_id)
    parent_context = (
        next((c for c in all_contexts if c.context_id == context.parent_topic), None)
        if context.parent_topic
        else None
    )
    children_contexts = [
        c for c in all_contexts if c.parent_topic == context.context_id
    ]

    return {
        "context_id": str(context.context_id),
        "url": context.url,
        "context_tags": context.context_tags,
        "raw_content": context.raw_content,
        "user_defined_context": context.user_defined_context,
        "context_type": context.context_type.value.lower(),  # Convert to lowercase for API
        "timestamp": context.timestamp,
        "parent_topic": str(context.parent_topic) if context.parent_topic else None,
        "parent": {
            "context_id": str(parent_context.context_id),
            "url": parent_context.url,
            "tags": parent_context.context_tags,
        }
        if parent_context
        else None,
        "children": [
            {
                "context_id": str(c.context_id),
                "url": c.url,
                "tags": c.context_tags,
                "content_preview": c.raw_content[:200] + "..." if len(c.raw_content) > 200 else c.raw_content,
            }
            for c in children_contexts
        ],
    }


__all__ = ["router"]
