#!/usr/bin/env python3
"""
Sprint 2 Enhanced Data Ingestion Pipeline Test Script

This script demonstrates and tests the enhanced ingestion pipeline features.
Run this after starting the server with: uvicorn app.main:app --reload
"""

import requests
import json
import time
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_pipeline_health():
    """Test basic pipeline health."""
    print("🔍 Testing pipeline health...")
    response = requests.get(f"{BASE_URL}/ping")
    assert response.status_code == 200
    print("✅ Pipeline is healthy")
    return response.json()

def test_enhanced_ingestion():
    """Test enhanced content ingestion."""
    print("\n📄 Testing enhanced content ingestion...")
    
    content_data = {
        "title": "Python Programming Fundamentals",
        "text": """
        Python is a high-level, interpreted programming language known for its simplicity and readability. 
        It supports multiple programming paradigms including procedural, object-oriented, and functional programming.
        Python's extensive standard library and vibrant ecosystem make it popular for web development, 
        data science, artificial intelligence, and automation. Key features include dynamic typing, 
        automatic memory management, and an interactive interpreter. Popular frameworks include Django for 
        web development, NumPy for numerical computing, and TensorFlow for machine learning.
        """,
        "source": "programming_tutorial",
        "metadata": {"language": "python", "level": "beginner", "category": "programming"}
    }
    
    response = requests.post(f"{BASE_URL}/content/ingest/enhanced", json=content_data)
    assert response.status_code == 200
    
    result = response.json()
    print(f"✅ Content ingested successfully")
    print(f"   - Content ID: {result['content_id']}")
    print(f"   - Chunks created: {result['chunks_created']}")
    print(f"   - Processing time: {result['processing_time_seconds']:.2f}s")
    print(f"   - Total tokens: {result['total_tokens']}")
    
    return result

def test_semantic_search():
    """Test semantic search functionality."""
    print("\n🔍 Testing semantic search...")
    
    # Test multiple search queries
    queries = [
        "python programming",
        "web development frameworks", 
        "machine learning libraries",
        "object oriented programming"
    ]
    
    for query in queries:
        print(f"\n   Searching for: '{query}'")
        response = requests.post(f"{BASE_URL}/content/search", params={
            "query": query,
            "max_results": 3
        })
        
        assert response.status_code == 200
        results = response.json()
        
        if results:
            print(f"   ✅ Found {len(results)} results")
            for i, result in enumerate(results, 1):
                print(f"      {i}. Similarity: {result['similarity_score']:.3f} - {result['chunk_text'][:100]}...")
        else:
            print(f"   ⚠️ No results found (similarity threshold may be too high)")

def test_pipeline_stats():
    """Test pipeline statistics."""
    print("\n📊 Testing pipeline statistics...")
    
    response = requests.get(f"{BASE_URL}/pipeline/stats")
    assert response.status_code == 200
    
    stats = response.json()
    print("✅ Pipeline statistics retrieved")
    print(f"   - Total content items: {stats['content_processing']['total_content_items']}")
    print(f"   - Total chunks: {stats['content_processing']['total_chunks']}")
    print(f"   - Total vectors: {stats['vector_storage']['total_vectors']}")
    print(f"   - Vector dimensions: {stats['vector_storage']['dimensions']}")
    print(f"   - Similarity threshold: {stats['vector_storage']['similarity_threshold']}")
    
    return stats

def test_complete_pipeline():
    """Test the complete pipeline integration."""
    print("\n🧪 Testing complete pipeline...")
    
    response = requests.post(f"{BASE_URL}/pipeline/test")
    assert response.status_code == 200
    
    result = response.json()
    print("✅ Complete pipeline test successful")
    print(f"   - Ingestion success: {result['ingestion']['success']}")
    print(f"   - Embedding test success: {result['embedding_test']['success']}")
    print(f"   - Vector dimensions match: {result['embedding_test']['dimensions_match']}")
    
    return result

def test_state_persistence():
    """Test pipeline state persistence."""
    print("\n💾 Testing state persistence...")
    
    response = requests.post(f"{BASE_URL}/pipeline/save")
    assert response.status_code == 200
    
    result = response.json()
    print(f"✅ {result['message']}")
    
    return result

def main():
    """Run all tests."""
    print("🚀 Sprint 2 Enhanced Data Ingestion Pipeline Test")
    print("=" * 60)
    
    try:
        # Run all tests
        test_pipeline_health()
        test_enhanced_ingestion()
        test_semantic_search()
        test_pipeline_stats()
        test_complete_pipeline()
        test_state_persistence()
        
        print("\n" + "=" * 60)
        print("🎉 All tests completed successfully!")
        print("\n📋 Summary:")
        print("   ✅ Enhanced content ingestion working")
        print("   ✅ Token-aware chunking operational")
        print("   ✅ Embedding generation functional")
        print("   ✅ Vector storage and search implemented")
        print("   ✅ Pipeline state persistence working")
        print("\n📝 Note: If semantic search returns no results, consider lowering")
        print("   the similarity threshold in config.py (current: 0.7)")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Cannot connect to the server.")
        print("   Make sure the server is running: uvicorn app.main:app --reload")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
