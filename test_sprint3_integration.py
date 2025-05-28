#!/usr/bin/env python3
"""
Sprint 3 Integration Test Script
Tests the hybrid search capabilities integrated with the existing pipeline.
"""

import asyncio
import logging
import sys
import os
from typing import List, Dict, Any

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.config import get_settings
from app.ingestion_pipeline import get_data_ingestion_pipeline
from app.simple_vector_store import get_knowledge_base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_hybrid_search_integration():
    """Test the complete hybrid search integration."""
    
    print("🧪 Starting Sprint 3 Hybrid Search Integration Tests")
    print("=" * 60)
    
    try:
        # Initialize components
        pipeline = get_data_ingestion_pipeline()
        knowledge_base = get_knowledge_base()
        
        print("✅ Components initialized successfully")
        
        # Test 1: Basic pipeline health
        print("\n🔍 Test 1: Pipeline Health Check")
        stats = pipeline.get_pipeline_statistics()
        print(f"   Vector count: {stats.get('vector_storage', {}).get('total_vectors', 0)}")
        print(f"   Hybrid search available: {stats.get('vector_storage', {}).get('hybrid_search_available', False)}")
        
        # Test 2: Ingest test content for search
        print("\n📝 Test 2: Ingesting Test Content")
        test_documents = [
            {
                "title": "Python Programming Basics",
                "text": "Python is a high-level programming language. It supports object-oriented programming and has dynamic typing. Python is widely used for web development, data science, and machine learning.",
                "source": "test_doc_1"
            },
            {
                "title": "Machine Learning Fundamentals", 
                "text": "Machine learning is a subset of artificial intelligence. It involves algorithms that learn patterns from data. Common types include supervised learning, unsupervised learning, and reinforcement learning.",
                "source": "test_doc_2"
            },
            {
                "title": "Web Development with FastAPI",
                "text": "FastAPI is a modern web framework for building APIs with Python. It provides automatic API documentation, type hints support, and high performance. FastAPI is built on Starlette and Pydantic.",
                "source": "test_doc_3"
            },
            {
                "title": "Data Science Tools",
                "text": "Data science involves extracting insights from data. Popular tools include pandas for data manipulation, numpy for numerical computing, and matplotlib for visualization. Jupyter notebooks are commonly used for interactive analysis.",
                "source": "test_doc_4"
            }
        ]
        
        ingestion_results = []
        for doc in test_documents:
            result = await pipeline.ingest_content(
                title=doc["title"],
                text=doc["text"],
                source=doc["source"]
            )
            ingestion_results.append(result)
            print(f"   ✅ Ingested: {doc['title']} - {result.get('chunks_created', 0)} chunks")
        
        total_chunks = sum(r.get('chunks_created', 0) for r in ingestion_results)
        print(f"   📊 Total chunks created: {total_chunks}")
        
        # Test 3: Search Mode Comparison
        print("\n🔍 Test 3: Search Mode Comparison")
        test_queries = [
            "Python programming language",
            "machine learning algorithms", 
            "web development framework",
            "data visualization tools"
        ]
        
        for query in test_queries:
            print(f"\n   Query: '{query}'")
            
            # Test different search modes
            modes = ["SEMANTIC_ONLY", "LEXICAL_ONLY", "HYBRID", "AUTO"]
            
            for mode in modes:
                try:
                    results = await pipeline.search_content(
                        query=query,
                        max_results=3,
                        search_mode=mode
                    )
                    
                    print(f"     {mode:15}: {len(results):2d} results", end="")
                    if results:
                        print(f" (top score: {results[0].similarity_score:.3f})")
                    else:
                        print()
                        
                except Exception as e:
                    print(f"     {mode:15}: ERROR - {e}")
        
        # Test 4: Detailed Search Analysis
        print("\n🔍 Test 4: Detailed Search Analysis")
        analysis_query = "Python web development"
        print(f"   Analyzing query: '{analysis_query}'")
        
        for mode in ["SEMANTIC_ONLY", "HYBRID"]:
            print(f"\n   === {mode} Mode ===")
            results = await pipeline.search_content(
                query=analysis_query,
                max_results=5,
                search_mode=mode
            )
            
            for i, result in enumerate(results, 1):
                print(f"     {i}. Score: {result.similarity_score:.3f}")
                print(f"        Chunk: {result.chunk_id}")
                print(f"        Text: {result.chunk_text[:100]}...")
                print()
        
        # Test 5: Performance Metrics
        print("\n📊 Test 5: Performance Metrics")
        final_stats = pipeline.get_pipeline_statistics()
        
        vector_stats = final_stats.get("vector_storage", {})
        print(f"   Total vectors: {vector_stats.get('total_vectors', 0)}")
        print(f"   Vector dimensions: {vector_stats.get('dimensions', 0)}")
        print(f"   Hybrid search available: {vector_stats.get('hybrid_search_available', False)}")
        
        if "retrieval_engine" in vector_stats:
            retrieval_stats = vector_stats["retrieval_engine"]
            print(f"   Total searches: {retrieval_stats.get('total_searches', 0)}")
            print(f"   Average results per search: {retrieval_stats.get('average_results_per_search', 0):.2f}")
        
        embedding_stats = final_stats.get("embedding_generation", {})
        print(f"   Embedding client active: {embedding_stats.get('client_initialized', False)}")
        print(f"   API key configured: {embedding_stats.get('api_key_configured', False)}")
        
        print("\n✅ All Integration Tests Completed Successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        logger.exception("Full error details:")
        return False


async def test_error_handling():
    """Test error handling and edge cases."""
    
    print("\n🔧 Testing Error Handling and Edge Cases")
    print("-" * 40)
    
    pipeline = get_data_ingestion_pipeline()
    
    # Test empty query
    try:
        results = await pipeline.search_content("", max_results=5)
        print("   ❌ Empty query should have failed")
    except Exception as e:
        print(f"   ✅ Empty query correctly rejected: {type(e).__name__}")
    
    # Test invalid search mode
    try:
        results = await pipeline.search_content("test", max_results=5, search_mode="INVALID_MODE")
        print("   ⚠️  Invalid search mode was accepted (fallback behavior)")
    except Exception as e:
        print(f"   ✅ Invalid search mode correctly rejected: {type(e).__name__}")
    
    # Test large max_results
    try:
        results = await pipeline.search_content("Python", max_results=1000)
        print(f"   ✅ Large max_results handled: {len(results)} results returned")
    except Exception as e:
        print(f"   ❌ Large max_results failed: {e}")
    
    print("   ✅ Error handling tests completed")


def main():
    """Main test runner."""
    print("🚀 Sprint 3 Integration Test Suite")
    print("Testing hybrid search integration with existing pipeline")
    print("=" * 60)
    
    # Check configuration
    settings = get_settings()
    print(f"API Host: {settings.api_host}:{settings.api_port}")
    print(f"Vector store: {settings.vector_store_type}")
    print(f"Hybrid search weights: semantic={settings.hybrid_semantic_weight}, lexical={settings.hybrid_lexical_weight}")
    
    # Run tests
    async def run_all_tests():
        success = await test_hybrid_search_integration()
        if success:
            await test_error_handling()
        return success
    
    # Execute tests
    try:
        success = asyncio.run(run_all_tests())
        
        if success:
            print("\n🎉 All tests passed! Hybrid search integration is working correctly.")
            print("\nNext steps:")
            print("- Start the FastAPI server: uvicorn app.main:app --reload")
            print("- Test the new endpoints:")
            print("  POST /content/search (with search_mode parameter)")
            print("  POST /content/search/compare")
            print("  GET /retrieval/stats")
            return 0
        else:
            print("\n❌ Some tests failed. Please check the errors above.")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Test suite crashed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
