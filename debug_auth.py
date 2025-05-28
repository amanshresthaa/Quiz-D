#!/usr/bin/env python3
"""
Debug authentication settings
"""

import os
from app.config import get_settings

# Set environment variables
os.environ['REQUIRE_API_KEY'] = 'true'
os.environ['API_KEY'] = 'test-api-key-12345'

settings = get_settings()

print("=== Authentication Settings Debug ===")
print(f"require_api_key: {getattr(settings, 'require_api_key', 'NOT SET')}")
print(f"api_key: {getattr(settings, 'api_key', 'NOT SET')}")
print(f"api_keys: {getattr(settings, 'api_keys', 'NOT SET')}")

# Test the validate function
from app.auth import validate_api_key

print("\n=== API Key Validation Tests ===")
print(f"Valid key test: {validate_api_key('test-api-key-12345')}")
print(f"Invalid key test: {validate_api_key('invalid-key')}")
