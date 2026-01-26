"""Parent topic mapping service using hybrid tag and embedding matching."""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_context import UserContext
from app.services.embedding import EmbeddingService


class ParentTopicMapper:
    """Service for finding parent topics using hybrid tag and embedding matching."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        similarity_threshold: float = 0.7,
        min_tag_overlap: int = 1,
    ):
        """Initialize the parent topic mapper.

        Args:
            embedding_service: Service for generating and comparing embeddings
            similarity_threshold: Minimum cosine similarity for parent matching (0-1)
            min_tag_overlap: Minimum number of overlapping tags required
        """
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.min_tag_overlap = min_tag_overlap

    async def find_parent_topic(
        self,
        session: AsyncSession,
        tags: List[str],
        embedding: Optional[List[float]],
        user_guest_id: uuid.UUID,
    ) -> Optional[uuid.UUID]:
        """Find the most probable parent topic for a context.

        Uses a hybrid approach:
        1. Tag matching: Find contexts with overlapping tags
        2. Embedding similarity: For matched contexts, compute cosine similarity
        3. Return most similar context_id if similarity > threshold

        Args:
            session: Database session
            tags: List of tags for the context
            embedding: Embedding vector for the context
            user_guest_id: User identifier to filter contexts

        Returns:
            UUID of the parent topic context, or None if no match found
        """
        if not tags:
            return None

        # Step 1: Tag matching - find contexts with overlapping tags
        # Using PostgreSQL array overlap operator (&&)
        tag_matching_query = select(UserContext).where(
            UserContext.user_guest_id == user_guest_id,
            UserContext.context_tags.op("&&")(array(tags)),  # PostgreSQL array overlap operator
            UserContext.parent_topic.is_(None),  # Only consider root contexts as potential parents
        )

        result = await session.execute(tag_matching_query)
        candidate_contexts = result.scalars().all()

        if not candidate_contexts:
            return None

        # Step 2: If we have an embedding, compute similarity for each candidate
        if embedding:
            best_match: Optional[UserContext] = None
            best_similarity: float = 0.0

            for candidate in candidate_contexts:
                # Check if embedding exists (handle both None and numpy arrays)
                if candidate.embedding is None:
                    continue
                
                # Convert pgvector/numpy array to list if needed
                if isinstance(candidate.embedding, list):
                    candidate_embedding = candidate.embedding
                else:
                    # Handle numpy array or pgvector types
                    try:
                        candidate_embedding = list(candidate.embedding)
                    except (TypeError, ValueError):
                        continue

                similarity = self.embedding_service.cosine_similarity(
                    embedding, candidate_embedding
                )

                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = candidate

            # Return parent if similarity exceeds threshold
            if best_match and best_similarity >= self.similarity_threshold:
                return best_match.context_id

        # Step 3: If no embedding or no good match, return first candidate
        # (fallback to tag-based matching only)
        if candidate_contexts:
            return candidate_contexts[0].context_id

        return None

    async def find_parent_topic_by_content(
        self,
        session: AsyncSession,
        content: str,
        tags: List[str],
        user_guest_id: uuid.UUID,
    ) -> Optional[uuid.UUID]:
        """Find parent topic by generating embedding from content.

        Args:
            session: Database session
            content: Raw content text
            tags: List of tags for the context
            user_guest_id: User identifier to filter contexts

        Returns:
            UUID of the parent topic context, or None if no match found
        """
        embedding = await self.embedding_service.generate_embedding(content)
        return await self.find_parent_topic(session, tags, embedding, user_guest_id)
