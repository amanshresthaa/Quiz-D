"""
Application configuration management using Pydantic BaseSettings.
Handles environment variables and configuration validation.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, List
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host address", alias="API_HOST")
    api_port: int = Field(default=8000, description="API port number", alias="API_PORT")
    api_workers: int = Field(default=1, description="Number of API workers", alias="WORKERS")
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")
    
    # DSPy Configuration
    dspy_model: str = Field(default="gpt-4o-mini", description="DSPy model to use")
    dspy_max_tokens: int = Field(default=500, description="Maximum tokens for DSPy completions")
    
    # Database Configuration
    database_url: str = Field(default="sqlite:///./quiz_app.db", description="Database connection URL")
    
    # Content Processing Configuration
    max_chunk_size: int = Field(default=500, description="Maximum number of tokens per content chunk")
    chunk_overlap: int = Field(default=100, description="Overlap between content chunks in tokens")
    preserve_sentence_integrity: bool = Field(default=True, description="Preserve sentence boundaries when chunking")
    
    # Embedding Configuration
    embedding_model: str = Field(default="text-embedding-3-small", description="OpenAI embedding model to use")
    embedding_dimensions: int = Field(default=512, description="Embedding vector dimensions")
    embedding_batch_size: int = Field(default=100, description="Batch size for embedding generation")
    
    # Vector Store Configuration
    vector_store_type: str = Field(default="faiss", description="Type of vector store (faiss, chroma, etc.)")
    vector_index_path: str = Field(default="./data/vector_index", description="Path to store vector index")
    similarity_threshold: float = Field(default=0.7, description="Minimum similarity threshold for retrieval")
    max_retrieval_results: int = Field(default=10, description="Maximum number of results to retrieve")
    
    # Hybrid Search Configuration
    hybrid_semantic_weight: float = Field(default=0.7, description="Weight for semantic search in hybrid mode")
    hybrid_lexical_weight: float = Field(default=0.3, description="Weight for lexical search in hybrid mode")
    hybrid_strategy: str = Field(default="weighted_fusion", description="Default hybrid fusion strategy")
    rrf_k_parameter: int = Field(default=60, description="K parameter for reciprocal rank fusion")
    
    # Lexical Search Configuration  
    bm25_k1_parameter: float = Field(default=1.5, description="BM25 k1 parameter for term frequency scaling")
    bm25_b_parameter: float = Field(default=0.75, description="BM25 b parameter for document length normalization")
    use_stemming: bool = Field(default=True, description="Whether to use stemming in lexical search")
    remove_stopwords: bool = Field(default=True, description="Whether to remove stopwords in lexical search")
    
    # Retrieval Configuration
    auto_mode_enabled: bool = Field(default=True, description="Whether to enable automatic search mode selection")
    fallback_to_lexical: bool = Field(default=True, description="Fall back to lexical search if semantic fails")
    search_timeout_seconds: int = Field(default=30, description="Timeout for search operations in seconds")
    
    # Security Configuration
    secret_key: str = Field(default="dev-secret-key", description="Application secret key")
    
    # Authentication Configuration (Sprint 7)
    require_api_key: bool = Field(default=False, description="Whether to require API key authentication")
    api_key: Optional[str] = Field(default=None, description="Single API key for authentication")
    api_keys: Optional[list] = Field(default=None, description="List of valid API keys")
    
    # Rate Limiting Configuration (Sprint 7)
    rate_limit_enabled: bool = Field(default=True, description="Whether to enable rate limiting")
    default_rate_limit: int = Field(default=60, description="Default requests per minute")
    quiz_generation_rate_limit: int = Field(default=10, description="Quiz generation requests per 5 minutes")
    question_generation_rate_limit: int = Field(default=30, description="Question generation requests per 5 minutes")
    content_ingestion_rate_limit: int = Field(default=20, description="Content ingestion requests per 5 minutes")
    
    # Request Validation Configuration (Sprint 7)
    max_request_size_mb: int = Field(default=10, description="Maximum request size in MB")
    max_content_length: int = Field(default=50000, description="Maximum content length in characters")
    max_questions_per_request: int = Field(default=20, description="Maximum questions per request")
    max_title_length: int = Field(default=200, description="Maximum title length")
    max_description_length: int = Field(default=1000, description="Maximum description length")
    
    # Security Features (Sprint 7)
    enable_input_sanitization: bool = Field(default=True, description="Whether to sanitize user inputs")
    enable_security_headers: bool = Field(default=True, description="Whether to add security headers")
    enable_cors_protection: bool = Field(default=False, description="Whether to restrict CORS origins")
    allowed_cors_origins: list = Field(default=["*"], description="Allowed CORS origins")
    
    # Production Configuration (Sprint 7)
    api_timeout_seconds: int = Field(default=300, description="API request timeout in seconds")
    quiz_generation_timeout_seconds: int = Field(default=120, description="Quiz generation timeout in seconds")
    question_generation_timeout_seconds: int = Field(default=60, description="Question generation timeout in seconds")
    
    # Sprint 7: Production timeouts
    api_timeout: int = Field(default=30, description="API request timeout in seconds")
    quiz_generation_timeout: int = Field(default=300, description="Quiz generation timeout in seconds")
    question_generation_timeout: int = Field(default=120, description="Question generation timeout in seconds")
    
    # Production configuration
    production_mode: bool = Field(default=False, description="Enable production mode")
    allowed_origins: List[str] = Field(default=["*"], description="CORS allowed origins")
    allowed_hosts: List[str] = Field(default=["*"], description="Trusted hosts")
    
    # Monitoring and logging
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables
        populate_by_name = True  # Allow using field names and aliases


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings


def validate_required_settings():
    """Validate that required settings are present."""
    required_checks = []
    
    # Check if running in production-like environment
    if settings.secret_key == "dev-secret-key":
        print("⚠️  WARNING: Using default secret key. Set SECRET_KEY in production.")
    
    if not settings.openai_api_key:
        print("⚠️  WARNING: OPENAI_API_KEY not set. DSPy and embedding features will not work.")
        required_checks.append("OPENAI_API_KEY")
    
    # Create vector index directory if it doesn't exist
    import os
    os.makedirs(os.path.dirname(settings.vector_index_path), exist_ok=True)
    
    return len(required_checks) == 0
