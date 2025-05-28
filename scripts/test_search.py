#!/usr/bin/env python3
"""
Test search functionality directly to debug the indexing issues.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.simple_vector_store import get_knowledge_base
from app.lexical_search import get_bm25_search_engine
from app.retrieval_engine import RetrievalEngine

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_search():
    """Test search functionality."""
    logger.info("Testing search components individually...")
    
    try:
        # Test vector store
        logger.info("=== Testing Vector Store ===")
        knowledge_base = get_knowledge_base()
        vector_store = knowledge_base.vector_store
        stats = vector_store.get_stats()
        logger.info(f"Vector store stats: {stats}")
        
        # Test BM25 search engine
        logger.info("=== Testing BM25 Search Engine ===")
        bm25_engine = get_bm25_search_engine()
        logger.info(f"BM25 engine loaded")
        
        # Try to search directly with BM25
        test_queries = ["Python", "programming", "machine learning", "data science"]
        
        for query in test_queries:
            logger.info(f"Testing BM25 search for: '{query}'")
            try:
                # Try keyword search
                from app.lexical_search import search_keyword
                results = search_keyword(query, max_results=3)
                logger.info(f"BM25 keyword search returned {len(results)} results")
                
                for i, result in enumerate(results[:2]):
                    logger.info(f"  Result {i+1}: {result.chunk_text[:100]}... (score: {result.similarity_score:.3f})")
                
            except Exception as e:
                logger.error(f"BM25 search failed: {e}")
        
        # Test unified retrieval engine
        logger.info("=== Testing Unified Retrieval Engine ===")
        retrieval_engine = RetrievalEngine()
        
        for query in test_queries[:2]:  # Test fewer queries
            logger.info(f"Testing unified search for: '{query}'")
            try:
                results = await retrieval_engine.search(query, max_results=3)
                logger.info(f"Unified search returned {len(results)} results")
                
                for i, result in enumerate(results[:2]):
                    logger.info(f"  Result {i+1}: {result.chunk_text[:100]}... (score: {result.similarity_score:.3f})")
                
            except Exception as e:
                logger.error(f"Unified search failed: {e}")
                import traceback
                traceback.print_exc()
        
        logger.info("Search testing completed!")
        
    except Exception as e:
        logger.error(f"Error during search testing: {e}")
        import traceback
        traceback.print_exc()
        raise


async def main():
    """Main function."""
    logger.info("Quiz-D Search Test Tool")
    logger.info("=" * 40)
    
    await test_search()


if __name__ == "__main__":
    asyncio.run(main())
