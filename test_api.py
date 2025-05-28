#!/usr/bin/env python3
"""
Test script for Quiz Generation API endpoints
Tests authentication, rate limiting, and basic functionality
"""

import requests
import json
import time
from typing import Dict, Any

# API Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key-12345"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def test_health_endpoint():
    """Test health check endpoint (no auth required)"""
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Health check passed")
            return True
        else:
            print("❌ Health check failed")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_detailed_health_endpoint():
    """Test detailed health endpoint (no auth required)"""
    print("\n🏥 Testing detailed health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health/detailed")
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Detailed health check passed")
            print(f"   System status: {data.get('status')}")
            print(f"   CPU usage: {data.get('metrics', {}).get('cpu_percent', 'N/A')}%")
            return True
        else:
            print("❌ Detailed health check failed")
            return False
    except Exception as e:
        print(f"❌ Detailed health check error: {e}")
        return False

def test_authentication():
    """Test authentication with valid and invalid keys"""
    print("\n🔐 Testing authentication...")
    
    # Test with valid API key
    try:
        response = requests.post(
            f"{BASE_URL}/generate/question",
            headers=HEADERS,
            json={"topic_or_query": "Python programming basics"}
        )
        print(f"Valid auth status: {response.status_code}")
        if response.status_code in [200, 422]:  # 422 for validation errors is OK
            print("✅ Valid authentication working")
        else:
            print(f"❌ Valid authentication failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Valid auth test error: {e}")
        return False
    
    # Test with invalid API key
    try:
        invalid_headers = {"Authorization": "Bearer invalid-key", "Content-Type": "application/json"}
        response = requests.post(
            f"{BASE_URL}/generate/question",
            headers=invalid_headers,
            json={"topic_or_query": "Python programming basics"}
        )
        print(f"Invalid auth status: {response.status_code}")
        if response.status_code == 401:
            print("✅ Invalid authentication properly rejected")
            return True
        else:
            print(f"❌ Invalid authentication not properly rejected: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Invalid auth test error: {e}")
        return False

def test_rate_limiting():
    """Test rate limiting functionality"""
    print("\n⏱️ Testing rate limiting...")
    
    # Make multiple rapid requests to test rate limiting
    requests_made = 0
    rate_limited = False
    
    for i in range(12):  # Exceed the limit of 10 quiz requests per 5 minutes
        try:
            response = requests.post(
                f"{BASE_URL}/generate/question",
                headers=HEADERS,
                json={"topic_or_query": "Test content for rate limiting"}
            )
            requests_made += 1
            
            if response.status_code == 429:  # Too Many Requests
                print(f"✅ Rate limiting triggered after {requests_made} requests")
                rate_limited = True
                break
            elif response.status_code not in [200, 422]:
                print(f"❌ Unexpected response: {response.status_code}")
                break
                
            time.sleep(0.1)  # Small delay between requests
            
        except Exception as e:
            print(f"❌ Rate limiting test error: {e}")
            return False
    
    if not rate_limited and requests_made >= 10:
        print(f"⚠️ Rate limiting may not be working (made {requests_made} requests)")
        return False
    
    return True

def test_quiz_generation():
    """Test quiz generation endpoint"""
    print("\n📝 Testing quiz generation...")
    
    # First ingest some content
    content_data = {
        "title": "Python Programming Guide",
        "text": "Python is a high-level programming language. It supports multiple programming paradigms including procedural, object-oriented, and functional programming. Python's syntax is designed to be readable and straightforward.",
        "source": "test_content",
        "metadata": {"category": "programming"}
    }
    
    try:
        # Ingest content first
        content_response = requests.post(
            f"{BASE_URL}/content/ingest",
            headers=HEADERS,
            json=content_data
        )
        
        if content_response.status_code != 200:
            print(f"❌ Failed to ingest content: {content_response.text}")
            return False
        
        content_result = content_response.json()
        content_id = content_result.get('content_id')
        
        # Now generate quiz
        quiz_data = {
            "content_ids": [content_id],
            "num_questions": 2,
            "question_types": ["multiple_choice"],
            "difficulty_levels": ["easy"],
            "title": "Python Programming Quiz",
            "description": "A basic quiz about Python programming concepts"
        }
        
        response = requests.post(
            f"{BASE_URL}/quiz/generate",
            headers=HEADERS,
            json=quiz_data,
            timeout=60
        )
        
        print(f"Quiz generation status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Quiz generation successful")
            print(f"   Quiz ID: {data.get('quiz_id', 'N/A')}")
            return True
        elif response.status_code == 422:
            print(f"❌ Validation error: {response.json()}")
            return False
        else:
            print(f"❌ Quiz generation failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Quiz generation error: {e}")
        return False

def test_content_ingestion():
    """Test content ingestion endpoint"""
    print("\n📚 Testing content ingestion...")
    
    content_data = {
        "title": "Machine Learning Introduction",
        "text": "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed.",
        "source": "test_source",
        "metadata": {"category": "AI"}
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/content/ingest",
            headers=HEADERS,
            json=content_data
        )
        
        print(f"Content ingestion status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Content ingestion successful")
            print(f"   Content ID: {data.get('content_id', 'N/A')}")
            print(f"   Chunks created: {data.get('chunks_created', 'N/A')}")
            return True
        else:
            print(f"❌ Content ingestion failed: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Content ingestion error: {e}")
        return False

def test_quick_quiz_generation():
    """Test quick quiz generation endpoint"""
    print("\n⚡ Testing quick quiz generation...")
    
    quiz_data = {
        "title": "Python Basics Quiz",
        "description": "A quick quiz about Python programming",
        "topic_or_query": "Python programming fundamentals",
        "num_questions": 2,
        "question_types": ["multiple_choice"],
        "difficulty": "easy"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/generate/quick-quiz",
            headers=HEADERS,
            json=quiz_data,
            timeout=60
        )
        
        print(f"Quick quiz generation status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ Quick quiz generation successful")
                
                # Safe parsing of response data
                quiz_info = data.get('quiz', {})
                if quiz_info and isinstance(quiz_info, dict):
                    questions = quiz_info.get('questions', [])
                    question_count = len(questions) if questions else 0
                    print(f"   Quiz generated with {question_count} questions")
                    
                    # Show quiz details if available
                    quiz_title = quiz_info.get('title', 'Untitled Quiz')
                    print(f"   Quiz title: {quiz_title}")
                    
                    if questions:
                        print(f"   First question: {questions[0].get('question_text', 'N/A')[:100]}...")
                else:
                    print("   Quiz data structure is not as expected")
                    print(f"   Raw response keys: {list(data.keys())}")
                
                return True
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                print(f"   Raw response: {response.text[:200]}...")
                return False
        elif response.status_code == 422:
            try:
                error_data = response.json()
                print(f"❌ Validation error: {error_data}")
            except json.JSONDecodeError:
                print(f"❌ Validation error (unparseable): {response.text}")
            return False
        elif response.status_code == 500:
            print(f"❌ Server error: {response.text}")
            try:
                error_data = response.json()
                if 'detail' in error_data:
                    print(f"   Error details: {error_data['detail']}")
            except:
                pass
            return False
        else:
            print(f"❌ Quick quiz generation failed: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Quick quiz generation timed out (60 seconds)")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ Connection error - is the server running?")
        return False
    except Exception as e:
        print(f"❌ Quick quiz generation error: {e}")
        return False

def test_monitoring_endpoints():
    """Test monitoring endpoints"""
    print("\n📊 Testing monitoring endpoints...")
    
    # Test metrics endpoint
    try:
        response = requests.get(f"{BASE_URL}/metrics")
        print(f"Metrics endpoint status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Metrics endpoint working")
            print(f"   Total requests: {data.get('request_metrics', {}).get('total_requests', 'N/A')}")
        else:
            print(f"❌ Metrics endpoint failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Metrics endpoint error: {e}")
        return False
    
    # Test Prometheus metrics
    try:
        response = requests.get(f"{BASE_URL}/metrics/prometheus")
        print(f"Prometheus metrics status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Prometheus metrics endpoint working")
            return True
        else:
            print(f"❌ Prometheus metrics failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Prometheus metrics error: {e}")
        return False

def main():
    """Run all API tests"""
    print("🚀 Starting Quiz Generation API Tests")
    print("=" * 50)
    
    tests = [
        test_health_endpoint,
        test_detailed_health_endpoint,
        test_authentication,
        test_rate_limiting,
        test_content_ingestion,
        test_quiz_generation,
        test_quick_quiz_generation,
        test_monitoring_endpoints
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
        
        time.sleep(1)  # Small delay between tests
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All tests passed!")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
