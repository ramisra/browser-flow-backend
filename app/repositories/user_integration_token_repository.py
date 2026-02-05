"""Repository for UserIntegrationToken database operations."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_integration_token import UserIntegrationToken


class UserIntegrationTokenRepository:
    """Repository for user integration token CRUD and soft-delete."""

    def __init__(self, session: AsyncSession):
        """Initialize the repository.

        Args:
            session: Database session
        """
        self.session = session

    async def get_token(
        self,
        user_guest_id: uuid.UUID,
        integration_tool: str,
    ) -> Optional[str]:
        """Return api_key for the user and integration only when not soft-deleted.

        Args:
            user_guest_id: User guest ID
            integration_tool: Integration tool id (e.g. 'notion')

        Returns:
            api_key string or None if not found or is_deleted
        """
        result = await self.session.execute(
            select(UserIntegrationToken.api_key).where(
                UserIntegrationToken.user_guest_id == user_guest_id,
                UserIntegrationToken.integration_tool == integration_tool,
                UserIntegrationToken.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def upsert_token(
        self,
        user_guest_id: uuid.UUID,
        integration_tool: str,
        api_key: str,
        integration_metadata: Optional[Dict[str, Any]] = None,
    ) -> UserIntegrationToken:
        """Insert or update token for (user_guest_id, integration_tool). Sets is_deleted=False.

        Args:
            user_guest_id: User guest ID
            integration_tool: Integration tool id (e.g. 'notion')
            api_key: Secret to store
            integration_metadata: Optional JSON metadata for the integration

        Returns:
            Created or updated UserIntegrationToken instance
        """
        result = await self.session.execute(
            select(UserIntegrationToken).where(
                UserIntegrationToken.user_guest_id == user_guest_id,
                UserIntegrationToken.integration_tool == integration_tool,
            )
        )
        row = result.scalar_one_or_none()

        now = datetime.utcnow()
        meta = integration_metadata if integration_metadata is not None else {}
        if row:
            row.api_key = api_key
            row.is_deleted = False
            row.integration_metadata = meta
            row.updated_at = now
            await self.session.flush()
            await self.session.refresh(row)
            return row

        token = UserIntegrationToken(
            user_guest_id=user_guest_id,
            integration_tool=integration_tool,
            api_key=api_key,
            integration_metadata=meta,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )
        self.session.add(token)
        await self.session.flush()
        await self.session.refresh(token)
        return token

    async def list_by_user(
        self,
        user_guest_id: uuid.UUID,
    ) -> List[Dict[str, Any]]:
        """Return active integrations for the user (is_deleted=False). Does not expose api_key.

        Args:
            user_guest_id: User guest ID

        Returns:
            List of dicts with integration_tool, created_at, updated_at
        """
        result = await self.session.execute(
            select(
                UserIntegrationToken.id,
                UserIntegrationToken.integration_tool,
                UserIntegrationToken.created_at,
                UserIntegrationToken.updated_at,
                UserIntegrationToken.integration_metadata,
            ).where(
                UserIntegrationToken.user_guest_id == user_guest_id,
                UserIntegrationToken.is_deleted.is_(False),
            )
        )
        rows = result.all()
        return [
            {
                "id": r.id,
                "integration_tool": r.integration_tool,
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "integration_metadata": r.integration_metadata or {},
            }
            for r in rows
        ]

    async def soft_delete(
        self,
        user_guest_id: uuid.UUID,
        integration_tool: str,
    ) -> bool:
        """Set is_deleted=True and updated_at for the row. Return True if a row was updated.

        Args:
            user_guest_id: User guest ID
            integration_tool: Integration tool id

        Returns:
            True if a row was found and updated, False otherwise (for 404)
        """
        stmt = (
            update(UserIntegrationToken)
            .where(
                UserIntegrationToken.user_guest_id == user_guest_id,
                UserIntegrationToken.integration_tool == integration_tool,
                UserIntegrationToken.is_deleted.is_(False),
            )
            .values(is_deleted=True, updated_at=datetime.utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_by_id(
        self,
        token_id: uuid.UUID,
        user_guest_id: uuid.UUID,
    ) -> Optional[UserIntegrationToken]:
        """Return the token row by id if it belongs to the user and is not deleted.

        Args:
            token_id: Integration token UUID
            user_guest_id: User guest ID

        Returns:
            UserIntegrationToken or None
        """
        result = await self.session.execute(
            select(UserIntegrationToken).where(
                UserIntegrationToken.id == token_id,
                UserIntegrationToken.user_guest_id == user_guest_id,
                UserIntegrationToken.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def update_metadata(
        self,
        token_id: uuid.UUID,
        user_guest_id: uuid.UUID,
        integration_metadata: Dict[str, Any],
    ) -> Optional[UserIntegrationToken]:
        """Update integration_metadata for a token by id. Returns the row if updated.

        Args:
            token_id: Integration token UUID
            user_guest_id: User guest ID
            integration_metadata: New metadata dict (stored as JSONB)

        Returns:
            Updated UserIntegrationToken or None if not found
        """
        row = await self.get_by_id(token_id=token_id, user_guest_id=user_guest_id)
        print(f"Row: {row}")
        if not row:
            return None
        row.integration_metadata = integration_metadata
        row.updated_at = datetime.utcnow()
        await self.session.flush()
        await self.session.refresh(row)
        return row
