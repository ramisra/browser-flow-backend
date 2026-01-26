"""OpenAI embedding generation service."""

import asyncio
from typing import List, Optional

import numpy as np
from openai import AsyncOpenAI

from app.core.config import settings


class EmbeddingService:
    """Service for generating embeddings using OpenAI API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """Initialize the embedding service.

        Args:
            api_key: OpenAI API key. If not provided, uses settings.OPENAI_API_KEY
            model: Embedding model name. If not provided, uses settings.EMBEDDING_MODEL
        """
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.model = model or settings.EMBEDDING_MODEL
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for a single text.

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats representing the embedding vector, or None if error
        """
        if not text or not text.strip():
            return None

        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text.strip(),
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    async def generate_embeddings_batch(
        self, texts: List[str], batch_size: int = 100
    ) -> List[Optional[List[float]]]:
        """Generate embeddings for multiple texts in batches.

        Args:
            texts: List of texts to generate embeddings for
            batch_size: Number of texts to process in each batch

        Returns:
            List of embeddings (or None for failed generations)
        """
        results = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = await self.client.embeddings.create(
                    model=self.model,
                    input=[text.strip() for text in batch if text and text.strip()],
                )
                batch_results = [item.embedding for item in response.data]
                results.extend(batch_results)
            except Exception as e:
                print(f"Error generating embeddings for batch: {e}")
                results.extend([None] * len(batch))
        
        return results

    def cosine_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score between -1 and 1
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
