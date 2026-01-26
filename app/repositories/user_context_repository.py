"""Repository for UserContext database operations."""

import uuid
from datetime import datetime
from typing import List, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_context import ContextType, UserContext
from app.services.embedding import EmbeddingService
from app.services.parent_topic_mapper import ParentTopicMapper


class UserContextRepository:
    """Repository for UserContext CRUD operations."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_service: EmbeddingService,
        parent_topic_mapper: ParentTopicMapper,
    ):
        """Initialize the repository.

        Args:
            session: Database session
            embedding_service: Service for generating embeddings
            parent_topic_mapper: Service for finding parent topics
        """
        self.session = session
        self.embedding_service = embedding_service
        self.parent_topic_mapper = parent_topic_mapper

    async def create_user_context(
        self,
        raw_content: str,
        context_tags: List[str],
        user_guest_id: uuid.UUID,
        url: Optional[str] = None,
        user_defined_context: Optional[str] = None,
        context_type: ContextType = ContextType.TEXT,
        find_parent: bool = True,
    ) -> UserContext:
        """Create a new user context with embedding and parent topic.

        Args:
            raw_content: Raw content text
            context_tags: List of tags for the context
            user_guest_id: User identifier
            url: Optional URL for the context
            user_defined_context: Optional additional user-defined context
            context_type: Type of context (text, image, video)
            find_parent: Whether to find and set parent topic

        Returns:
            Created UserContext instance
        """
        # Generate embedding
        embedding_list = await self.embedding_service.generate_embedding(raw_content)
        
        # Convert embedding for pgvector compatibility
        # For asyncpg, pgvector needs the embedding as a numpy array
        # The array must be float32 and properly formatted
        embedding_array = None
        if embedding_list:
            # Convert to numpy array with explicit dtype
            embedding_array = np.array(embedding_list, dtype=np.float32)
            # Ensure it's a 1D array (not nested)
            if embedding_array.ndim != 1:
                embedding_array = embedding_array.flatten()
            # Ensure contiguous memory layout
            embedding_array = np.ascontiguousarray(embedding_array, dtype=np.float32)

        # Find parent topic if requested
        parent_topic_id: Optional[uuid.UUID] = None
        if find_parent:
            parent_topic_id = await self.parent_topic_mapper.find_parent_topic(
                self.session, context_tags, embedding_list, user_guest_id
            )

        # Create context
        user_context = UserContext(
            context_tags=context_tags,
            raw_content=raw_content,
            user_defined_context=user_defined_context,
            embedding=embedding_array,
            url=url,
            context_type=context_type,
            user_guest_id=user_guest_id,
            timestamp=datetime.utcnow(),
            parent_topic=parent_topic_id,
        )

        self.session.add(user_context)
        # Don't flush immediately - let the caller handle the transaction
        # This avoids type conversion issues with pgvector and asyncpg
        return user_context

    async def get_user_context(
        self, context_id: uuid.UUID
    ) -> Optional[UserContext]:
        """Get a user context by ID.

        Args:
            context_id: Context identifier

        Returns:
            UserContext instance or None if not found
        """
        result = await self.session.execute(
            select(UserContext).where(UserContext.context_id == context_id)
        )
        return result.scalar_one_or_none()

    async def get_user_contexts_by_ids(
        self, context_ids: List[uuid.UUID]
    ) -> List[UserContext]:
        """Get multiple user contexts by IDs.

        Args:
            context_ids: List of context identifiers

        Returns:
            List of UserContext instances
        """
        if not context_ids:
            return []

        result = await self.session.execute(
            select(UserContext).where(UserContext.context_id.in_(context_ids))
        )
        return list(result.scalars().all())

    async def get_user_contexts_by_guest_id(
        self, user_guest_id: uuid.UUID, limit: Optional[int] = None
    ) -> List[UserContext]:
        """Get all user contexts for a guest ID.

        Args:
            user_guest_id: User identifier
            limit: Optional limit on number of results

        Returns:
            List of UserContext instances
        """
        query = (
            select(UserContext)
            .where(UserContext.user_guest_id == user_guest_id)
            .order_by(UserContext.timestamp.desc())
        )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())
