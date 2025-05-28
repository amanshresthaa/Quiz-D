"""
Authentication and security middleware for the Quiz Generation API.
Implements API key authentication, rate limiting, and security features.
"""

import time
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict, deque

from fastapi import HTTPException, Request, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# Rate limiting storage (in production, use Redis)
rate_limit_storage: Dict[str, deque] = defaultdict(deque)

# Request size limits
MAX_REQUEST_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_CONTENT_LENGTH = 50000  # 50k characters
MAX_QUESTIONS_PER_REQUEST = 20
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000

# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}

def add_security_headers_middleware(app):
    """Add security headers middleware to the FastAPI app."""
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
            
        return response
    
    return app

class AuthenticationError(HTTPException):
    """Custom authentication error."""
    def __init__(self, detail: str = "Authentication required"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )

class RateLimitError(HTTPException):
    """Custom rate limit error."""
    def __init__(self, detail: str = "Rate limit exceeded"):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )

class RequestValidationError(HTTPException):
    """Custom request validation error."""
    def __init__(self, detail: str = "Request validation failed"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )

def get_client_identifier(request: Request) -> str:
    """Get client identifier for rate limiting."""
    # Try to get from X-Forwarded-For header (load balancer/proxy)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain
        return forwarded_for.split(",")[0].strip()
    
    # Fall back to direct client IP
    client_host = getattr(request.client, "host", "unknown")
    return client_host

def check_rate_limit(client_id: str, limit: int = 60, window: int = 60) -> bool:
    """
    Check if client is within rate limit.
    
    Args:
        client_id: Client identifier
        limit: Number of requests allowed
        window: Time window in seconds
        
    Returns:
        bool: True if within limit, False if exceeded
    """
    now = time.time()
    window_start = now - window
    
    # Clean old entries
    client_requests = rate_limit_storage[client_id]
    while client_requests and client_requests[0] < window_start:
        client_requests.popleft()
    
    # Check limit
    if len(client_requests) >= limit:
        return False
    
    # Add current request
    client_requests.append(now)
    return True

def validate_api_key(api_key: str) -> bool:
    """
    Validate API key.
    
    Args:
        api_key: API key to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    settings = get_settings()
    
    # If API key authentication is not required, allow all requests
    if not getattr(settings, 'require_api_key', False):
        return True
    
    # If API key authentication is required, check the provided key
    if hasattr(settings, 'api_keys') and settings.api_keys:
        # Multiple API keys support
        return api_key in settings.api_keys
    elif hasattr(settings, 'api_key') and settings.api_key:
        # Single API key
        return api_key == settings.api_key
    
    # If no valid API keys are configured but authentication is required
    return False

def sanitize_content(content: str) -> str:
    """
    Sanitize content to prevent prompt injection and other issues.
    
    Args:
        content: Content to sanitize
        
    Returns:
        str: Sanitized content
    """
    if not content:
        return content
    
    # Remove potential prompt injection patterns
    dangerous_patterns = [
        "ignore previous instructions",
        "ignore all previous",
        "new instructions:",
        "system:",
        "assistant:",
        "user:",
        "###",
        "---",
        "```",
        "<script",
        "</script>",
        "javascript:",
        "data:text/html",
    ]
    
    sanitized = content
    for pattern in dangerous_patterns:
        sanitized = sanitized.replace(pattern.lower(), f"[FILTERED: {pattern}]")
        sanitized = sanitized.replace(pattern.upper(), f"[FILTERED: {pattern}]")
        sanitized = sanitized.replace(pattern.title(), f"[FILTERED: {pattern}]")
    
    # Limit length
    if len(sanitized) > MAX_CONTENT_LENGTH:
        sanitized = sanitized[:MAX_CONTENT_LENGTH] + "... [TRUNCATED]"
        logger.warning(f"Content truncated from {len(content)} to {MAX_CONTENT_LENGTH} characters")
    
    return sanitized

# Security middleware
security = HTTPBearer(auto_error=False)

async def verify_api_key(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Verify API key from Authorization header.
    
    Args:
        request: FastAPI request object
        credentials: HTTP bearer credentials
        
    Returns:
        str: Client identifier
        
    Raises:
        AuthenticationError: If authentication fails
    """
    settings = get_settings()
    
    # Check if authentication is required
    require_auth = getattr(settings, 'require_api_key', False)
    
    if require_auth:
        if not credentials:
            raise AuthenticationError("API key required. Use Authorization: Bearer <api-key>")
        
        if not validate_api_key(credentials.credentials):
            raise AuthenticationError("Invalid API key")
    
    # Get client identifier for rate limiting
    client_id = get_client_identifier(request)
    
    return client_id

async def check_request_limits(request: Request) -> None:
    """
    Check request size and other limits.
    
    Args:
        request: FastAPI request object
        
    Raises:
        RequestValidationError: If limits are exceeded
    """
    # Check content length
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_REQUEST_SIZE_BYTES:
        raise RequestValidationError(
            f"Request too large. Maximum size: {MAX_REQUEST_SIZE_BYTES} bytes"
        )

async def apply_rate_limiting(client_id: str, endpoint: str = "default") -> None:
    """
    Apply rate limiting based on endpoint and client.
    
    Args:
        client_id: Client identifier
        endpoint: Endpoint name for specific limits
        
    Raises:
        RateLimitError: If rate limit is exceeded
    """
    settings = get_settings()
    
    # Skip rate limiting if disabled
    if not getattr(settings, 'rate_limit_enabled', True):
        return
    
    # Different limits for different endpoints
    limits = {
        "quiz_generation": {"limit": getattr(settings, 'quiz_generation_rate_limit', 10), "window": 300},  # 10 requests per 5 minutes
        "question_generation": {"limit": getattr(settings, 'question_generation_rate_limit', 30), "window": 300},  # 30 requests per 5 minutes
        "content_ingestion": {"limit": getattr(settings, 'content_ingestion_rate_limit', 20), "window": 300},  # 20 requests per 5 minutes
        "default": {"limit": getattr(settings, 'default_rate_limit', 60), "window": 60}  # 60 requests per minute
    }
    
    limit_config = limits.get(endpoint, limits["default"])
    
    # Use endpoint-specific client key for rate limiting
    rate_limit_key = f"{client_id}:{endpoint}"
    
    if not check_rate_limit(
        rate_limit_key, 
        limit_config["limit"], 
        limit_config["window"]
    ):
        logger.warning(f"Rate limit exceeded for client {client_id} on endpoint {endpoint}")
        raise RateLimitError(
            f"Rate limit exceeded for {endpoint}. "
            f"Limit: {limit_config['limit']} requests per {limit_config['window']} seconds"
        )

def get_rate_limit_status(client_id: str, endpoint: str = "default") -> Dict[str, Any]:
    """
    Get current rate limit status for debugging.
    
    Args:
        client_id: Client identifier
        endpoint: Endpoint name
        
    Returns:
        Dict with rate limiting status information
    """
    import time
    
    settings = get_settings()
    limits = {
        "quiz_generation": {"limit": getattr(settings, 'quiz_generation_rate_limit', 10), "window": 300},
        "question_generation": {"limit": getattr(settings, 'question_generation_rate_limit', 30), "window": 300},
        "content_ingestion": {"limit": getattr(settings, 'content_ingestion_rate_limit', 20), "window": 300},
        "default": {"limit": getattr(settings, 'default_rate_limit', 60), "window": 60}
    }
    
    limit_config = limits.get(endpoint, limits["default"])
    rate_limit_key = f"{client_id}:{endpoint}"
    
    # Check current usage
    now = time.time()
    window_start = now - limit_config["window"]
    
    client_requests = rate_limit_storage[rate_limit_key]
    # Count requests in current window
    current_requests = sum(1 for req_time in client_requests if req_time >= window_start)
    
    return {
        "client_id": client_id,
        "endpoint": endpoint,
        "rate_limit_key": rate_limit_key,
        "current_requests": current_requests,
        "limit": limit_config["limit"],
        "window_seconds": limit_config["window"],
        "remaining_requests": max(0, limit_config["limit"] - current_requests),
        "window_start": window_start,
        "current_time": now,
        "rate_limiting_enabled": getattr(settings, 'rate_limit_enabled', True)
    }

def validate_quiz_request(request_data: dict) -> dict:
    """
    Validate and sanitize quiz generation request.
    
    Args:
        request_data: Request data dictionary
        
    Returns:
        dict: Sanitized request data
        
    Raises:
        RequestValidationError: If validation fails
    """
    # Validate number of questions
    num_questions = request_data.get("num_questions", 5)
    if num_questions > MAX_QUESTIONS_PER_REQUEST:
        raise RequestValidationError(
            f"Too many questions requested. Maximum: {MAX_QUESTIONS_PER_REQUEST}"
        )
    
    # Sanitize text content
    if "topic_or_query" in request_data:
        request_data["topic_or_query"] = sanitize_content(request_data["topic_or_query"])
    
    if "title" in request_data:
        title = request_data["title"]
        if len(title) > MAX_TITLE_LENGTH:
            raise RequestValidationError(f"Title too long. Maximum: {MAX_TITLE_LENGTH} characters")
        request_data["title"] = sanitize_content(title)
    
    if "description" in request_data:
        description = request_data["description"]
        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise RequestValidationError(f"Description too long. Maximum: {MAX_DESCRIPTION_LENGTH} characters")
        request_data["description"] = sanitize_content(description)
    
    return request_data

def validate_content_request(request_data: dict) -> dict:
    """
    Validate and sanitize content ingestion request.
    
    Args:
        request_data: Request data dictionary
        
    Returns:
        dict: Sanitized request data
        
    Raises:
        RequestValidationError: If validation fails
    """
    # Sanitize text content
    if "text" in request_data:
        text = request_data["text"]
        if not text.strip():
            raise RequestValidationError("Text content cannot be empty")
        request_data["text"] = sanitize_content(text)
    
    if "title" in request_data:
        title = request_data["title"]
        if len(title) > MAX_TITLE_LENGTH:
            raise RequestValidationError(f"Title too long. Maximum: {MAX_TITLE_LENGTH} characters")
        request_data["title"] = sanitize_content(title)
    
    return request_data

# Dependency functions for FastAPI
async def get_authenticated_client(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Get authenticated client ID."""
    await check_request_limits(request)
    client_id = await verify_api_key(request, credentials)
    return client_id

async def get_authenticated_client_with_quiz_limits(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Get authenticated client with quiz generation rate limits."""
    client_id = await get_authenticated_client(request, credentials)
    await apply_rate_limiting(client_id, "quiz_generation")
    return client_id

async def get_authenticated_client_with_question_limits(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Get authenticated client with question generation rate limits."""
    client_id = await get_authenticated_client(request, credentials)
    await apply_rate_limiting(client_id, "question_generation")
    return client_id

async def get_authenticated_client_with_content_limits(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """Get authenticated client with content ingestion rate limits."""
    client_id = await get_authenticated_client(request, credentials)
    await apply_rate_limiting(client_id, "content_ingestion")
    return client_id
