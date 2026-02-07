"""API endpoints for user integration tokens (e.g. Notion API key)."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.integration_types import (
    get_capabilities,
    integration_requires_api_key,
    is_supported_integration,
    normalize_integration_tool,
)
from app.db.session import get_async_session
from app.repositories.user_integration_token_repository import (
    UserIntegrationTokenRepository,
)


class IntegrationCapability(BaseModel):
    """One supported integration for capabilities list."""

    id: str
    name: str
    description: Optional[str] = None
    requires_api_key: bool = True


class CapabilitiesResponse(BaseModel):
    """Response for GET /integrations/capabilities."""

    integrations: List[IntegrationCapability]


class SaveTokenRequest(BaseModel):
    """Body for POST /integrations/tokens. api_key optional for integrations that don't require it (e.g. Excel)."""

    integration_tool: str
    api_key: Optional[str] = None
    integration_metadata: Optional[Dict[str, Any]] = None


class TokenSummary(BaseModel):
    """One integration token summary (no api_key)."""

    id: str
    integration_tool: str
    created_at: datetime
    updated_at: datetime
    integration_metadata: Dict[str, Any] = {}


class SaveTokenResponse(BaseModel):
    """Response for POST /integrations/tokens."""

    id: str
    integration_tool: str
    created_at: datetime
    updated_at: datetime
    integration_metadata: Dict[str, Any] = {}


class UpdateMetadataRequest(BaseModel):
    """Body for PATCH /integrations/tokens/{token_id}."""

    integration_metadata: Dict[str, Any]


class TokensListResponse(BaseModel):
    """Response for GET /integrations/tokens."""

    tokens: List[TokenSummary]


router = APIRouter(tags=["integrations"], prefix="/integrations")


async def require_user_guest_id(
    x_user_guest_id: Optional[str] = Header(None, alias="X-User-Guest-ID"),
) -> uuid.UUID:
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


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities_list() -> CapabilitiesResponse:
    """List integration tools that browser_flow supports (e.g. Notion)."""
    caps = get_capabilities()
    print(caps)
    return CapabilitiesResponse(
        integrations=[
            IntegrationCapability(
                id=c["id"],
                name=c["name"],
                description=c.get("description"),
                requires_api_key=c.get("requires_api_key", True),
            )
            for c in caps
        ]
    )


@router.post("/tokens", response_model=SaveTokenResponse)
async def save_token(
    body: SaveTokenRequest,
    user_guest_id: uuid.UUID = Depends(require_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
) -> SaveTokenResponse:
    """Upsert integration token for the user. Sets is_deleted=False if re-adding."""
    if not is_supported_integration(body.integration_tool):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported integration_tool: {body.integration_tool}",
        )
    canonical = normalize_integration_tool(body.integration_tool)
    if integration_requires_api_key(canonical) and not (body.api_key or "").strip():
        raise HTTPException(
            status_code=400,
            detail="api_key is required for this integration and cannot be empty",
        )
    # Integrations that don't require a key (e.g. Excel) store empty string
    api_key_value = (body.api_key or "").strip() if integration_requires_api_key(canonical) else ""
    repo = UserIntegrationTokenRepository(session)
    token_row = await repo.upsert_token(
        user_guest_id=user_guest_id,
        integration_tool=canonical,
        api_key=api_key_value or (body.api_key or "").strip(),
        integration_metadata=body.integration_metadata,
    )
    await session.commit()
    return SaveTokenResponse(
        id=str(token_row.id),
        integration_tool=token_row.integration_tool,
        created_at=token_row.created_at,
        updated_at=token_row.updated_at,
        integration_metadata=token_row.integration_metadata or {},
    )


@router.get("/tokens", response_model=TokensListResponse)
async def list_tokens(
    user_guest_id: uuid.UUID = Depends(require_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
) -> TokensListResponse:
    """List active integration tokens for the user (deleted ones excluded)."""
    repo = UserIntegrationTokenRepository(session)
    items = await repo.list_by_user(user_guest_id)
    return TokensListResponse(
        tokens=[
            TokenSummary(
                id=str(t["id"]),
                integration_tool=t["integration_tool"],
                created_at=t["created_at"],
                updated_at=t["updated_at"],
                integration_metadata=t["integration_metadata"],
            )
            for t in items
        ]
    )


@router.patch("/tokens/{token_id}", response_model=SaveTokenResponse)
async def update_token_metadata(
    token_id: uuid.UUID,
    body: UpdateMetadataRequest,
    user_guest_id: uuid.UUID = Depends(require_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
) -> SaveTokenResponse:
    """Update integration_metadata for a token by id. Token must belong to the user."""
    print(f"token_id:{token_id}")
    repo = UserIntegrationTokenRepository(session)
    token_row = await repo.update_metadata(
        token_id=token_id,
        user_guest_id=user_guest_id,
        integration_metadata=body.integration_metadata,
    )
    if not token_row:
        raise HTTPException(
            status_code=404,
            detail="Integration token not found or does not belong to user",
        )
    await session.commit()
    return SaveTokenResponse(
        id=str(token_row.id),
        integration_tool=token_row.integration_tool,
        created_at=token_row.created_at,
        updated_at=token_row.updated_at,
        integration_metadata=token_row.integration_metadata or {},
    )


@router.delete("/tokens/{integration_tool}")
async def delete_token(
    integration_tool: str,
    user_guest_id: uuid.UUID = Depends(require_user_guest_id),
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, str]:
    """Soft-delete integration token for the user."""
    if not is_supported_integration(integration_tool):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported integration_tool: {integration_tool}",
        )
    canonical = normalize_integration_tool(integration_tool)
    repo = UserIntegrationTokenRepository(session)
    updated = await repo.soft_delete(user_guest_id=user_guest_id, integration_tool=canonical)
    await session.commit()
    if not updated:
        raise HTTPException(
            status_code=404,
            detail=f"No active token found for integration: {integration_tool}",
        )
    return {"status": "deleted", "integration_tool": canonical}
