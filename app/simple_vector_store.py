"""
Simple in-memory vector store implementation as fallback when FAISS is not available.
Implements Sprint 2 requirements for knowledge base storage and retrieval.
Enhanced with Sprint 3 hybrid search capabilities.
"""

import os
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from math import sqrt

from app.models import ContentChunk, VectorSearchResult
from app.config import get_settings

logger = logging.getLogger(__name__)

# Import retrieval engine components
try:
    from app.retrieval_engine import RetrievalEngine, SearchMode
    RETRIEVAL_ENGINE_AVAILABLE = True
except ImportError:
    logger.warning("RetrievalEngine not available - falling back to basic semantic search")
    RETRIEVAL_ENGINE_AVAILABLE = False
    RetrievalEngine = None
    SearchMode = None


class SimpleVectorStore:
    """
    Simple in-memory vector store implementation using numpy for similarity search.
    This is a fallback implementation when FAISS is not available.
    """
    
    def __init__(self, dimensions: int = None):
        self.settings = get_settings()
        self.dimensions = dimensions or self.settings.embedding_dimensions
        
        # Storage
        self._vectors: List[List[float]] = []
        self._chunk_metadata: List[Dict[str, Any]] = []
        self._chunk_id_to_index: Dict[str, int] = {}
        
        logger.info(f"Initialized Simple Vector Store with {self.dimensions} dimensions")
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors.
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            float: Cosine similarity score (0-1)
        """
        try:
            # Convert to numpy arrays
            a = np.array(vec1)
            b = np.array(vec2)
            
            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            
            if norm_a == 0 or norm_b == 0:
                return 0.0
            
            similarity = dot_product / (norm_a * norm_b)
            
            # Ensure similarity is in [0, 1] range
            return max(0.0, min(1.0, similarity))
            
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def add_chunk(self, chunk: ContentChunk) -> bool:
        """
        Add a chunk with its embedding to the vector store.
        
        Args:
            chunk: Content chunk with embedding
            
        Returns:
            bool: True if successfully added
        """
        if not chunk.embedding:
            raise ValueError(f"Chunk {chunk.id} has no embedding")
        
        if len(chunk.embedding) != self.dimensions:
            raise ValueError(f"Embedding dimensions {len(chunk.embedding)} "
                           f"don't match expected {self.dimensions}")
        
        try:
            # Check if chunk already exists
            if chunk.id in self._chunk_id_to_index:
                logger.warning(f"Chunk {chunk.id} already exists, skipping")
                return False
            
            # Get the index where this vector will be added
            vector_index = len(self._vectors)
            
            # Add vector and metadata
            self._vectors.append(chunk.embedding)
            
            metadata = {
                "chunk_id": chunk.id,
                "content_id": chunk.content_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
                "metadata": chunk.metadata
            }
            
            self._chunk_metadata.append(metadata)
            self._chunk_id_to_index[chunk.id] = vector_index
            
            logger.debug(f"Added chunk {chunk.id} to vector store at index {vector_index}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chunk {chunk.id} to vector store: {e}")
            raise RuntimeError(f"Failed to add chunk to vector store: {e}")
    
    def add_chunks(self, chunks: List[ContentChunk]) -> int:
        """
        Add multiple chunks to the vector store.
        
        Args:
            chunks: List of content chunks with embeddings
            
        Returns:
            int: Number of chunks successfully added
        """
        if not chunks:
            return 0
        
        added_count = 0
        failed_chunks = []
        
        for chunk in chunks:
            try:
                if self.add_chunk(chunk):
                    added_count += 1
            except Exception as e:
                logger.warning(f"Failed to add chunk {chunk.id}: {e}")
                failed_chunks.append(chunk.id)
        
        if failed_chunks:
            logger.warning(f"Failed to add {len(failed_chunks)} chunks: {failed_chunks}")
        
        logger.info(f"Successfully added {added_count}/{len(chunks)} chunks to vector store")
        return added_count
    
    def search(self, query_vector: List[float], k: int = None) -> List[VectorSearchResult]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            
        Returns:
            List[VectorSearchResult]: Search results ordered by similarity
        """
        if k is None:
            k = self.settings.max_retrieval_results
        
        if not query_vector:
            return []
        
        if len(query_vector) != self.dimensions:
            raise ValueError(f"Query vector dimensions {len(query_vector)} "
                           f"don't match expected {self.dimensions}")
        
        if not self._vectors:
            logger.warning("Vector store is empty")
            return []
        
        try:
            # Calculate similarities for all vectors
            similarities = []
            for i, stored_vector in enumerate(self._vectors):
                similarity = self._cosine_similarity(query_vector, stored_vector)
                similarities.append((similarity, i))
            
            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x[0], reverse=True)
            
            # Take top k results without filtering by threshold to improve recall
            results = []
            for similarity, idx in similarities[:k]:
                metadata = self._chunk_metadata[idx]
                result = VectorSearchResult(
                    chunk_id=metadata["chunk_id"],
                    content_id=metadata["content_id"],
                    chunk_text=metadata["text"],
                    similarity_score=float(similarity),
                    chunk_index=metadata["chunk_index"],
                    metadata=metadata.get("metadata", {})
                )
                results.append(result)
            
            logger.debug(f"Found {len(results)} results above threshold {self.settings.similarity_threshold}")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise RuntimeError(f"Vector search failed: {e}")
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve chunk metadata by chunk ID.
        
        Args:
            chunk_id: Chunk ID to retrieve
            
        Returns:
            Optional[Dict[str, Any]]: Chunk metadata if found
        """
        if chunk_id in self._chunk_id_to_index:
            index = self._chunk_id_to_index[chunk_id]
            return self._chunk_metadata[index]
        return None
    
    def remove_chunk(self, chunk_id: str) -> bool:
        """
        Remove a chunk from the vector store.
        
        Args:
            chunk_id: ID of chunk to remove
            
        Returns:
            bool: True if successfully removed
        """
        if chunk_id not in self._chunk_id_to_index:
            return False
        
        try:
            index = self._chunk_id_to_index[chunk_id]
            
            # Remove from vectors and metadata (this is inefficient but works for simple case)
            del self._vectors[index]
            del self._chunk_metadata[index]
            del self._chunk_id_to_index[chunk_id]
            
            # Update indices for remaining chunks
            updated_mapping = {}
            for cid, idx in self._chunk_id_to_index.items():
                if idx > index:
                    updated_mapping[cid] = idx - 1
                else:
                    updated_mapping[cid] = idx
            
            self._chunk_id_to_index = updated_mapping
            
            logger.info(f"Removed chunk {chunk_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove chunk {chunk_id}: {e}")
            return False
    
    def clear(self):
        """Clear all data from the vector store."""
        try:
            self._vectors.clear()
            self._chunk_metadata.clear()
            self._chunk_id_to_index.clear()
            logger.info("Cleared vector store")
        except Exception as e:
            logger.error(f"Failed to clear vector store: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the vector store.
        
        Returns:
            Dict[str, Any]: Vector store statistics
        """
        return {
            "total_vectors": len(self._vectors),
            "dimensions": self.dimensions,
            "metadata_entries": len(self._chunk_metadata),
            "index_type": "SimpleVectorStore",
            "similarity_threshold": self.settings.similarity_threshold,
            "max_retrieval_results": self.settings.max_retrieval_results
        }
    
    def save_index(self, filepath: str = None) -> bool:
        """
        Save the vector index and metadata to disk.
        
        Args:
            filepath: Path to save to (optional)
            
        Returns:
            bool: True if successfully saved
        """
        if filepath is None:
            filepath = self.settings.vector_index_path
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            # Save all data
            data = {
                'vectors': self._vectors,
                'chunk_metadata': self._chunk_metadata,
                'chunk_id_to_index': self._chunk_id_to_index,
                'dimensions': self.dimensions
            }
            
            with open(f"{filepath}.simple", 'wb') as f:
                pickle.dump(data, f)
            
            logger.info(f"Saved vector index to {filepath}.simple")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save vector index: {e}")
            return False
    
    def _load_index(self, filepath: str = None) -> bool:
        """
        Load vector index and metadata from disk.
        
        Args:
            filepath: Path to load from (optional)
            
        Returns:
            bool: True if successfully loaded
        """
        if filepath is None:
            filepath = self.settings.vector_index_path
        
        data_file = f"{filepath}.simple"
        
        if not os.path.exists(data_file):
            logger.info("No existing simple vector index found")
            return False
        
        try:
            with open(data_file, 'rb') as f:
                data = pickle.load(f)
                
            self._vectors = data['vectors']
            self._chunk_metadata = data['chunk_metadata']
            self._chunk_id_to_index = data['chunk_id_to_index']
            
            # Verify dimensions match
            if data['dimensions'] != self.dimensions:
                logger.warning(f"Loaded index dimensions {data['dimensions']} "
                             f"don't match expected {self.dimensions}")
            
            logger.info(f"Loaded vector index from {filepath}.simple with {len(self._vectors)} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load vector index: {e}")
            return False


class KnowledgeBase:
    """
    High-level knowledge base interface using SimpleVectorStore.
    Enhanced with Sprint 3 hybrid search capabilities.
    """
    
    def __init__(self, vector_store: SimpleVectorStore = None):
        self.vector_store = vector_store or SimpleVectorStore()
        self._embedding_generator = None
        self._retrieval_engine = None
        
        # Try to load existing index
        self.vector_store._load_index()
        
        # Initialize retrieval engine if available
        if RETRIEVAL_ENGINE_AVAILABLE:
            try:
                self._retrieval_engine = RetrievalEngine()
                logger.info("RetrievalEngine initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize RetrievalEngine: {e}")
                self._retrieval_engine = None
    
    def set_embedding_generator(self, embedding_generator):
        """Set the embedding generator for text-based operations."""
        self._embedding_generator = embedding_generator
        
        # Also set it for retrieval engine if available
        if self._retrieval_engine and hasattr(self._retrieval_engine, 'set_semantic_search'):
            try:
                # Create semantic search wrapper
                class SemanticSearchWrapper:
                    def __init__(self, vector_store, embedding_gen):
                        self.vector_store = vector_store
                        self.embedding_gen = embedding_gen
                    
                    async def search(self, query: str, k: int = None) -> List[VectorSearchResult]:
                        query_vector = await self.embedding_gen.embed_text(query)
                        return self.vector_store.search(query_vector, k)
                    
                    # Make the wrapper callable
                    async def __call__(self, query: str, k: int = None) -> List[VectorSearchResult]:
                        return await self.search(query, k)
                
                semantic_wrapper = SemanticSearchWrapper(self.vector_store, embedding_generator)
                self._retrieval_engine.set_semantic_search(semantic_wrapper)
                logger.info("Connected embedding generator to retrieval engine")
            except Exception as e:
                logger.warning(f"Failed to connect embedding generator to retrieval engine: {e}")
    
    def add_chunk(self, chunk: ContentChunk) -> bool:
        """Add a chunk to the knowledge base."""
        success = self.vector_store.add_chunk(chunk)
        
        # Also add to retrieval engine if available
        if success and self._retrieval_engine:
            try:
                self._retrieval_engine.add_chunk(chunk)
            except Exception as e:
                logger.warning(f"Failed to add chunk to retrieval engine: {e}")
        
        return success
    
    def add_chunks(self, chunks: List[ContentChunk]) -> int:
        """Add multiple chunks to the knowledge base."""
        count = self.vector_store.add_chunks(chunks)
        
        # Also add to retrieval engine if available
        if count > 0 and self._retrieval_engine:
            try:
                self._retrieval_engine.add_chunks(chunks)
            except Exception as e:
                logger.warning(f"Failed to add chunks to retrieval engine: {e}")
        
        return count
    
    async def search_by_text(self, query_text: str, k: int = None, search_mode: str = "AUTO") -> List[VectorSearchResult]:
        """
        Search the knowledge base using text query with hybrid search support.
        
        Args:
            query_text: Query text
            k: Maximum number of results
            search_mode: Search mode - "AUTO", "SEMANTIC_ONLY", "LEXICAL_ONLY", "HYBRID"
        """
        if not self._embedding_generator:
            raise RuntimeError("Embedding generator not configured")
        
        # Use retrieval engine if available and mode is not semantic only
        if self._retrieval_engine and search_mode.upper() != "SEMANTIC_ONLY":
            try:
                # Map search mode string to enum
                mode_map = {
                    "AUTO": SearchMode.AUTO,
                    "SEMANTIC_ONLY": SearchMode.SEMANTIC_ONLY,
                    "LEXICAL_ONLY": SearchMode.LEXICAL_ONLY,
                    "HYBRID": SearchMode.HYBRID
                }
                
                mode = mode_map.get(search_mode.upper(), SearchMode.AUTO)
                results = await self._retrieval_engine.search(query_text, k, mode)
                
                logger.info(f"Hybrid search returned {len(results)} results for query: {query_text[:50]}...")
                return results
                
            except Exception as e:
                logger.warning(f"Hybrid search failed, falling back to semantic search: {e}")
        
        # Fallback to semantic-only search
        query_vector = await self._embedding_generator.embed_text(query_text)
        results = self.vector_store.search(query_vector, k)
        
        logger.info(f"Semantic search returned {len(results)} results for query: {query_text[:50]}...")
        return results
    
    def search_by_vector(self, query_vector: List[float], k: int = None) -> List[VectorSearchResult]:
        """Search the knowledge base using embedding vector."""
        return self.vector_store.search(query_vector, k)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        stats = self.vector_store.get_stats()
        
        # Add retrieval engine stats if available
        if self._retrieval_engine:
            try:
                retrieval_stats = self._retrieval_engine.get_statistics()
                stats["retrieval_engine"] = retrieval_stats
                stats["hybrid_search_available"] = True
            except Exception as e:
                logger.warning(f"Failed to get retrieval engine stats: {e}")
                stats["hybrid_search_available"] = False
        else:
            stats["hybrid_search_available"] = False
        
        return stats
    
    def save(self, filepath: str = None) -> bool:
        """Save the knowledge base to disk."""
        success = self.vector_store.save_index(filepath)
        
        # Also save retrieval engine state if available
        if self._retrieval_engine:
            try:
                # Save lexical search index
                if hasattr(self._retrieval_engine, 'lexical_search') and self._retrieval_engine.lexical_search:
                    lexical_path = f"{filepath or 'index'}_lexical.pkl"
                    self._retrieval_engine.lexical_search.save_index(lexical_path)
                    logger.info(f"Saved lexical search index to {lexical_path}")
            except Exception as e:
                logger.warning(f"Failed to save retrieval engine state: {e}")
        
        return success
    
    def clear(self):
        """Clear all data from the knowledge base."""
        self.vector_store.clear()
        
        # Also clear retrieval engine if available
        if self._retrieval_engine:
            try:
                if hasattr(self._retrieval_engine, 'clear'):
                    self._retrieval_engine.clear()
                elif hasattr(self._retrieval_engine, 'lexical_search') and self._retrieval_engine.lexical_search:
                    self._retrieval_engine.lexical_search.clear()
                logger.info("Cleared retrieval engine data")
            except Exception as e:
                logger.warning(f"Failed to clear retrieval engine: {e}")


# Global knowledge base instance
knowledge_base = KnowledgeBase()


def get_knowledge_base() -> KnowledgeBase:
    """Get the global knowledge base instance."""
    return knowledge_base
