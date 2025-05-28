#!/usr/bin/env python3
"""
Check the current configuration of the Quiz API
"""

import sys
import os
sys.path.append('/Users/amankumarshrestha/Downloads/Quiz-D')

from app.config import get_settings

def main():
    """Check configuration settings"""
    settings = get_settings()
    
    print("🔧 Current Quiz API Configuration")
    print("="*50)
    
    # Authentication settings
    print(f"require_api_key: {settings.require_api_key}")
    print(f"api_key: {'SET' if settings.api_key else 'NOT SET'}")
    print(f"api_keys: {'SET' if settings.api_keys else 'NOT SET'}")
    
    # API settings
    print(f"api_host: {settings.api_host}")
    print(f"api_port: {settings.api_port}")
    
    # OpenAI settings
    print(f"openai_api_key: {'SET' if settings.openai_api_key else 'NOT SET'}")
    
    # Security settings
    print(f"secret_key: {'CUSTOM' if settings.secret_key != 'dev-secret-key' else 'DEFAULT'}")
    
    print("\n🧪 Testing auth configuration...")
    
    # Test the validation function
    from app.auth import validate_api_key
    
    print(f"validate_api_key('test'): {validate_api_key('test')}")
    print(f"validate_api_key(''): {validate_api_key('')}")
    
    # Check environment variables
    print("\n🌍 Environment Variables:")
    auth_related = ['REQUIRE_API_KEY', 'API_KEY', 'SECRET_KEY', 'OPENAI_API_KEY']
    for var in auth_related:
        value = os.getenv(var)
        print(f"{var}: {'SET' if value else 'NOT SET'}")

if __name__ == "__main__":
    main()
