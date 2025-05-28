"""
Pydantic models for the Quiz application.
Defines the core data structures for content, questions, and quizzes.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class QuestionType(str, Enum):
    """Supported question types."""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"
    ESSAY = "essay"


class DifficultyLevel(str, Enum):
    """Question difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ContentItem(BaseModel):
    """
    Represents a piece of content that can be used for quiz generation.
    """
    id: Optional[str] = Field(default=None, description="Unique identifier for the content")
    title: Optional[str] = Field(default=None, description="Title of the content")
    text: str = Field(..., description="The actual text content")
    source: Optional[str] = Field(default=None, description="Source of the content (file path, URL, etc.)")
    content_type: Optional[str] = Field(default="text", description="Type of content (text, pdf, etc.)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    
    @field_validator('text')
    @classmethod
    def text_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Text content cannot be empty')
        return v.strip()


class ContentChunk(BaseModel):
    """
    Represents a chunk of processed content.
    """
    id: Optional[str] = Field(default=None, description="Unique identifier for the chunk")
    content_id: str = Field(..., description="ID of the parent content item")
    text: str = Field(..., description="The chunk text")
    chunk_index: int = Field(..., description="Index of this chunk within the parent content")
    start_position: Optional[int] = Field(default=None, description="Start position in original text")
    end_position: Optional[int] = Field(default=None, description="End position in original text")
    token_count: Optional[int] = Field(default=None, description="Number of tokens in this chunk")
    embedding: Optional[List[float]] = Field(default=None, description="Embedding vector for this chunk")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional chunk metadata")


class VectorSearchResult(BaseModel):
    """
    Represents a result from vector similarity search.
    """
    chunk_id: str = Field(..., description="ID of the chunk")
    content_id: str = Field(..., description="ID of the parent content")
    chunk_text: str = Field(..., description="Text content of the chunk")
    similarity_score: float = Field(..., description="Similarity score (0-1)")
    chunk_index: int = Field(..., description="Index of chunk within parent content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class EmbeddingRequest(BaseModel):
    """
    Request model for generating embeddings.
    """
    texts: List[str] = Field(..., description="List of texts to embed")
    model: Optional[str] = Field(default=None, description="Embedding model to use")


class EmbeddingResponse(BaseModel):
    """
    Response model for embedding generation.
    """
    embeddings: List[List[float]] = Field(..., description="Generated embeddings")
    model: str = Field(..., description="Model used for embedding")
    dimensions: int = Field(..., description="Embedding dimensions")
    token_usage: Optional[Dict[str, int]] = Field(default=None, description="Token usage information")


class Question(BaseModel):
    """
    Represents a quiz question.
    """
    id: Optional[str] = Field(default=None, description="Unique identifier for the question")
    question_text: str = Field(..., description="The question text")
    question_type: QuestionType = Field(..., description="Type of question")
    answer_text: str = Field(..., description="The correct answer")
    choices: Optional[List[str]] = Field(default=None, description="Multiple choice options")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM, description="Difficulty level")
    explanation: Optional[str] = Field(default=None, description="Explanation of the answer")
    source_content_id: Optional[str] = Field(default=None, description="ID of source content")
    tags: List[str] = Field(default_factory=list, description="Question tags/categories")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    
    @field_validator('question_text')
    @classmethod
    def question_text_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Question text cannot be empty')
        return v.strip()
    
    @field_validator('answer_text')
    @classmethod
    def answer_text_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Answer text cannot be empty')
        return v.strip()
    
    @field_validator('choices')
    @classmethod
    def validate_choices(cls, v, info):
        question_type = info.data.get('question_type') if info.data else None
        if question_type == QuestionType.MULTIPLE_CHOICE:
            if not v or len(v) < 2:
                raise ValueError('Multiple choice questions must have at least 2 choices')
        elif question_type == QuestionType.TRUE_FALSE:
            if v and len(v) != 2:
                raise ValueError('True/False questions must have exactly 2 choices')
        return v


class Quiz(BaseModel):
    """
    Represents a complete quiz.
    """
    id: Optional[str] = Field(default=None, description="Unique identifier for the quiz")
    title: str = Field(..., description="Quiz title")
    description: Optional[str] = Field(default=None, description="Quiz description")
    questions: List[Question] = Field(..., description="List of questions in the quiz")
    time_limit: Optional[int] = Field(default=None, description="Time limit in minutes")
    source_content_ids: List[str] = Field(default_factory=list, description="IDs of source content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional quiz metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    
    @field_validator('title')
    @classmethod
    def title_must_not_be_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Quiz title cannot be empty')
        return v.strip()
    
    @field_validator('questions')
    @classmethod
    def questions_must_not_be_empty(cls, v):
        if not v:
            raise ValueError('Quiz must have at least one question')
        return v


# Request/Response Models for API endpoints

class ContentIngestionRequest(BaseModel):
    """Request model for content ingestion."""
    title: Optional[str] = Field(default=None, description="Title for the content")
    text: str = Field(..., description="Text content to ingest")
    source: Optional[str] = Field(default=None, description="Source identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ContentIngestionResponse(BaseModel):
    """Response model for content ingestion."""
    content_id: str = Field(..., description="ID of the created content")
    chunks_created: int = Field(..., description="Number of chunks created")
    message: str = Field(..., description="Success message")

class ContentSearchRequest(BaseModel):
    """Request model for content search endpoint."""
    query: str = Field(..., description="Search query text")
    max_results: Optional[int] = Field(default=None, description="Maximum number of results to return")
    search_mode: str = Field(default="AUTO", description="Search mode: AUTO, SEMANTIC_ONLY, LEXICAL_ONLY, HYBRID")

class SearchCompareRequest(BaseModel):
    """Request model for comparing search modes endpoint."""
    query: str = Field(..., description="Search query text")
    max_results: Optional[int] = Field(default=5, description="Maximum number of results to return")


class QuizGenerationRequest(BaseModel):
    """Request model for quiz generation."""
    content_ids: List[str] = Field(..., description="IDs of content to use for quiz generation")
    num_questions: int = Field(default=5, ge=1, le=50, description="Number of questions to generate")
    question_types: List[QuestionType] = Field(default_factory=lambda: [QuestionType.MULTIPLE_CHOICE], description="Types of questions to generate")
    difficulty_levels: List[DifficultyLevel] = Field(default_factory=lambda: [DifficultyLevel.MEDIUM], description="Difficulty levels for questions")
    title: Optional[str] = Field(default=None, description="Quiz title")
    description: Optional[str] = Field(default=None, description="Quiz description")


class QuizGenerationResponse(BaseModel):
    """Response model for quiz generation."""
    quiz_id: str = Field(..., description="ID of the generated quiz")
    message: str = Field(..., description="Success message")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Application status")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    version: str = Field(default="1.0.0", description="Application version")
    config_valid: bool = Field(..., description="Whether configuration is valid")
