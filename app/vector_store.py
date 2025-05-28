"""
Vector store implementation using FAISS for semantic search.
Implements Sprint 2 requirements for knowledge base storage and retrieval.
"""

import os
import pickle
import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

import faiss
from app.models import ContentChunk, VectorSearchResult
from app.config import get_settings

logger = logging.getLogger(__name__)


class FAISSVectorStore:
    """
    Vector store implementation using FAISS for efficient similarity search.
    """
    
    def __init__(self, dimensions: int = None):
        self.settings = get_settings()
        self.dimensions = dimensions or self.settings.embedding_dimensions
        
        # FAISS index
        self._index: Optional[faiss.Index] = None
        
        # Metadata storage (maps vector index to chunk metadata)
        self._chunk_metadata: Dict[int, Dict[str, Any]] = {}
        
        # Chunk ID to index mapping
        self._chunk_id_to_index: Dict[str, int] = {}
        self._index_to_chunk_id: Dict[int, str] = {}
        
        # Initialize index
        self._initialize_index()
        
        # Load existing index if available
        self._load_index()
    
    def _initialize_index(self):
        """Initialize FAISS index."""
        try:
            # Use IndexFlatIP (Inner Product) for cosine similarity
            # Note: We'll normalize vectors before adding them
            self._index = faiss.IndexFlatIP(self.dimensions)
            logger.info(f"Initialized FAISS index with {self.dimensions} dimensions")
        except Exception as e:
            logger.error(f"Failed to initialize FAISS index: {e}")
            raise RuntimeError(f"Failed to initialize vector store: {e}")
    
    def _normalize_vectors(self, vectors: np.ndarray) -> np.ndarray:
        """
        Normalize vectors for cosine similarity.
        
        Args:
            vectors: Array of vectors to normalize
            
        Returns:
            np.ndarray: Normalized vectors
        """
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        # Avoid division by zero
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms
    
    def add_chunk(self, chunk: ContentChunk) -> bool:
        """
        Add a chunk with its embedding to the vector store.
        
        Args:
            chunk: Content chunk with embedding
            
        Returns:
            bool: True if successfully added
            
        Raises:
            ValueError: If chunk has no embedding
            RuntimeError: If addition fails
        """
        if not chunk.embedding:
            raise ValueError(f"Chunk {chunk.id} has no embedding")
        
        if len(chunk.embedding) != self.dimensions:
            raise ValueError(f"Embedding dimensions {len(chunk.embedding)} "
                           f"don't match expected {self.dimensions}")
        
        try:
            # Convert embedding to numpy array
            vector = np.array([chunk.embedding], dtype=np.float32)
            
            # Normalize for cosine similarity
            vector = self._normalize_vectors(vector)
            
            # Get the index where this vector will be added
            vector_index = self._index.ntotal
            
            # Add to FAISS index
            self._index.add(vector)
            
            # Store metadata
            metadata = {
                "chunk_id": chunk.id,
                "content_id": chunk.content_id,
                "text": chunk.text,
                "chunk_index": chunk.chunk_index,
                "token_count": chunk.token_count,
                "metadata": chunk.metadata
            }
            
            self._chunk_metadata[vector_index] = metadata
            self._chunk_id_to_index[chunk.id] = vector_index
            self._index_to_chunk_id[vector_index] = chunk.id
            
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
        
        if self._index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []
        
        try:
            # Convert to numpy array and normalize
            query = np.array([query_vector], dtype=np.float32)
            query = self._normalize_vectors(query)
            
            # Search in FAISS index
            scores, indices = self._index.search(query, min(k, self._index.ntotal))
            
            # Convert results
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx == -1:  # FAISS returns -1 for missing results
                    continue
                
                if idx not in self._chunk_metadata:
                    logger.warning(f"No metadata found for index {idx}")
                    continue
                
                metadata = self._chunk_metadata[idx]
                
                # Filter by similarity threshold
                if score < self.settings.similarity_threshold:
                    continue
                
                result = VectorSearchResult(
                    chunk_id=metadata["chunk_id"],
                    content_id=metadata["content_id"],
                    chunk_text=metadata["text"],
                    similarity_score=float(score),
                    chunk_index=metadata["chunk_index"],
                    metadata=metadata.get("metadata", {})
                )
                results.append(result)
            
            logger.debug(f"Found {len(results)} results above threshold {self.settings.similarity_threshold}")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise RuntimeError(f"Vector search failed: {e}")
    
    def search_by_text(self, query_text: str, k: int = None) -> List[VectorSearchResult]:
        """
        Search using text query (requires embedding generation).
        
        Args:
            query_text: Text query
            k: Number of results to return
            
        Returns:
            List[VectorSearchResult]: Search results
            
        Note:
            This method requires the embedding generator to be available.
            Use search() directly if you already have the query vector.
        """
        # This would require embedding the query text first
        # For now, raise an error indicating this needs to be done externally
        raise NotImplementedError(
            "Text-based search requires embedding generation. "
            "Please embed the query text first and use search() method."
        )
    
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
            return self._chunk_metadata.get(index)
        return None
    
    def remove_chunk(self, chunk_id: str) -> bool:
        """
        Remove a chunk from the vector store.
        
        Args:
            chunk_id: ID of chunk to remove
            
        Returns:
            bool: True if successfully removed
            
        Note:
            FAISS doesn't support efficient removal of individual vectors.
            This implementation marks the chunk as removed but doesn't
            actually remove it from the index. For full removal, the
            index would need to be rebuilt.
        """
        if chunk_id not in self._chunk_id_to_index:
            return False
        
        try:
            index = self._chunk_id_to_index[chunk_id]
            
            # Remove from metadata
            if index in self._chunk_metadata:
                del self._chunk_metadata[index]
            
            # Remove from mappings
            del self._chunk_id_to_index[chunk_id]
            if index in self._index_to_chunk_id:
                del self._index_to_chunk_id[index]
            
            logger.info(f"Marked chunk {chunk_id} as removed")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove chunk {chunk_id}: {e}")
            return False
    
    def clear(self):
        """Clear all data from the vector store."""
        try:
            self._index.reset()
            self._chunk_metadata.clear()
            self._chunk_id_to_index.clear()
            self._index_to_chunk_id.clear()
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
            "total_vectors": self._index.ntotal if self._index else 0,
            "dimensions": self.dimensions,
            "metadata_entries": len(self._chunk_metadata),
            "index_type": type(self._index).__name__ if self._index else None,
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
            
            # Save FAISS index
            index_file = f"{filepath}.faiss"
            faiss.write_index(self._index, index_file)
            
            # Save metadata
            metadata_file = f"{filepath}.metadata"
            with open(metadata_file, 'wb') as f:
                pickle.dump({
                    'chunk_metadata': self._chunk_metadata,
                    'chunk_id_to_index': self._chunk_id_to_index,
                    'index_to_chunk_id': self._index_to_chunk_id,
                    'dimensions': self.dimensions
                }, f)
            
            logger.info(f"Saved vector index to {filepath}")
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
        
        index_file = f"{filepath}.faiss"
        metadata_file = f"{filepath}.metadata"
        
        if not (os.path.exists(index_file) and os.path.exists(metadata_file)):
            logger.info("No existing vector index found")
            return False
        
        try:
            # Load FAISS index
            self._index = faiss.read_index(index_file)
            
            # Load metadata
            with open(metadata_file, 'rb') as f:
                data = pickle.load(f)
                self._chunk_metadata = data['chunk_metadata']
                self._chunk_id_to_index = data['chunk_id_to_index']
                self._index_to_chunk_id = data['index_to_chunk_id']
                
                # Verify dimensions match
                if data['dimensions'] != self.dimensions:
                    logger.warning(f"Loaded index dimensions {data['dimensions']} "
                                 f"don't match expected {self.dimensions}")
            
            logger.info(f"Loaded vector index from {filepath} with {self._index.ntotal} vectors")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load vector index: {e}")
            return False


class KnowledgeBase:
    """
    High-level knowledge base interface combining vector store and embedding generation.
    """
    
    def __init__(self, vector_store: FAISSVectorStore = None):
        self.vector_store = vector_store or FAISSVectorStore()
        self._embedding_generator = None  # Will be injected when needed
    
    def set_embedding_generator(self, embedding_generator):
        """Set the embedding generator for text-based operations."""
        self._embedding_generator = embedding_generator
    
    def add_chunk(self, chunk: ContentChunk) -> bool:
        """
        Add a chunk to the knowledge base.
        
        Args:
            chunk: Content chunk with embedding
            
        Returns:
            bool: True if successfully added
        """
        return self.vector_store.add_chunk(chunk)
    
    def add_chunks(self, chunks: List[ContentChunk]) -> int:
        """
        Add multiple chunks to the knowledge base.
        
        Args:
            chunks: List of content chunks with embeddings
            
        Returns:
            int: Number of chunks successfully added
        """
        return self.vector_store.add_chunks(chunks)
    
    async def search_by_text(self, query_text: str, k: int = None) -> List[VectorSearchResult]:
        """
        Search the knowledge base using text query.
        
        Args:
            query_text: Text query
            k: Number of results to return
            
        Returns:
            List[VectorSearchResult]: Search results
        """
        if not self._embedding_generator:
            raise RuntimeError("Embedding generator not configured")
        
        # Generate embedding for query
        query_vector = await self._embedding_generator.embed_text(query_text)
        
        # Search using vector
        return self.vector_store.search(query_vector, k)
    
    def search_by_vector(self, query_vector: List[float], k: int = None) -> List[VectorSearchResult]:
        """
        Search the knowledge base using embedding vector.
        
        Args:
            query_vector: Query embedding vector
            k: Number of results to return
            
        Returns:
            List[VectorSearchResult]: Search results
        """
        return self.vector_store.search(query_vector, k)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        return self.vector_store.get_stats()
    
    def save(self, filepath: str = None) -> bool:
        """Save the knowledge base to disk."""
        return self.vector_store.save_index(filepath)
    
    def clear(self):
        """Clear all data from the knowledge base."""
        self.vector_store.clear()


# Global knowledge base instance
knowledge_base = KnowledgeBase()


def get_knowledge_base() -> KnowledgeBase:
    """Get the global knowledge base instance."""
    return knowledge_base
