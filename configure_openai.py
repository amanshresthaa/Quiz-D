#!/usr/bin/env python3
"""
OpenAI Configuration and Testing Script for Quiz Generation
Helps configure and test OpenAI API key for DSPy integration
"""

import os
import sys
import json
from typing import Optional

def check_openai_api_key() -> Optional[str]:
    """Check if OpenAI API key is configured."""
    api_key = os.getenv('OPENAI_API_KEY')
    if api_key:
        print(f"✅ OpenAI API key found: {api_key[:10]}...{api_key[-4:]}")
        return api_key
    else:
        print("❌ OpenAI API key not found in environment variables")
        return None

def test_openai_connection(api_key: str) -> bool:
    """Test OpenAI API connection."""
    try:
        import openai
        openai.api_key = api_key
        
        # Test with a simple completion
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Say 'API test successful'"}],
            max_tokens=10
        )
        
        if response.choices[0].message.content:
            print("✅ OpenAI API connection successful")
            return True
        else:
            print("❌ OpenAI API connection failed - no response")
            return False
            
    except ImportError:
        print("❌ OpenAI library not installed. Install with: pip install openai")
        return False
    except Exception as e:
        print(f"❌ OpenAI API connection failed: {e}")
        return False

def test_dspy_integration() -> bool:
    """Test DSPy integration with OpenAI."""
    try:
        # Import DSPy quiz generator
        sys.path.append('/Users/amankumarshrestha/Downloads/Quiz-D')
        from app.dspy_quiz_generator import DSPyQuizGenerator
        
        generator = DSPyQuizGenerator()
        
        if generator.is_available():
            print("✅ DSPy is properly configured")
            
            # Test simple question generation
            test_text = "Python is a programming language known for its simplicity and readability."
            result = generator.generate_simple_question(test_text)
            
            if "error" not in result:
                print("✅ DSPy question generation working")
                print(f"   Sample question: {result.get('question', 'N/A')}")
                print(f"   Sample answer: {result.get('answer', 'N/A')}")
                return True
            else:
                print(f"❌ DSPy question generation error: {result.get('error')}")
                return False
        else:
            print("❌ DSPy is not properly configured")
            return False
            
    except ImportError as e:
        print(f"❌ Cannot import DSPy modules: {e}")
        return False
    except Exception as e:
        print(f"❌ DSPy integration test failed: {e}")
        return False

def create_env_file(api_key: str):
    """Create .env file with OpenAI API key."""
    env_path = "/Users/amankumarshrestha/Downloads/Quiz-D/.env"
    
    # Read existing .env file if it exists
    existing_env = {}
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    existing_env[key] = value
    
    # Add or update OpenAI API key
    existing_env['OPENAI_API_KEY'] = api_key
    
    # Write back to .env file
    with open(env_path, 'w') as f:
        f.write("# Environment variables for Quiz Generation App\n\n")
        f.write("# Authentication\n")
        f.write("REQUIRE_API_KEY=true\n")
        f.write("API_KEY=test-api-key-12345\n\n")
        f.write("# OpenAI Configuration\n")
        f.write(f"OPENAI_API_KEY={api_key}\n\n")
        
        # Write other existing variables
        for key, value in existing_env.items():
            if key not in ['OPENAI_API_KEY', 'REQUIRE_API_KEY', 'API_KEY']:
                f.write(f"{key}={value}\n")
    
    print(f"✅ Created/updated .env file at {env_path}")

def main():
    """Main configuration and testing function."""
    print("🔧 OpenAI Configuration and Testing for Quiz Generation\n")
    
    # Check current API key
    current_key = check_openai_api_key()
    
    if not current_key:
        print("\n📝 To configure OpenAI API key:")
        print("1. Get your API key from https://platform.openai.com/api-keys")
        print("2. Set environment variable: export OPENAI_API_KEY='your-key-here'")
        print("3. Or provide it interactively:")
        
        api_key = input("\nEnter your OpenAI API key (or press Enter to skip): ").strip()
        if api_key:
            create_env_file(api_key)
            os.environ['OPENAI_API_KEY'] = api_key
            current_key = api_key
        else:
            print("⚠️  Skipping configuration. Quiz generation will not work without API key.")
            return False
    
    # Test OpenAI connection
    print("\n🔗 Testing OpenAI connection...")
    if not test_openai_connection(current_key):
        return False
    
    # Test DSPy integration
    print("\n🧠 Testing DSPy integration...")
    if not test_dspy_integration():
        return False
    
    print("\n✅ All tests passed! Quiz generation should work properly.")
    print("\n🚀 You can now:")
    print("1. Start the API server: python -m app.main")
    print("2. Test quiz generation endpoints")
    print("3. Use the CLI tool: python quiz_cli.py")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
