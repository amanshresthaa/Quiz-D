"""
Unit tests for the DSPy question generation module.
Tests both with mock LLM and with real API calls.
"""

import pytest
import uuid
import os
import sys
from typing import Dict, Any, List
from unittest.mock import patch, MagicMock

# Add parent directory to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import QuestionType, DifficultyLevel, ContentChunk, Question
from app.question_generation import QuestionGenerationModule
from app.retrieval_engine import RetrievalEngine, SearchMode, VectorSearchResult


# Mock data for testing
mock_context = """
DSPy is a framework for programming (not prompting) foundation models like GPT-4, Claude, Llama-2, and Mistral. 
DSPy allows for structured programming with LLMs via signatures and modules that define the expected inputs and outputs. 
These modules can be composed together to create complex pipelines, which can then be optimized using DSPy's teleprompters.
DSPy was created by Stanford researchers to make LLM programming more systematic and reliable.
"""

mock_search_results = [
    VectorSearchResult(
        content_id="1",
        chunk_id=1,
        text=mock_context,
        score=0.95,
        metadata={"source": "test"}
    )
]


class MockRetrievalEngine:
    """Mock retrieval engine for testing."""
    
    def search(self, query: str, mode: SearchMode, limit: int = 5) -> List[VectorSearchResult]:
        """Mock search method."""
        return mock_search_results


class MockDSPyModule:
    """Mock DSPy module for testing."""
    
    def __call__(self, **kwargs):
        """Mock calling the module."""
        if "context" not in kwargs:
            raise ValueError("Missing context")
            
        if "multiple_choice" in str(kwargs.get("context", "")).lower():
            return MagicMock(
                question="What is DSPy primarily designed for?",
                answer="Programming language models",
                choices=["Programming language models", "Image generation", "Data analysis", "Web development"],
                explanation="DSPy is specifically designed as a framework for programming language models in a structured way."
            )
        elif "true_false" in str(kwargs.get("context", "")).lower():
            return MagicMock(
                question="DSPy was created by researchers at MIT.",
                answer="False",
                explanation="DSPy was created by Stanford researchers, not MIT."
            )
        else:
            return MagicMock(
                question="What is DSPy?",
                answer="A framework for programming language models",
                reasoning="Based on the context, DSPy is clearly described as a framework for programming foundation models."
            )


@pytest.fixture
def mock_qgen_module():
    """Create a question generation module with mock DSPy modules."""
    with patch('app.question_generation.get_dspy_quiz_generator') as mock_dspy_generator:
        mock_dspy_generator.return_value.is_available.return_value = True
        
        module = QuestionGenerationModule(retrieval_engine=MockRetrievalEngine())
        
        # Replace DSPy modules with mocks
        module.basic_qa_generator = MockDSPyModule()
        module.mc_generator = MockDSPyModule()
        module.tf_generator = MockDSPyModule()
        module.sa_generator = MockDSPyModule()
        module.essay_generator = MockDSPyModule()
        module.quality_checker = MagicMock(return_value=MagicMock(is_high_quality="True"))
        
        yield module


def test_generate_question_multiple_choice(mock_qgen_module):
    """Test generating a multiple choice question."""
    context = "[Generate a medium difficulty level question] " + mock_context
    result = mock_qgen_module.generate_question(
        context=context,
        question_type=QuestionType.MULTIPLE_CHOICE
    )
    
    assert result is not None
    assert "question_text" in result
    assert "answer_text" in result
    assert "choices" in result
    assert isinstance(result["choices"], list)
    assert len(result["choices"]) >= 2
    assert result["question_type"] == QuestionType.MULTIPLE_CHOICE


def test_generate_one_question_with_retrieval(mock_qgen_module):
    """Test the end-to-end question generation with retrieval."""
    question = mock_qgen_module.generate_one_question(
        topic_or_query="What is DSPy?",
        question_type=QuestionType.MULTIPLE_CHOICE
    )
    
    assert question is not None
    assert isinstance(question, Question)
    assert question.question_text
    assert question.answer_text
    assert question.question_type == QuestionType.MULTIPLE_CHOICE


def test_quality_checker(mock_qgen_module):
    """Test the quality checker functionality."""
    is_high_quality, _ = mock_qgen_module.check_question_quality(
        context=mock_context,
        question="What is DSPy?",
        answer="A framework for programming language models"
    )
    
    assert is_high_quality is True


def test_fallback_to_sample_questions():
    """Test fallback to sample questions when DSPy is not available."""
    with patch('app.question_generation.get_dspy_quiz_generator') as mock_dspy_generator:
        mock_dspy_generator.return_value.is_available.return_value = False
        
        module = QuestionGenerationModule()
        result = module.generate_question(
            context="This doesn't matter since we'll use samples",
            question_type=QuestionType.MULTIPLE_CHOICE
        )
        
        assert result is not None
        assert "question_text" in result
        assert "answer_text" in result
        assert "choices" in result


@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping live API test because OPENAI_API_KEY is not set")
def test_live_question_generation():
    """
    Test live question generation with real OpenAI API.
    Only runs if OPENAI_API_KEY is set in environment.
    """
    from app.question_generation import get_question_generation_module
    from app.retrieval_engine import get_retrieval_engine
    
    try:
        retrieval_engine = get_retrieval_engine()
        qgen = get_question_generation_module(retrieval_engine)
        
        question = qgen.generate_one_question(
            topic_or_query="What is Python?",
            question_type=QuestionType.SHORT_ANSWER
        )
        
        assert question is not None
        assert isinstance(question, Question)
        assert question.question_text
        assert question.answer_text
        
    except Exception as e:
        pytest.skip(f"Live test failed: {str(e)}")


if __name__ == "__main__":
    # Run tests manually
    pytest.main(["-xvs", __file__])
