"""
Embedding Service
Generate text embeddings for semantic search and deduplication.
"""

from typing import List

from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using OpenAI."""
    
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS = 1536
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            # Clean and truncate text if necessary
            text = text.strip()
            if not text:
                return [0.0] * self.EMBEDDING_DIMENSIONS
            
            # OpenAI has a token limit, truncate if too long
            max_chars = 8000
            if len(text) > max_chars:
                text = text[:max_chars]
            
            response = self.client.embeddings.create(
                model=self.EMBEDDING_MODEL,
                input=text,
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error("Embedding generation failed", error=str(e))
            raise
    
    async def get_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100,
    ) -> List[List[float]]:
        """
        Generate embeddings for multiple texts in batches.
        
        Args:
            texts: List of texts to embed
            batch_size: Number of texts per API call
            
        Returns:
            List of embedding vectors
        """
        try:
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                # Clean texts
                batch = [t.strip()[:8000] if t.strip() else " " for t in batch]
                
                response = self.client.embeddings.create(
                    model=self.EMBEDDING_MODEL,
                    input=batch,
                )
                
                # Sort by index to maintain order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                embeddings = [d.embedding for d in sorted_data]
                all_embeddings.extend(embeddings)
            
            return all_embeddings
            
        except Exception as e:
            logger.error("Batch embedding generation failed", error=str(e))
            raise
    
    def cosine_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float],
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between 0 and 1
        """
        import numpy as np
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
