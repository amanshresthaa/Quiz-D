#!/usr/bin/env python3
"""
Application launcher script for the Quiz Generation system.
Provides easy startup with configuration validation.
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from app.config import get_settings, validate_required_settings
except ImportError:
    print("❌ Could not import application modules")
    print("Make sure you're in the project root directory and dependencies are installed")
    sys.exit(1)


def check_dependencies():
    """Check if required dependencies are installed."""
    try:
        import fastapi
        import uvicorn
        import pydantic
        import dspy
        print("✅ All required dependencies found")
        return True
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        return False


def check_configuration():
    """Check application configuration."""
    settings = get_settings()
    
    print("🔧 Configuration Check:")
    print(f"   API Host: {settings.api_host}")
    print(f"   API Port: {settings.api_port}")
    print(f"   Workers: {settings.api_workers}")
    print(f"   Max Chunk Size: {settings.max_chunk_size}")
    print(f"   Log Level: {settings.log_level}")
    
    # Check for .env file
    if os.path.exists('.env'):
        print("✅ .env file found")
    else:
        print("⚠️  .env file not found (using defaults)")
        if os.path.exists('.env.example'):
            print("💡 Tip: cp .env.example .env")
    
    # Validate settings
    config_valid = validate_required_settings()
    
    if settings.openai_api_key:
        print("✅ OpenAI API key configured")
    else:
        print("⚠️  OpenAI API key not set (DSPy will use fallback mode)")
    
    return config_valid


def start_application(host=None, port=None, reload=True, workers=None):
    """Start the FastAPI application."""
    settings = get_settings()
    
    # Use provided values or fall back to settings
    host = host or settings.api_host
    port = port or settings.api_port
    workers = workers or settings.api_workers
    
    print(f"🚀 Starting Quiz Generation API...")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Reload: {reload}")
    print(f"   Workers: {workers}")
    print()
    print(f"📊 API Documentation: http://{host}:{port}/docs")
    print(f"🔄 Alternative docs: http://{host}:{port}/redoc")
    print(f"🏥 Health check: http://{host}:{port}/ping")
    print()
    
    try:
        import uvicorn
        uvicorn.run(
            "app.main:app",
            host=host,
            port=port,
            reload=reload,
            workers=workers if not reload else 1,  # Multiple workers don't work with reload
            log_level=settings.log_level.lower()
        )
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Failed to start application: {e}")
        sys.exit(1)


def run_tests():
    """Run the test suite."""
    print("🧪 Running test suite...")
    try:
        result = subprocess.run([
            sys.executable, "-m", "pytest", "tests/", "-v"
        ], capture_output=False)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Failed to run tests: {e}")
        return False


def run_dspy_exploration():
    """Run DSPy exploration script."""
    print("🔍 Running DSPy exploration...")
    try:
        subprocess.run([
            sys.executable, "scripts/dspy_exploration.py"
        ], capture_output=False)
    except Exception as e:
        print(f"❌ Failed to run DSPy exploration: {e}")


def main():
    """Main launcher function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Quiz Generation Application Launcher")
    parser.add_argument("--host", default=None, help="API host address")
    parser.add_argument("--port", type=int, default=None, help="API port number")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    parser.add_argument("--workers", type=int, default=None, help="Number of workers")
    parser.add_argument("--test", action="store_true", help="Run tests before starting")
    parser.add_argument("--dspy-demo", action="store_true", help="Run DSPy exploration demo")
    parser.add_argument("--check-only", action="store_true", help="Only check configuration, don't start")
    
    args = parser.parse_args()
    
    print("Quiz Generation Application Launcher")
    print("=" * 50)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Check configuration
    config_valid = check_configuration()
    
    if args.check_only:
        print(f"\n✅ Configuration check complete (Valid: {config_valid})")
        return
    
    # Run tests if requested
    if args.test:
        if not run_tests():
            print("❌ Tests failed. Use --force to start anyway.")
            sys.exit(1)
        print("✅ All tests passed")
    
    # Run DSPy demo if requested
    if args.dspy_demo:
        run_dspy_exploration()
        return
    
    # Start application
    print("\n" + "=" * 50)
    start_application(
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        workers=args.workers
    )


if __name__ == "__main__":
    main()
