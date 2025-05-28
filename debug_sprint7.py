#!/usr/bin/env python3
"""
Comprehensive Debug Script for Sprint 7 Issues
Helps diagnose and fix Rate Limiting, OpenAI Configuration, and Response Parsing
"""

import os
import sys
import json
import time
import requests
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, '/Users/amankumarshrestha/Downloads/Quiz-D')

def test_rate_limiting_debug():
    """Debug rate limiting system"""
    print("🚦 DEBUGGING RATE LIMITING")
    print("=" * 40)
    
    try:
        from app.auth import get_rate_limit_status, check_rate_limit, rate_limit_storage
        from app.config import get_settings
        
        settings = get_settings()
        
        # Test client
        test_client = "debug-client-123"
        test_endpoint = "quiz_generation"
        
        print(f"✓ Rate limiting enabled: {getattr(settings, 'rate_limit_enabled', True)}")
        print(f"✓ Quiz generation limit: {getattr(settings, 'quiz_generation_rate_limit', 10)}")
        
        # Get current status
        status = get_rate_limit_status(test_client, test_endpoint)
        print(f"✓ Rate limit status: {json.dumps(status, indent=2)}")
        
        # Test check_rate_limit function
        print("\n🔄 Testing rate limit checking...")
        for i in range(3):
            result = check_rate_limit(f"{test_client}:{test_endpoint}", 5, 60)
            print(f"   Request {i+1}: {'✅ Allowed' if result else '❌ Blocked'}")
        
        # Show storage state
        print(f"\n💾 Current storage keys: {list(rate_limit_storage.keys())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Rate limiting debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_openai_debug():
    """Debug OpenAI configuration"""
    print("\n🤖 DEBUGGING OPENAI CONFIGURATION")
    print("=" * 40)
    
    # Check environment variables
    api_key = os.getenv('OPENAI_API_KEY')
    print(f"✓ OPENAI_API_KEY environment: {'Set' if api_key else 'Not set'}")
    
    if api_key:
        print(f"✓ API key format: {api_key[:10]}...{api_key[-4:]} (length: {len(api_key)})")
    
    # Check app settings
    try:
        from app.config import get_settings
        settings = get_settings()
        
        config_key = getattr(settings, 'openai_api_key', None)
        print(f"✓ Config API key: {'Set' if config_key else 'Not set'}")
        
    except Exception as e:
        print(f"❌ Config check failed: {e}")
    
    # Test DSPy configuration
    try:
        from app.dspy_quiz_generator import DSPyQuizGenerator
        
        generator = DSPyQuizGenerator()
        print(f"✓ DSPy configured: {generator.is_available()}")
        
        if generator.is_available():
            # Test simple generation
            test_result = generator.generate_simple_question("Python is a programming language.")
            print(f"✓ Test generation: {'Success' if 'error' not in test_result else 'Failed'}")
            if 'error' in test_result:
                print(f"   Error: {test_result['error']}")
        
        return True
        
    except Exception as e:
        print(f"❌ DSPy debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints_debug():
    """Debug API endpoints with detailed response parsing"""
    print("\n🌐 DEBUGGING API ENDPOINTS")
    print("=" * 40)
    
    base_url = "http://localhost:8000"
    api_key = "test-api-key-12345"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Test health endpoint
    print("🏥 Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test authentication
    print("\n🔐 Testing authentication...")
    try:
        # Test with valid key
        response = requests.get(f"{base_url}/health/detailed", headers=headers, timeout=10)
        print(f"   Valid key status: {response.status_code}")
        
        # Test with invalid key
        bad_headers = {"Authorization": "Bearer invalid-key", "Content-Type": "application/json"}
        response = requests.get(f"{base_url}/health/detailed", headers=bad_headers, timeout=10)
        print(f"   Invalid key status: {response.status_code}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test quiz generation with detailed error handling
    print("\n⚡ Testing quiz generation...")
    quiz_data = {
        "title": "Debug Test Quiz",
        "description": "A quiz for debugging",
        "topic_or_query": "Simple topic",
        "num_questions": 1,
        "question_types": ["multiple_choice"],
        "difficulty": "easy"
    }
    
    try:
        response = requests.post(
            f"{base_url}/generate/quick-quiz",
            headers=headers,
            json=quiz_data,
            timeout=30
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")
        
        if response.headers.get('content-type', '').startswith('application/json'):
            try:
                data = response.json()
                print(f"   JSON structure: {json.dumps(data, indent=2)[:500]}...")
            except json.JSONDecodeError as e:
                print(f"   JSON decode error: {e}")
                print(f"   Raw response: {response.text[:500]}")
        else:
            print(f"   Non-JSON response: {response.text[:200]}")
            
    except Exception as e:
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
    
    return True

def check_dependencies():
    """Check all required dependencies"""
    print("\n📦 CHECKING DEPENDENCIES")
    print("=" * 40)
    
    dependencies = [
        'fastapi',
        'uvicorn', 
        'pydantic',
        'dspy',
        'openai',
        'requests'
    ]
    
    missing = []
    for dep in dependencies:
        try:
            __import__(dep.replace('-', '_'))
            print(f"✅ {dep}")
        except ImportError:
            print(f"❌ {dep}")
            missing.append(dep)
    
    if missing:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
        return False
    
    return True

def check_server_status():
    """Check if server is running"""
    print("\n🖥️  CHECKING SERVER STATUS")
    print("=" * 40)
    
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print(f"✅ Server is running (status: {response.status_code})")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Server is not running")
        print("Start server with: python -m app.main")
        return False
    except Exception as e:
        print(f"❌ Server check failed: {e}")
        return False

def generate_fix_suggestions():
    """Generate suggestions to fix identified issues"""
    print("\n🔧 FIX SUGGESTIONS")
    print("=" * 40)
    
    print("1. 🚦 Rate Limiting Issues:")
    print("   - Check rate limiting is enabled in config")
    print("   - Verify rate_limit_storage is properly initialized")
    print("   - Test with: python debug_sprint7.py")
    
    print("\n2. 🤖 OpenAI Configuration:")
    print("   - Set environment variable: export OPENAI_API_KEY='your-key'")
    print("   - Or run configuration script: python configure_openai.py")
    print("   - Restart server after setting API key")
    
    print("\n3. 🌐 Response Parsing:")
    print("   - Updated test_api.py with better error handling")
    print("   - Added safe JSON parsing with fallbacks")
    print("   - Test with: python test_api.py")
    
    print("\n4. 🖥️  Server Issues:")
    print("   - Start server: python -m app.main")
    print("   - Check logs for error messages")
    print("   - Verify all dependencies are installed")

def main():
    """Main debugging function"""
    print("🔍 SPRINT 7 COMPREHENSIVE DEBUG TOOL")
    print("=" * 50)
    
    all_passed = True
    
    # Check dependencies first
    if not check_dependencies():
        all_passed = False
    
    # Check server status
    server_running = check_server_status()
    
    # Run debugging tests
    if not test_rate_limiting_debug():
        all_passed = False
    
    if not test_openai_debug():
        all_passed = False
    
    if server_running:
        if not test_api_endpoints_debug():
            all_passed = False
    else:
        print("\n⚠️  Skipping API tests - server not running")
    
    # Generate fix suggestions
    generate_fix_suggestions()
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ All debugging tests completed successfully!")
    else:
        print("⚠️  Some issues found. Check the suggestions above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
