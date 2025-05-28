"""
Embedding generation module using DSPy and OpenAI.
Implements Sprint 2 requirements for vector embeddings.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

import dspy
from openai import AsyncOpenAI
from app.models import ContentChunk, EmbeddingRequest, EmbeddingResponse
from app.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """
    Generates embeddings for text chunks using OpenAI's embedding models via DSPy.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[AsyncOpenAI] = None
        self._dspy_embedder = None
        self._initialize_clients()
    
    def _initialize_clients(self):
        """Initialize OpenAI and DSPy clients."""
        if not self.settings.openai_api_key:
            logger.warning("OpenAI API key not configured. Embedding generation will not work.")
            return
        
        try:
            # Initialize async OpenAI client
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
            
            # Initialize DSPy with OpenAI
            dspy.configure(
                lm=dspy.LM(
                    model=f"openai/{self.settings.dspy_model}",
                    api_key=self.settings.openai_api_key,
                    max_tokens=self.settings.dspy_max_tokens
                )
            )
            
            # Initialize DSPy embedder
            try:
                self._dspy_embedder = dspy.Embedder(
                    f"openai/{self.settings.embedding_model}",
                    dimensions=self.settings.embedding_dimensions
                )
                logger.info(f"Initialized DSPy embedder with model: {self.settings.embedding_model}")
            except Exception as e:
                logger.warning(f"Failed to initialize DSPy embedder: {e}. Falling back to direct OpenAI API.")
                self._dspy_embedder = None
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding clients: {e}")
            self._client = None
    
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List[float]: Embedding vector
            
        Raises:
            ValueError: If text is empty
            RuntimeError: If embedding generation fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        embeddings = await self.embed_texts([text])
        return embeddings[0]
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of embedding vectors
            
        Raises:
            ValueError: If texts list is empty
            RuntimeError: If embedding generation fails
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")
        
        # Filter out empty texts
        valid_texts = [text.strip() for text in texts if text.strip()]
        if not valid_texts:
            raise ValueError("No valid texts to embed")
        
        # Try DSPy embedder first, then fallback to direct OpenAI
        if self._dspy_embedder:
            try:
                return await self._embed_with_dspy(valid_texts)
            except Exception as e:
                logger.warning(f"DSPy embedding failed: {e}. Falling back to direct OpenAI API.")
        
        return await self._embed_with_openai(valid_texts)
    
    async def _embed_with_dspy(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using DSPy.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of embedding vectors
        """
        try:
            # DSPy's embedder might be synchronous, so run in executor
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, 
                lambda: self._dspy_embedder(texts)
            )
            
            # Convert to list of lists if needed
            if isinstance(embeddings, np.ndarray):
                embeddings = embeddings.tolist()
            elif not isinstance(embeddings, list):
                embeddings = [embeddings]
            
            # Ensure we have the right format
            if len(embeddings) != len(texts):
                raise ValueError(f"Expected {len(texts)} embeddings, got {len(embeddings)}")
            
            return embeddings
            
        except Exception as e:
            logger.error(f"DSPy embedding failed: {e}")
            raise RuntimeError(f"Failed to generate embeddings with DSPy: {e}")
    
    async def _embed_with_openai(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings using direct OpenAI API.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List[List[float]]: List of embedding vectors
        """
        if not self._client:
            raise RuntimeError("OpenAI client not initialized")
        
        try:
            # Process in batches to avoid API limits
            batch_size = self.settings.embedding_batch_size
            all_embeddings = []
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                
                response = await self._client.embeddings.create(
                    model=self.settings.embedding_model,
                    input=batch,
                    dimensions=self.settings.embedding_dimensions
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
                logger.debug(f"Generated embeddings for batch {i//batch_size + 1}, "
                           f"texts: {len(batch)}, embeddings: {len(batch_embeddings)}")
            
            if len(all_embeddings) != len(texts):
                raise ValueError(f"Expected {len(texts)} embeddings, got {len(all_embeddings)}")
            
            return all_embeddings
            
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise RuntimeError(f"Failed to generate embeddings with OpenAI: {e}")
    
    async def embed_chunk(self, chunk: ContentChunk) -> ContentChunk:
        """
        Generate embedding for a content chunk and update it.
        
        Args:
            chunk: Content chunk to embed
            
        Returns:
            ContentChunk: Updated chunk with embedding
        """
        try:
            embedding = await self.embed_text(chunk.text)
            
            # Create updated chunk with embedding
            chunk_dict = chunk.model_dump()
            chunk_dict['embedding'] = embedding
            
            return ContentChunk(**chunk_dict)
            
        except Exception as e:
            logger.error(f"Failed to embed chunk {chunk.id}: {e}")
            raise RuntimeError(f"Failed to embed chunk: {e}")
    
    async def embed_chunks(self, chunks: List[ContentChunk]) -> List[ContentChunk]:
        """
        Generate embeddings for multiple chunks.
        
        Args:
            chunks: List of content chunks to embed
            
        Returns:
            List[ContentChunk]: Updated chunks with embeddings
        """
        if not chunks:
            return []
        
        try:
            # Extract texts from chunks
            texts = [chunk.text for chunk in chunks]
            
            # Generate embeddings
            embeddings = await self.embed_texts(texts)
            
            # Update chunks with embeddings
            updated_chunks = []
            for chunk, embedding in zip(chunks, embeddings):
                chunk_dict = chunk.model_dump()
                chunk_dict['embedding'] = embedding
                updated_chunks.append(ContentChunk(**chunk_dict))
            
            logger.info(f"Successfully embedded {len(updated_chunks)} chunks")
            return updated_chunks
            
        except Exception as e:
            logger.error(f"Failed to embed chunks: {e}")
            raise RuntimeError(f"Failed to embed chunks: {e}")
    
    def get_embedding_info(self) -> Dict[str, Any]:
        """
        Get information about the embedding configuration.
        
        Returns:
            Dict[str, Any]: Embedding configuration info
        """
        return {
            "model": self.settings.embedding_model,
            "dimensions": self.settings.embedding_dimensions,
            "batch_size": self.settings.embedding_batch_size,
            "client_initialized": self._client is not None,
            "dspy_embedder_available": self._dspy_embedder is not None,
            "api_key_configured": bool(self.settings.openai_api_key)
        }
    
    async def test_embedding(self, test_text: str = "This is a test sentence for embedding.") -> Dict[str, Any]:
        """
        Test embedding generation with a sample text.
        
        Args:
            test_text: Text to use for testing
            
        Returns:
            Dict[str, Any]: Test results
        """
        try:
            embedding = await self.embed_text(test_text)
            
            return {
                "success": True,
                "text": test_text,
                "embedding_length": len(embedding),
                "expected_dimensions": self.settings.embedding_dimensions,
                "dimensions_match": len(embedding) == self.settings.embedding_dimensions,
                "sample_values": embedding[:5] if len(embedding) >= 5 else embedding
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "text": test_text
            }


# Global embedding generator instance
embedding_generator = EmbeddingGenerator()


def get_embedding_generator() -> EmbeddingGenerator:
    """Get the global embedding generator instance."""
    return embedding_generator
