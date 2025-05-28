"""
Main FastAPI application for the Quiz generation system.
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any
import uuid
import time
from datetime import datetime
import logging

from app.config import get_settings, validate_required_settings
from app.auth import (
    get_authenticated_client_with_quiz_limits, 
    get_authenticated_client_with_question_limits, 
    get_authenticated_client_with_content_limits,
    add_security_headers_middleware,
    AuthenticationError, RateLimitError, RequestValidationError
)
from app.models import (
    HealthResponse, ContentIngestionRequest, ContentIngestionResponse,
    QuizGenerationRequest, QuizGenerationResponse, ContentItem, Quiz, Question,
    VectorSearchResult
)
from app.content_processor import get_content_processor, ContentProcessor
from app.dspy_quiz_generator import get_dspy_quiz_generator, DSPyQuizGenerator
from app.ingestion_pipeline import get_data_ingestion_pipeline, DataIngestionPipeline
from app.question_generation import get_question_generation_module, QuestionGenerationModule
from app.quiz_orchestrator import get_quiz_orchestrator, QuizOrchestrator
from app.question_api_models import (
    QuestionGenerationRequest, MultiQuestionGenerationRequest, QuickQuizGenerationRequest,
    QuestionGenerationResponse, MultiQuestionGenerationResponse, QuickQuizGenerationResponse,
    QuestionGenerationStats
)
from app.middleware import (
    add_timeout_middleware, add_request_size_middleware, add_response_time_middleware,
    with_quiz_timeout, with_question_timeout, task_manager
)
from app.monitoring import (
    setup_logging, add_monitoring_middleware, start_system_monitoring,
    get_health_status, metrics_collector, quiz_monitor
)
from app.file_manager import get_file_manager
from app.enhanced_logging import get_quiz_logger, setup_enhanced_logging
from app.workflow_orchestrator import get_workflow_orchestrator, WorkflowOrchestrator

# Create FastAPI application
app = FastAPI(
    title="Quiz Generation API",
    description="An AI-powered quiz generation system using DSPy and FastAPI",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Global settings - must be initialized before middleware
settings = get_settings()

# Setup enhanced logging and file management
enhanced_logger = setup_enhanced_logging()
file_manager = get_file_manager()
workflow_orchestrator = get_workflow_orchestrator()

# Setup traditional logging (for backward compatibility)
logger = setup_logging(
    log_level=getattr(settings, 'log_level', 'INFO'),
    log_format=getattr(settings, 'log_format', 'json')
)

enhanced_logger.info("Quiz Generation API initialized with structured workflow", {
    "input_dir": str(file_manager.input_dir),
    "output_dir": str(file_manager.output_dir),
    "version": "1.0.0"
})

# Configure CORS for production
cors_origins = ["*"] if not settings.production_mode else getattr(settings, 'allowed_origins', ["*"])
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Add security headers middleware
add_security_headers_middleware(app)

# Add timeout and performance middleware
add_timeout_middleware(app, timeout_seconds=getattr(settings, 'api_timeout', 30))
add_request_size_middleware(app, max_size=getattr(settings, 'max_request_size', 10 * 1024 * 1024))
add_response_time_middleware(app)

# Add monitoring middleware
if getattr(settings, 'enable_metrics', True):
    add_monitoring_middleware(app)

# Add Trusted Host middleware for production
if getattr(settings, 'production_mode', False):
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=getattr(settings, 'allowed_hosts', ["*"])
    )

# Exception handlers for custom errors
@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication failed", "error": str(exc)}
    )

@app.exception_handler(RateLimitError)
async def rate_limit_exception_handler(request: Request, exc: RateLimitError):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded", "error": str(exc), "retry_after": exc.retry_after}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=400,
        content={"detail": "Request validation failed", "error": str(exc)}
    )

# In-memory storage for quizzes (will be replaced with database in later sprints)
quiz_storage = {}


def get_quiz_orchestrator_dependency() -> QuizOrchestrator:
    """Dependency for quiz orchestrator."""
    return get_quiz_orchestrator()


def get_question_generation_module_dependency() -> QuestionGenerationModule:
    """Dependency for question generation module."""
    from app.retrieval_engine import get_retrieval_engine
    return get_question_generation_module(get_retrieval_engine())


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("🚀 Starting Quiz Generation API...")
    logger.info(f"📊 API Documentation available at: http://{settings.api_host}:{settings.api_port}/docs")
    
    # Start system monitoring
    if getattr(settings, 'enable_metrics', True):
        await start_system_monitoring()
        logger.info("📊 System monitoring started")
    
    # Validate configuration
    config_valid = validate_required_settings()
    if not config_valid:
        logger.warning("⚠️  Some configuration issues detected. Check logs above.")
    
    # Check DSPy availability
    dspy_gen = get_dspy_quiz_generator()
    if dspy_gen.is_available():
        logger.info("✅ DSPy is properly configured and ready")
    else:
        logger.warning("⚠️  DSPy not configured. Quiz generation will use sample questions.")
    
    # Initialize knowledge base and connect semantic search
    try:
        from app.simple_vector_store import get_knowledge_base
        from app.embedding_generator import get_embedding_generator
        from app.retrieval_engine import get_retrieval_engine
        
        # Initialize components
        knowledge_base = get_knowledge_base()
        embedding_generator = get_embedding_generator()
        retrieval_engine = get_retrieval_engine()
        
        # Set the global retrieval engine instance in the knowledge base
        knowledge_base._retrieval_engine = retrieval_engine
        
        # Connect embedding generator to knowledge base (this enables semantic search)
        knowledge_base.set_embedding_generator(embedding_generator)
        logger.info("✅ Semantic search enabled and connected to retrieval engine")
        
    except Exception as e:
        logger.error(f"⚠️  Failed to initialize semantic search: {e}")
        
    # Initialize question generation module
    try:
        qgen = get_question_generation_module_dependency()
        logger.info("✅ Question Generation Module initialized")
    except Exception as e:
        logger.error(f"⚠️  Question Generation Module initialization failed: {e}")
    
    logger.info("🎉 Quiz Generation API startup complete")


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint with basic health information."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0",
        config_valid=validate_required_settings()
    )


@app.get("/ping", response_model=dict)
async def ping():
    """Simple ping endpoint for health checks."""
    return {
        "message": "pong",
        "timestamp": datetime.now().isoformat(),
        "status": "healthy"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Detailed health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0",
        config_valid=validate_required_settings()
    )


@app.get("/health/detailed")
async def detailed_health_check():
    """Comprehensive health check with system metrics."""
    return get_health_status()


@app.get("/metrics")
async def get_metrics():
    """Get application metrics."""
    return {
        "summary": metrics_collector.get_summary_stats(),
        "endpoints": metrics_collector.get_endpoint_stats(),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics/prometheus")
async def get_prometheus_metrics():
    """Get metrics in Prometheus format."""
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(
        content=metrics_collector.export_prometheus_metrics(),
        media_type="text/plain"
    )


@app.get("/health/legacy", response_model=HealthResponse)
async def legacy_health_check():
    """Legacy detailed health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        version="1.0.0",
        config_valid=validate_required_settings()
    )


@app.get("/debug/semantic-search-status")
async def debug_semantic_search_status():
    """Debug endpoint to check semantic search configuration status."""
    from app.simple_vector_store import get_knowledge_base
    from app.embedding_generator import get_embedding_generator
    from app.retrieval_engine import get_retrieval_engine
    
    kb = get_knowledge_base()
    emb_gen = get_embedding_generator()
    ret_eng = get_retrieval_engine()
    
    return {
        "knowledge_base": {
            "vector_count": len(kb.vector_store._vectors),
            "has_embedding_generator": kb._embedding_generator is not None,
            "has_retrieval_engine": kb._retrieval_engine is not None,
            "kb_retrieval_engine_id": id(kb._retrieval_engine) if kb._retrieval_engine else None,
        },
        "global_retrieval_engine": {
            "id": id(ret_eng),
            "has_semantic_search": ret_eng._semantic_search_func is not None,
            "semantic_search_type": str(type(ret_eng._semantic_search_func)) if ret_eng._semantic_search_func else None,
        },
        "instances_match": kb._retrieval_engine is ret_eng if kb._retrieval_engine else False,
        "embedding_generator": {
            "available": emb_gen is not None,
            "type": str(type(emb_gen)) if emb_gen else None,
        }
    }


@app.post("/content/ingest", response_model=ContentIngestionResponse)
async def ingest_content(
    request: ContentIngestionRequest,
    authenticated: str = Depends(get_authenticated_client_with_content_limits),
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Ingest and process content for quiz generation, including embeddings and vector storage.
    """
    try:
        # Run full ingestion pipeline
        result = await pipeline.ingest_content(
            title=request.title,
            text=request.text,
            source=request.source,
            metadata=request.metadata,
            generate_embeddings=True
        )
        # Check success
        if not result.get("success", False):
            raise HTTPException(status_code=500, detail=result.get("error", "Ingestion failed"))
        # Build response
        return ContentIngestionResponse(
            content_id=result["content_id"],
            chunks_created=result["chunks_created"],
            message=f"Successfully ingested content '{result['content_title']}' with {result['chunks_created']} chunks"
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.get("/content", response_model=List[ContentItem])
async def list_content(processor: ContentProcessor = Depends(get_content_processor)):
    """
    List all ingested content items.
    
    Args:
        processor: Content processor dependency
        
    Returns:
        List[ContentItem]: List of all content items
    """
    return processor.list_content()


@app.get("/content/stats", response_model=dict)
async def get_content_stats(processor: ContentProcessor = Depends(get_content_processor)):
    """
    Get statistics about ingested content.
    
    Args:
        processor: Content processor dependency
        
    Returns:
        dict: Content statistics
    """
    return processor.get_content_statistics()


@app.get("/content/{content_id}", response_model=ContentItem)
async def get_content(
    content_id: str,
    processor: ContentProcessor = Depends(get_content_processor)
):
    """
    Get a specific content item by ID.
    
    Args:
        content_id: The content ID
        processor: Content processor dependency
        
    Returns:
        ContentItem: The requested content item
    """
    try:
        return processor.get_content(content_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Content with ID {content_id} not found")


# Enhanced ingestion endpoints for Sprint 2

@app.post("/content/ingest/enhanced", response_model=dict)
async def ingest_content_enhanced(
    request: ContentIngestionRequest,
    authenticated: str = Depends(get_authenticated_client_with_content_limits),
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Enhanced content ingestion with embeddings and vector storage.
    
    Args:
        request: Content ingestion request with text and metadata
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Detailed ingestion results including embedding and vector storage info
    """
    try:
        result = await pipeline.ingest_content(
            title=request.title,
            text=request.text,
            source=request.source,
            metadata=request.metadata,
            generate_embeddings=True
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Ingestion failed"))
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


from app.models import ContentSearchRequest, SearchCompareRequest

@app.post("/content/search", response_model=List[VectorSearchResult])
async def search_content(
    request: ContentSearchRequest,
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Search content using specified search mode via data ingestion pipeline.
    """
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    try:
        results = await pipeline.search_content(
            query=query,
            max_results=request.max_results,
            search_mode=request.search_mode
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.post("/content/search/compare", response_model=dict)
async def compare_search_modes(
    query: str,
    max_results: int = 5,
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Compare different search modes for the same query.
    
    Args:
        query: Search query text
        max_results: Maximum number of results per mode
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Results from all search modes for comparison
    """
    try:
        if not query.strip():
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Run all search modes
        modes = ["SEMANTIC_ONLY", "LEXICAL_ONLY", "HYBRID", "AUTO"]
        results = {}
        
        for mode in modes:
            try:
                search_results = await pipeline.search_content(
                    query=query,
                    max_results=max_results,
                    search_mode=mode
                )
                
                results[mode.lower()] = {
                    "count": len(search_results),
                    "results": [
                        {
                            "chunk_id": r.chunk_id,
                            "similarity_score": r.similarity_score,
                            "text_preview": r.chunk_text[:100] + "..." if len(r.chunk_text) > 100 else r.chunk_text
                        }
                        for r in search_results
                    ]
                }
            except Exception as e:
                results[mode.lower()] = {
                    "error": str(e),
                    "count": 0,
                    "results": []
                }
        
        return {
            "query": query,
            "max_results": max_results,
            "search_modes": results
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search comparison failed: {str(e)}")


@app.get("/retrieval/stats", response_model=dict)
async def get_retrieval_stats(
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Get detailed retrieval engine statistics.
    
    Args:
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Retrieval engine statistics and capabilities
    """
    try:
        stats = pipeline.get_pipeline_statistics()
        
        # Extract retrieval-specific stats
        retrieval_stats = {
            "vector_storage": stats.get("vector_storage", {}),
            "embedding_generation": stats.get("embedding_generation", {}),
            "pipeline_health": stats.get("pipeline_health", {})
        }
        
        # Add hybrid search availability
        vector_stats = stats.get("vector_storage", {})
        retrieval_stats["hybrid_search_available"] = vector_stats.get("hybrid_search_available", False)
        
        if "retrieval_engine" in vector_stats:
            retrieval_stats["retrieval_engine"] = vector_stats["retrieval_engine"]
        
        return retrieval_stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get retrieval stats: {str(e)}")


@app.get("/pipeline/stats", response_model=dict)
async def get_pipeline_stats(
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Get comprehensive pipeline statistics.
    
    Args:
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Pipeline statistics including content, embedding, and vector store info
    """
    return pipeline.get_pipeline_statistics()


@app.post("/pipeline/test", response_model=dict)
async def test_pipeline(
    test_text: str = None,
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Test the complete ingestion pipeline.
    
    Args:
        test_text: Optional test text (uses default if not provided)
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Test results
    """
    try:
        result = await pipeline.test_pipeline(test_text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline test failed: {str(e)}")


@app.post("/pipeline/save", response_model=dict)
async def save_pipeline_state(
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Save the current pipeline state to disk.
    
    Args:
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Save operation result
    """
    try:
        success = await pipeline.save_pipeline_state()
        return {
            "success": success,
            "message": "Pipeline state saved successfully" if success else "Failed to save pipeline state"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Save failed: {str(e)}")


@app.post("/pipeline/clear", response_model=dict)
async def clear_pipeline_data(
    pipeline: DataIngestionPipeline = Depends(get_data_ingestion_pipeline)
):
    """
    Clear all pipeline data (useful for testing).
    
    Args:
        pipeline: Data ingestion pipeline dependency
        
    Returns:
        dict: Clear operation result
    """
    try:
        pipeline.clear_pipeline_data()
        return {
            "success": True,
            "message": "Pipeline data cleared successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Clear failed: {str(e)}")



@app.post("/quiz/generate", response_model=QuizGenerationResponse)
async def generate_quiz(
    request: QuizGenerationRequest,
    authenticated: str = Depends(get_authenticated_client_with_quiz_limits),
    processor: ContentProcessor = Depends(get_content_processor),
    dspy_generator: DSPyQuizGenerator = Depends(get_dspy_quiz_generator)
):
    """
    Generate a quiz from ingested content.
    
    Args:
        request: Quiz generation request
        processor: Content processor dependency
        dspy_generator: DSPy quiz generator dependency
        
    Returns:
        QuizGenerationResponse: Response with quiz ID
    """
    try:
        start_time = time.time()
        quiz_id = str(uuid.uuid4())
        
        # Log quiz generation start
        quiz_monitor.log_quiz_generation_start(
            quiz_id, len(request.content_ids), request.num_questions
        )
        
        # Validate content IDs
        all_chunks = []
        for content_id in request.content_ids:
            try:
                chunks = processor.get_chunks(content_id)
                all_chunks.extend(chunks)
            except KeyError:
                raise HTTPException(status_code=404, detail=f"Content with ID {content_id} not found")
        
        if not all_chunks:
            raise HTTPException(status_code=400, detail="No content chunks available for quiz generation")
        
        # Generate questions using DSPy with timeout
        quiz_timeout = getattr(settings, 'quiz_generation_timeout', 300)
        questions = await with_quiz_timeout(
            dspy_generator.generate_quiz_questions_async(
                content_chunks=all_chunks,
                num_questions=request.num_questions,
                question_types=request.question_types,
                difficulty=request.difficulty_levels[0] if request.difficulty_levels else None
            ),
            timeout_seconds=quiz_timeout
        )
        
        # Create quiz
        quiz = Quiz(
            id=quiz_id,
            title=request.title or f"Generated Quiz {quiz_id[:8]}",
            description=request.description or f"Quiz generated from {len(request.content_ids)} content item(s)",
            questions=questions,
            source_content_ids=request.content_ids,
            created_at=datetime.now()
        )
        
        # Store quiz
        quiz_storage[quiz_id] = quiz
        
        # Log successful completion
        duration = time.time() - start_time
        quiz_monitor.log_quiz_generation_complete(quiz_id, duration, True)
        
        return QuizGenerationResponse(
            quiz_id=quiz_id,
            message=f"Successfully generated quiz with {len(questions)} questions"
        )
    
    except HTTPException:
        # Log error with proper duration calculation
        if 'start_time' in locals() and 'quiz_id' in locals():
            duration = time.time() - start_time
            quiz_monitor.log_quiz_generation_complete(quiz_id, duration, False, str(e))
        raise
    except Exception as e:
        # Log error with proper duration calculation
        if 'start_time' in locals() and 'quiz_id' in locals():
            duration = time.time() - start_time
            quiz_monitor.log_quiz_generation_complete(quiz_id, duration, False, str(e))
        raise HTTPException(status_code=500, detail=f"Error generating quiz: {str(e)}")


@app.get("/quiz", response_model=List[Quiz])
async def list_quizzes():
    """
    List all generated quizzes.
    
    Returns:
        List[Quiz]: List of all quizzes
    """
    return list(quiz_storage.values())


@app.get("/quiz/{quiz_id}", response_model=Quiz)
async def get_quiz(quiz_id: str):
    """
    Get a specific quiz by ID.
    
    Args:
        quiz_id: The quiz ID
        
    Returns:
        Quiz: The requested quiz
    """
    if quiz_id not in quiz_storage:
        raise HTTPException(status_code=404, detail=f"Quiz with ID {quiz_id} not found")
    
    return quiz_storage[quiz_id]


@app.get("/dspy/demo", response_model=dict)
async def dspy_demo(
    text: str = "Artificial intelligence is transforming many industries by automating complex tasks.",
    dspy_generator: DSPyQuizGenerator = Depends(get_dspy_quiz_generator)
):
    """
    Demonstrate DSPy functionality with a simple question generation.
    
    Args:
        text: Text to generate a question from
        dspy_generator: DSPy generator dependency
        
    Returns:
        dict: Generated question and answer
    """
    result = dspy_generator.generate_simple_question(text)
    
    return {
        "input_text": text,
        "generated_question": result.get("question"),
        "generated_answer": result.get("answer"),
        "reasoning": result.get("reasoning"),
        "dspy_configured": dspy_generator.is_available(),
        "error": result.get("error")
    }


# SPRINT 4: Question Generation Endpoints

@app.post("/generate/question", response_model=QuestionGenerationResponse)
async def generate_single_question(
    request: QuestionGenerationRequest,
    authenticated: str = Depends(get_authenticated_client_with_question_limits),
    qgen_module: QuestionGenerationModule = Depends(get_question_generation_module_dependency)
):
    """
    Generate a single question from a topic or query.
    
    Args:
        request: Question generation request
        qgen_module: Question generation module dependency
        
    Returns:
        QuestionGenerationResponse with the generated question
    """
    try:
        start_time = time.time()
        
        question = qgen_module.generate_one_question(
            topic_or_query=request.topic_or_query,
            question_type=request.question_type,
            difficulty=request.difficulty
        )
        
        processing_time = time.time() - start_time
        
        if not question:
            return QuestionGenerationResponse(
                error="Failed to generate question. Try a different topic or question type.",
                processing_time=processing_time
            )
            
        return QuestionGenerationResponse(
            question=question,
            processing_time=processing_time
        )
        
    except Exception as e:
        return QuestionGenerationResponse(
            error=f"Error generating question: {str(e)}",
            processing_time=0.0
        )


@app.post("/generate/questions", response_model=MultiQuestionGenerationResponse)
async def generate_multiple_questions(
    request: MultiQuestionGenerationRequest,
    authenticated: str = Depends(get_authenticated_client_with_question_limits),
    orchestrator: QuizOrchestrator = Depends(get_quiz_orchestrator_dependency)
):
    """
    Generate multiple questions from a topic or query.
    
    Args:
        request: Multi-question generation request
        orchestrator: Quiz orchestrator dependency
        
    Returns:
        MultiQuestionGenerationResponse with generated questions
    """
    try:
        start_time = time.time()
        
        questions, metadata = await orchestrator.generate_multiple_questions(
            topic_or_query=request.topic_or_query,
            num_questions=request.num_questions,
            question_types=request.question_types,
            difficulty=request.difficulty
        )
        
        processing_time = time.time() - start_time
        
        return MultiQuestionGenerationResponse(
            questions=questions,
            count=len(questions),
            processing_time=processing_time
        )
        
    except Exception as e:
        return MultiQuestionGenerationResponse(
            error=f"Error generating questions: {str(e)}",
            processing_time=time.time() - start_time if 'start_time' in locals() else 0.0
        )


@app.post("/generate/quick-quiz", response_model=QuickQuizGenerationResponse)
async def generate_quick_quiz(
    request: QuickQuizGenerationRequest,
    authenticated: str = Depends(get_authenticated_client_with_quiz_limits),
    orchestrator: QuizOrchestrator = Depends(get_quiz_orchestrator_dependency)
):
    """
    Generate a complete quiz directly from a topic.
    
    Args:
        request: Quick quiz generation request
        orchestrator: Quiz orchestrator dependency
        
    Returns:
        QuickQuizGenerationResponse with the generated quiz
    """
    try:
        start_time = time.time()
        
        quiz, metadata = await orchestrator.generate_quiz(
            title=request.title,
            description=request.description or f"Quiz about {request.topic_or_query}",
            topic_or_query=request.topic_or_query,
            num_questions=request.num_questions,
            question_types=request.question_types,
            difficulty=request.difficulty
        )
        
        # Store the generated quiz
        quiz_storage[quiz.id] = quiz
        
        processing_time = time.time() - start_time
        
        return QuickQuizGenerationResponse(
            quiz=quiz,
            processing_time=processing_time
        )
        
    except Exception as e:
        return QuickQuizGenerationResponse(
            error=f"Error generating quiz: {str(e)}",
            processing_time=time.time() - start_time if 'start_time' in locals() else 0.0
        )


@app.get("/generate/stats", response_model=Dict[str, Any])
async def get_generation_statistics(
    orchestrator: QuizOrchestrator = Depends(get_quiz_orchestrator_dependency)
):
    """
    Get statistics about the question generation process.
    
    Args:
        orchestrator: Quiz orchestrator dependency
        
    Returns:
        Dictionary containing generation statistics
    """
    return orchestrator.get_statistics()


# ============================================================================
# WORKFLOW MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/workflow/process-inputs", response_model=dict)
async def process_all_inputs(
    background_tasks: BackgroundTasks,
    authenticated: str = Depends(get_authenticated_client_with_content_limits),
    workflow: WorkflowOrchestrator = Depends(get_workflow_orchestrator)
):
    """
    Process all files in the input/ directory through the complete pipeline.
    
    This endpoint:
    1. Reads all .txt files from input/ directory
    2. Processes them through ingestion pipeline with embeddings
    3. Writes processed content to output/content/ directory
    4. Logs all operations with timestamps
    5. Creates processing summary
    
    Returns:
        dict: Processing results summary
    """
    try:
        enhanced_logger.info("Starting batch input processing workflow")
        
        # Start processing session
        session_id = await workflow.start_processing_session()
        
        # Process all input files
        results = await workflow.process_all_input_files()
        
        enhanced_logger.log_performance_metrics("batch_input_processing", {
            "session_id": session_id,
            "files_processed": len(results.get("processed_files", [])),
            "errors": len(results.get("errors", [])),
            "success_rate": len(results.get("processed_files", [])) / max(1, len(results.get("processed_files", [])) + len(results.get("errors", [])))
        })
        
        return {
            "success": True,
            "session_id": session_id,
            "message": f"Processed {len(results.get('processed_files', []))} input files",
            "results": results
        }
        
    except Exception as e:
        enhanced_logger.error("Batch input processing failed", e)
        raise HTTPException(status_code=500, detail=f"Workflow processing failed: {str(e)}")


@app.post("/workflow/generate-quiz", response_model=dict)
async def workflow_generate_quiz(
    content_query: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    authenticated: str = Depends(get_authenticated_client_with_quiz_limits),
    workflow: WorkflowOrchestrator = Depends(get_workflow_orchestrator)
):
    """
    Generate quiz from processed content using structured workflow.
    
    This endpoint:
    1. Searches processed content for relevant material
    2. Generates quiz questions using the quiz orchestrator
    3. Writes quiz to output/quizzes/ directory with structured naming
    4. Logs generation metrics and performance
    
    Args:
        content_query: Query to find relevant content
        num_questions: Number of questions to generate (default: 5)
        difficulty: Question difficulty level (default: medium)
        
    Returns:
        dict: Quiz generation results
    """
    try:
        enhanced_logger.log_api_request(
            "/workflow/generate-quiz", "POST",
            {"content_query": content_query, "num_questions": num_questions, "difficulty": difficulty}
        )
        
        # Generate quiz through workflow
        result = await workflow.generate_quiz_from_content(
            content_query=content_query,
            num_questions=num_questions,
            difficulty=difficulty
        )
        
        if result.get("success"):
            return {
                "success": True,
                "quiz_file": result["quiz_file"],
                "question_count": result["question_count"],
                "message": f"Generated {result['question_count']} questions for '{content_query}'",
                "metadata": result.get("metadata", {})
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Quiz generation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        enhanced_logger.error(f"Workflow quiz generation failed for query: {content_query}", e)
        raise HTTPException(status_code=500, detail=f"Quiz generation workflow failed: {str(e)}")


@app.post("/workflow/generate-questions", response_model=dict)
async def workflow_generate_questions(
    content_query: str,
    num_questions: int = 10,
    authenticated: str = Depends(get_authenticated_client_with_question_limits),
    workflow: WorkflowOrchestrator = Depends(get_workflow_orchestrator)
):
    """
    Generate individual questions from processed content using structured workflow.
    
    This endpoint:
    1. Searches processed content for relevant material
    2. Generates individual questions using the quiz orchestrator
    3. Writes questions to output/questions/ directory with structured naming
    4. Logs generation metrics and performance
    
    Args:
        content_query: Query to find relevant content
        num_questions: Number of questions to generate (default: 10)
        
    Returns:
        dict: Question generation results
    """
    try:
        enhanced_logger.log_api_request(
            "/workflow/generate-questions", "POST",
            {"content_query": content_query, "num_questions": num_questions}
        )
        
        # Generate questions through workflow
        result = await workflow.generate_questions_from_content(
            content_query=content_query,
            num_questions=num_questions
        )
        
        if result.get("success"):
            return {
                "success": True,
                "questions_file": result["questions_file"],
                "question_count": result["question_count"],
                "message": f"Generated {result['question_count']} questions for '{content_query}'",
                "metadata": result.get("metadata", {})
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Question generation failed"))
            
    except HTTPException:
        raise
    except Exception as e:
        enhanced_logger.error(f"Workflow question generation failed for query: {content_query}", e)
        raise HTTPException(status_code=500, detail=f"Question generation workflow failed: {str(e)}")


@app.get("/workflow/status", response_model=dict)
async def get_workflow_status(
    workflow: WorkflowOrchestrator = Depends(get_workflow_orchestrator)
):
    """
    Get current workflow status and directory information.
    
    Returns:
        dict: Workflow status including input files, output files, and session info
    """
    try:
        # Count files in input and output directories
        input_files = file_manager.find_input_files("*.txt")
        
        status = {
            "input_directory": str(file_manager.input_dir),
            "output_directory": str(file_manager.output_dir),
            "input_files_count": len(input_files),
            "input_files": [f.name for f in input_files],
            "current_session": workflow.current_session_id,
            "output_structure": workflow._collect_session_outputs() if workflow.current_session_id else {},
            "directories": {
                "logs": str(file_manager.logs_dir),
                "content": str(file_manager.content_dir),
                "quizzes": str(file_manager.quizzes_dir),
                "questions": str(file_manager.questions_dir)
            }
        }
        
        return status
        
    except Exception as e:
        enhanced_logger.error("Failed to get workflow status", e)
        raise HTTPException(status_code=500, detail=f"Failed to get workflow status: {str(e)}")


@app.post("/workflow/complete-session", response_model=dict)
async def complete_workflow_session(
    workflow: WorkflowOrchestrator = Depends(get_workflow_orchestrator)
):
    """
    Complete current workflow session and generate summary.
    
    Returns:
        dict: Session completion summary
    """
    try:
        summary = await workflow.complete_session()
        
        enhanced_logger.info("Workflow session completed", {
            "session_id": summary.get("session_id"),
            "duration_seconds": summary.get("duration_seconds")
        })
        
        return {
            "success": True,
            "message": "Workflow session completed successfully",
            "summary": summary
        }
        
    except Exception as e:
        enhanced_logger.error("Failed to complete workflow session", e)
        raise HTTPException(status_code=500, detail=f"Failed to complete session: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        workers=settings.api_workers,
        reload=True
    )
