#!/usr/bin/env python3
"""
Debug the vector store to see what's actually stored and compare with BM25.
"""

import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simple_vector_store import get_knowledge_base

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def debug_vector_store():
    """Debug the vector store contents."""
    logger.info("Debugging vector store contents...")
    
    try:
        knowledge_base = get_knowledge_base()
        vector_store = knowledge_base.vector_store
        
        stats = vector_store.get_stats()
        logger.info(f"Vector store stats: {stats}")
        
        logger.info(f"Chunk metadata count: {len(vector_store._chunk_metadata)}")
        logger.info(f"Chunk ID to index mapping: {len(vector_store._chunk_id_to_index)}")
        
        # Show first few chunks
        for i, metadata in enumerate(vector_store._chunk_metadata[:3]):
            logger.info(f"Metadata {i}:")
            logger.info(f"  Chunk ID: {metadata.get('chunk_id', 'MISSING')}")
            logger.info(f"  Content ID: {metadata.get('content_id', 'MISSING')}")
            logger.info(f"  Chunk Index: {metadata.get('chunk_index', 'MISSING')}")
            logger.info(f"  Text (first 200 chars): {metadata.get('text', 'MISSING')[:200]}...")
            
            # Check if this has the keys we expect
            logger.info(f"  Available keys: {list(metadata.keys())}")
        
        # Check if there are specific content types
        content_ids = set()
        chunk_ids = set()
        for metadata in vector_store._chunk_metadata:
            content_ids.add(metadata.get('content_id'))
            chunk_ids.add(metadata.get('chunk_id'))
        
        logger.info(f"Unique content IDs: {len(content_ids)}")
        logger.info(f"Content IDs: {list(content_ids)}")
        logger.info(f"Unique chunk IDs: {len(chunk_ids)}")
        logger.info(f"Sample chunk IDs: {list(chunk_ids)[:5]}")
        
    except Exception as e:
        logger.error(f"Error debugging vector store: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function."""
    logger.info("Vector Store Debug Tool")
    logger.info("=" * 40)
    
    debug_vector_store()


if __name__ == "__main__":
    main()
