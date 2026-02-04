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

    async def search_similar_contexts(
        self,
        query_embedding: List[float],
        user_guest_id: Optional[uuid.UUID] = None,
        limit: int = 5,
    ) -> List[UserContext]:
        """Search for similar contexts using vector similarity.

        Args:
            query_embedding: Query embedding vector
            user_guest_id: Optional user guest ID to filter contexts
            limit: Maximum number of results

        Returns:
            List of similar UserContext instances
        """
        from pgvector.sqlalchemy import Vector
        from sqlalchemy import func, cast
        from sqlalchemy.sql import func as sql_func

        # Convert embedding to numpy array
        embedding_array = np.array(query_embedding, dtype=np.float32)
        if embedding_array.ndim != 1:
            embedding_array = embedding_array.flatten()
        embedding_array = np.ascontiguousarray(embedding_array, dtype=np.float32)

        # Build query with cosine similarity using pgvector's cosine_distance
        # Note: pgvector uses cosine_distance which returns 0 for identical vectors
        # We use 1 - cosine_distance for similarity score
        base_query = select(UserContext).where(
            UserContext.embedding.isnot(None)
        )

        # Filter by user if provided
        if user_guest_id:
            base_query = base_query.where(UserContext.user_guest_id == user_guest_id)

        # Use raw SQL for pgvector similarity search
        # pgvector's cosine_distance function
        similarity_expr = UserContext.embedding.cosine_distance(embedding_array)
        # Convert distance to similarity (1 - distance)
        similarity_score = (1 - similarity_expr).label("similarity_score")

        query = select(UserContext, similarity_score).where(
            UserContext.embedding.isnot(None)
        )

        if user_guest_id:
            query = query.where(UserContext.user_guest_id == user_guest_id)

        # Order by similarity (ascending distance = descending similarity)
        query = query.order_by(similarity_expr).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()

        # Attach similarity score to contexts
        contexts = []
        for row in rows:
            context = row[0]
            if len(row) > 1:
                context.similarity_score = float(row[1])
            contexts.append(context)

        return contexts
