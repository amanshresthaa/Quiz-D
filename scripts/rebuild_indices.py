#!/usr/bin/env python3
"""
Rebuild search indices for Quiz-D system.
This script rebuilds both the BM25 lexical index and ensures proper vector store loading.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simple_vector_store import get_knowledge_base
from app.lexical_search import BM25SearchEngine
from app.retrieval_engine import RetrievalEngine
from app.config import get_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def rebuild_indices():
    """Rebuild all search indices."""
    logger.info("Starting index rebuild process...")
    
    try:
        # Initialize settings
        settings = get_settings()
        logger.info("Settings loaded successfully")
        
        # Initialize vector store
        logger.info("Initializing vector store...")
        knowledge_base = get_knowledge_base()
        vector_store = knowledge_base.vector_store
        
        # Get total vectors in store
        stats = vector_store.get_stats()
        total_vectors = stats["total_vectors"]
        logger.info(f"Vector store contains {total_vectors} vectors")
        
        if total_vectors == 0:
            logger.warning("Vector store is empty! You may need to add content first.")
            return
        
        # Initialize lexical search
        logger.info("Initializing lexical search...")
        lexical_search = BM25SearchEngine()
        
        # Get all chunks from vector store for indexing
        logger.info("Retrieving all chunks for lexical indexing...")
        
        # Create chunks from vector store metadata (SimpleVectorStore uses list)
        all_chunks = []
        for metadata in vector_store._chunk_metadata:
            from app.models import ContentChunk
            
            # Skip chunks with None ID (old corrupted data)
            if metadata.get("chunk_id") is None:
                logger.warning(f"Skipping chunk with None ID: {metadata.get('content_id', 'unknown')}")
                continue
                
            chunk = ContentChunk(
                id=metadata["chunk_id"],  # Set the id field to the chunk_id from metadata
                content_id=metadata["content_id"],
                chunk_index=metadata["chunk_index"],
                text=metadata["text"],
                token_count=metadata.get("token_count"),
                metadata=metadata.get("metadata", {})
            )
            all_chunks.append(chunk)
        
        logger.info(f"Retrieved {len(all_chunks)} chunks from vector store")
        
        # Add chunks to lexical search (this will rebuild the BM25 index)
        if all_chunks:
            logger.info("Building BM25 index...")
            for chunk in all_chunks:
                lexical_search.add_chunk(chunk)
            
            # Save the lexical index
            lexical_search.save_index()
            logger.info("BM25 index built and saved successfully")
        else:
            logger.warning("No chunks found to index")
        
        # Test the indices
        logger.info("Testing search functionality...")
        retrieval_engine = RetrievalEngine()
        
        # Test search
        test_query = "Python programming"
        logger.info(f"Testing search with query: '{test_query}'")
        
        results = await retrieval_engine.search(test_query, max_results=3)
        logger.info(f"Search returned {len(results)} results")
        
        for i, result in enumerate(results[:3]):
            logger.info(f"Result {i+1}: {result.chunk_text[:100]}... (score: {result.similarity_score:.3f})")
        
        logger.info("Index rebuild completed successfully!")
        
    except Exception as e:
        logger.error(f"Error during index rebuild: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """Main function."""
    logger.info("Quiz-D Index Rebuild Tool")
    logger.info("=" * 40)
    
    await rebuild_indices()


if __name__ == "__main__":
    asyncio.run(main())
