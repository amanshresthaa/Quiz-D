"""
Test suite for the Quiz application.
Covers content processing, model validation, and API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json

from app.main import app
from app.content_processor import ContentProcessor
from app.models import ContentItem, Question, Quiz, QuestionType, DifficultyLevel
from app.dspy_quiz_generator import DSPyQuizGenerator


class TestContentProcessor:
    """Test cases for ContentProcessor."""
    
    def setup_method(self):
        """Set up test method."""
        self.processor = ContentProcessor()
    
    def test_ingest_simple_content(self):
        """Test basic content ingestion."""
        text = "This is a test paragraph. It contains some text for testing."
        
        content = self.processor.ingest_content(
            title="Test Content",
            text=text,
            source="test"
        )
        
        assert content.id is not None
        assert content.title == "Test Content"
        assert content.text == text
        assert content.source == "test"
        assert isinstance(content.created_at, datetime)
        
        # Check that chunks were created
        chunks = self.processor.get_chunks(content.id)
        assert len(chunks) > 0
        assert chunks[0].content_id == content.id
    
    def test_ingest_empty_text_raises_error(self):
        """Test that empty text raises ValueError."""
        with pytest.raises(ValueError, match="Text content cannot be empty"):
            self.processor.ingest_content(text="")
    
    def test_chunk_large_content(self):
        """Test chunking of large content."""
        # Create content larger than default chunk size
        text = "This is a test sentence. " * 100  # About 2500 characters
        
        content = self.processor.ingest_content(text=text)
        chunks = self.processor.get_chunks(content.id)
        
        assert len(chunks) > 1  # Should be split into multiple chunks
        
        # Verify chunks contain expected content
        combined_text = " ".join([chunk.text for chunk in chunks])
        assert "This is a test sentence." in combined_text
    
    def test_content_not_found(self):
        """Test retrieving non-existent content."""
        with pytest.raises(KeyError):
            self.processor.get_content("non-existent-id")
    
    def test_content_statistics(self):
        """Test content statistics calculation."""
        # Initially empty
        stats = self.processor.get_content_statistics()
        assert stats["total_content_items"] == 0
        assert stats["total_chunks"] == 0
        
        # Add some content
        self.processor.ingest_content(text="Test content 1")
        self.processor.ingest_content(text="Test content 2")
        
        stats = self.processor.get_content_statistics()
        assert stats["total_content_items"] == 2
        assert stats["total_chunks"] > 0


class TestModels:
    """Test cases for Pydantic models."""
    
    def test_content_item_validation(self):
        """Test ContentItem validation."""
        # Valid content item
        content = ContentItem(text="Valid text content")
        assert content.text == "Valid text content"
        assert content.content_type == "text"  # default value
        
        # Invalid empty text
        with pytest.raises(ValueError):
            ContentItem(text="")
    
    def test_question_validation(self):
        """Test Question validation."""
        # Valid multiple choice question
        question = Question(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            answer_text="4",
            choices=["2", "3", "4", "5"]
        )
        assert question.question_text == "What is 2 + 2?"
        assert question.choices == ["2", "3", "4", "5"]
        
        # Invalid multiple choice (not enough choices)
        with pytest.raises(ValueError):
            Question(
                question_text="Test?",
                question_type=QuestionType.MULTIPLE_CHOICE,
                answer_text="A",
                choices=["A"]  # Only one choice
            )
    
    def test_quiz_validation(self):
        """Test Quiz validation."""
        question = Question(
            question_text="Test question?",
            question_type=QuestionType.SHORT_ANSWER,
            answer_text="Test answer"
        )
        
        # Valid quiz
        quiz = Quiz(
            title="Test Quiz",
            questions=[question]
        )
        assert quiz.title == "Test Quiz"
        assert len(quiz.questions) == 1
        
        # Invalid empty quiz
        with pytest.raises(ValueError):
            Quiz(title="Empty Quiz", questions=[])


class TestDSPyQuizGenerator:
    """Test cases for DSPy quiz generator."""
    
    def setup_method(self):
        """Set up test method."""
        self.generator = DSPyQuizGenerator()
    
    def test_simple_question_generation(self):
        """Test simple question generation (works with or without API key)."""
        text = "Python is a programming language."
        result = self.generator.generate_simple_question(text)
        
        assert "question" in result
        assert "answer" in result
        assert isinstance(result["question"], str)
        assert isinstance(result["answer"], str)
    
    def test_quiz_generation_fallback(self):
        """Test quiz generation fallback when DSPy is not configured."""
        from app.models import ContentChunk
        
        # Create sample chunks
        chunks = [
            ContentChunk(
                content_id="test-content",
                text="Test content for quiz generation.",
                chunk_index=0
            )
        ]
        
        questions = self.generator.generate_quiz_questions(
            content_chunks=chunks,
            num_questions=3,
            question_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE]
        )
        
        assert len(questions) == 3
        assert all(isinstance(q, Question) for q in questions)
        assert questions[0].question_type == QuestionType.MULTIPLE_CHOICE
        assert questions[1].question_type == QuestionType.TRUE_FALSE


class TestAPI:
    """Test cases for FastAPI endpoints."""
    
    def setup_method(self):
        """Set up test method."""
        self.client = TestClient(app)
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_ping_endpoint(self):
        """Test ping endpoint."""
        response = self.client.get("/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "pong"
        assert "timestamp" in data
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
    
    def test_content_ingestion(self):
        """Test content ingestion endpoint."""
        content_data = {
            "title": "Test Content",
            "text": "This is test content for the quiz application.",
            "source": "test"
        }
        
        response = self.client.post("/content/ingest", json=content_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "content_id" in data
        assert data["chunks_created"] > 0
        assert "Successfully ingested" in data["message"]
    
    def test_content_ingestion_empty_text(self):
        """Test content ingestion with empty text."""
        content_data = {
            "text": ""
        }
        
        response = self.client.post("/content/ingest", json=content_data)
        assert response.status_code == 400
    
    def test_list_content(self):
        """Test listing content."""
        # First ingest some content
        content_data = {
            "text": "Test content for listing."
        }
        self.client.post("/content/ingest", json=content_data)
        
        # Then list content
        response = self.client.get("/content")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_content_stats(self):
        """Test getting content statistics."""
        response = self.client.get("/content/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "total_content_items" in data
        assert "total_chunks" in data
    
    def test_quiz_generation(self):
        """Test quiz generation endpoint."""
        # First ingest content
        content_data = {
            "text": "This is test content for quiz generation. It should contain enough information to generate questions."
        }
        ingest_response = self.client.post("/content/ingest", json=content_data)
        content_id = ingest_response.json()["content_id"]
        
        # Then generate quiz
        quiz_data = {
            "content_ids": [content_id],
            "num_questions": 2,
            "question_types": ["multiple_choice"],
            "title": "Test Quiz"
        }
        
        response = self.client.post("/quiz/generate", json=quiz_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "quiz_id" in data
        assert "Successfully generated" in data["message"]
    
    def test_quiz_generation_invalid_content(self):
        """Test quiz generation with invalid content ID."""
        quiz_data = {
            "content_ids": ["non-existent-id"],
            "num_questions": 2
        }
        
        response = self.client.post("/quiz/generate", json=quiz_data)
        assert response.status_code == 404
    
    def test_get_quiz(self):
        """Test getting a specific quiz."""
        # First create a quiz
        content_data = {"text": "Content for quiz retrieval test."}
        ingest_response = self.client.post("/content/ingest", json=content_data)
        content_id = ingest_response.json()["content_id"]
        
        quiz_data = {
            "content_ids": [content_id],
            "num_questions": 1
        }
        quiz_response = self.client.post("/quiz/generate", json=quiz_data)
        quiz_id = quiz_response.json()["quiz_id"]
        
        # Then retrieve the quiz
        response = self.client.get(f"/quiz/{quiz_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == quiz_id
        assert "questions" in data
        assert len(data["questions"]) == 1
    
    def test_get_nonexistent_quiz(self):
        """Test getting a non-existent quiz."""
        response = self.client.get("/quiz/non-existent-id")
        assert response.status_code == 404
    
    def test_dspy_demo(self):
        """Test DSPy demonstration endpoint."""
        response = self.client.get("/dspy/demo")
        assert response.status_code == 200
        
        data = response.json()
        assert "input_text" in data
        assert "generated_question" in data
        assert "generated_answer" in data
        assert "dspy_configured" in data
    
    def test_dspy_demo_custom_text(self):
        """Test DSPy demo with custom text."""
        custom_text = "Machine learning is a subset of artificial intelligence."
        response = self.client.get(f"/dspy/demo?text={custom_text}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["input_text"] == custom_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
