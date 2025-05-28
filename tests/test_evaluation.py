"""
Test suite for the question evaluation module.
Tests both heuristic and LLM-based evaluation methods.
"""

import pytest
import os
import sys
from unittest.mock import patch, MagicMock

# Add parent directory to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import Question, QuestionType, DifficultyLevel
from app.evaluation_module import QuestionEvaluationModule


class MockLLMEvaluator:
    """Mock LLM evaluator for testing."""
    
    def __call__(self, **kwargs):
        """Mock calling the LLM evaluator."""
        if "context" not in kwargs or "question" not in kwargs:
            raise ValueError("Missing required inputs")
            
        # Check if answer is in context (simple test)
        context = kwargs.get("context", "").lower()
        answer = kwargs.get("answer", "").lower()
        
        if answer in context:
            # Good evaluation
            return MagicMock(
                answerable="True",
                correct="True",
                score="0.9",
                reasoning="The answer is clearly stated in the context.",
                suggested_improvement="No improvements needed."
            )
        else:
            # Bad evaluation
            return MagicMock(
                answerable="False",
                correct="False",
                score="0.3",
                reasoning="The answer is not supported by the provided context.",
                suggested_improvement="The question should be revised to match information in the context."
            )


@pytest.fixture
def mock_evaluation_module():
    """Create a question evaluation module with mock LLM evaluator."""
    with patch('app.evaluation_module.get_dspy_quiz_generator') as mock_dspy_gen:
        mock_dspy_gen.return_value.is_available.return_value = True
        
        module = QuestionEvaluationModule()
        module.evaluator = MockLLMEvaluator()
        
        yield module


def test_heuristic_evaluation_multiple_choice(mock_evaluation_module):
    """Test heuristic evaluation of multiple choice questions."""
    # Create test question where answer is in context
    context = "Python is a high-level programming language with simple, easy-to-learn syntax."
    question = Question(
        id="test1",
        question_text="What is Python?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        answer_text="a high-level programming language",
        choices=["a high-level programming language", "a database system", "an operating system", "a web browser"]
    )
    
    # Evaluate
    passed, score, reasoning = mock_evaluation_module.evaluate_question_heuristic(context, question)
    
    # Check results
    assert passed is True
    assert score > 0.8
    assert "appears verbatim" in reasoning.lower()
    
    # Create test question where answer is not in context
    question2 = Question(
        id="test2",
        question_text="What is Python?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        answer_text="a snake species",
        choices=["a high-level programming language", "a database system", "an operating system", "a snake species"]
    )
    
    # Evaluate
    passed2, score2, reasoning2 = mock_evaluation_module.evaluate_question_heuristic(context, question2)
    
    # Check results
    assert passed2 is False
    assert score2 < 0.6


def test_heuristic_evaluation_true_false(mock_evaluation_module):
    """Test heuristic evaluation of true/false questions."""
    context = "The Earth orbits the Sun in an elliptical pattern. It takes approximately 365.25 days to complete one orbit."
    
    # Create test question with relevant terms in context
    question = Question(
        id="test3",
        question_text="The Earth orbits the Sun in an elliptical pattern.",
        question_type=QuestionType.TRUE_FALSE,
        answer_text="True",
        choices=["True", "False"]
    )
    
    # Evaluate
    passed, score, reasoning = mock_evaluation_module.evaluate_question_heuristic(context, question)
    
    # Check results
    assert passed is True
    assert score >= 0.7
    assert "key terms" in reasoning.lower()
    
    # Create test question with few terms in context
    question2 = Question(
        id="test4",
        question_text="The Earth orbits the Moon in a circular pattern.",
        question_type=QuestionType.TRUE_FALSE,
        answer_text="False",
        choices=["True", "False"]
    )
    
    # Evaluate
    passed2, score2, reasoning2 = mock_evaluation_module.evaluate_question_heuristic(context, question2)
    
    # Check results - might still pass if enough key terms match
    assert "key terms" in reasoning2.lower()


def test_llm_evaluation(mock_evaluation_module):
    """Test LLM-based evaluation."""
    # Create test context and question where answer is in context
    context = "DSPy is a framework for programming language models in a structured way."
    question = Question(
        id="test5",
        question_text="What is DSPy?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        answer_text="A framework for programming language models",
        choices=["A framework for programming language models", "A database system", "A Python IDE", "A web framework"]
    )
    
    # Evaluate using LLM
    passed, score, reasoning, details = mock_evaluation_module.evaluate_question_llm(context, question)
    
    # Check results
    assert passed is True
    assert score > 0.7
    assert details is not None
    assert details.get("answerable") is True
    assert details.get("correct") is True
    
    # Test with answer not in context
    question2 = Question(
        id="test6",
        question_text="What is DSPy?",
        question_type=QuestionType.MULTIPLE_CHOICE,
        answer_text="A Python graphics library",
        choices=["A framework for programming language models", "A database system", "A Python IDE", "A Python graphics library"]
    )
    
    # Evaluate using LLM
    passed2, score2, reasoning2, details2 = mock_evaluation_module.evaluate_question_llm(context, question2)
    
    # Check results
    assert passed2 is False
    assert score2 < 0.5
    assert details2 is not None
    assert details2.get("suggested_improvement") is not None


def test_combined_evaluation(mock_evaluation_module):
    """Test the combined evaluation approach."""
    context = "Machine learning is a branch of artificial intelligence that involves training models on data."
    question = Question(
        id="test7",
        question_text="What is machine learning?",
        question_type=QuestionType.SHORT_ANSWER,
        answer_text="A branch of artificial intelligence"
    )
    
    # Test with LLM first
    passed, score, reasoning, details = mock_evaluation_module.evaluate_question(
        context, question, use_llm=True
    )
    
    assert passed is True
    assert score > 0.7
    assert details is not None
    
    # Test fallback to heuristic
    with patch.object(mock_evaluation_module, 'evaluate_question_llm', side_effect=Exception("LLM error")):
        with patch.object(mock_evaluation_module, 'evaluate_question_heuristic') as mock_heuristic:
            # Set up the mock to return expected values
            mock_heuristic.return_value = (True, 0.8, "Heuristic reasoning")
            
            passed2, score2, reasoning2, details2 = mock_evaluation_module.evaluate_question(
                context, question, use_llm=True
            )
            
            assert mock_heuristic.called
            assert details2 is not None
            assert "error" in details2
            assert passed2 is True
            assert score2 == 0.8
            assert reasoning2 == "Heuristic reasoning"
    
    # Test direct heuristic
    passed3, score3, reasoning3, details3 = mock_evaluation_module.evaluate_question(
        context, question, use_llm=False
    )
    
    assert details3 is None  # Heuristic doesn't provide details


@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping integration test because OPENAI_API_KEY is not set")
def test_real_evaluator_integration():
    """Test the evaluator with real LLM calls if API key is available."""
    from app.evaluation_module import get_evaluation_module
    
    # Only run if we have an API key
    evaluator = get_evaluation_module()
    
    # Create a simple question and context
    context = "Python is a high-level, interpreted, general-purpose programming language. Its design philosophy emphasizes code readability with the use of significant indentation. Python is dynamically-typed and garbage-collected."
    question = Question(
        id="integration1",
        question_text="What type of programming language is Python?",
        question_type=QuestionType.SHORT_ANSWER,
        answer_text="high-level, interpreted, general-purpose"
    )
    
    # Evaluate with real LLM if available
    if evaluator._dspy_generator.is_available():
        passed, score, reasoning, details = evaluator.evaluate_question(context, question)
        
        # Just check that we get results without errors
        assert isinstance(passed, bool)
        assert isinstance(score, float)
        assert reasoning is not None
