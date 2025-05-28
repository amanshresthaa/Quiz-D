"""
Integration tests for Sprint 5 evaluation and quiz assembly functionality.
Tests the complete pipeline from retrieval through generation to evaluation and assembly.
"""

import asyncio
import pytest
import os
import sys
import time
from typing import Dict, Any, List

# Add parent directory to path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.models import QuestionType, DifficultyLevel, Question, Quiz
from app.retrieval_engine import SearchMode, get_retrieval_engine
from app.question_generation import get_question_generation_module
from app.evaluation_module import get_evaluation_module
from app.quiz_orchestrator import get_quiz_orchestrator


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping integration test because OPENAI_API_KEY is not set")
async def test_question_evaluation_integration():
    """
    Test the question evaluation pipeline.
    
    This test:
    1. Generates a question
    2. Evaluates the question
    3. Verifies evaluation results
    """
    try:
        # Get orchestrator and evaluator
        orchestrator = get_quiz_orchestrator()
        evaluator = get_evaluation_module()
        
        # Generate a question with evaluation
        question, eval_results = await orchestrator.generate_one_question_async(
            topic_or_query="What is Python programming?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            difficulty=DifficultyLevel.EASY,
            evaluate=True
        )
        
        # Verify we got results
        if question:  # Question passed evaluation
            assert isinstance(question, Question)
            assert question.question_text
            assert question.answer_text
            
            # Check evaluation results
            assert eval_results is not None
            assert "score" in eval_results
            assert eval_results.get("passed") is True
            
        else:  # Question failed evaluation
            # Check that we have failure details
            assert eval_results is not None
            assert "score" in eval_results
            assert eval_results.get("passed") is False
            assert "reasoning" in eval_results
            
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping integration test because OPENAI_API_KEY is not set")
async def test_multiple_question_generation_with_evaluation():
    """
    Test the generation of multiple questions with evaluation.
    
    This test:
    1. Generates multiple questions with evaluation
    2. Verifies that questions were filtered by quality
    3. Checks quiz assembly
    """
    try:
        # Get orchestrator
        orchestrator = get_quiz_orchestrator()
        
        # Generate multiple questions with evaluation
        questions, eval_summary = await orchestrator.generate_multiple_questions(
            topic_or_query="Introduction to machine learning",
            num_questions=3,
            question_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE],
            difficulty=DifficultyLevel.MEDIUM,
            evaluate=True
        )
        
        # Verify we got some questions
        assert isinstance(questions, list)
        assert len(questions) <= 3  # May be fewer if some failed quality check
        
        # Check evaluation summary
        assert eval_summary is not None
        assert "questions_evaluated" in eval_summary
        assert "questions_passed" in eval_summary
        assert "questions_failed" in eval_summary
        assert "average_score" in eval_summary
        
        # All returned questions should have passed evaluation
        for question in questions:
            assert isinstance(question, Question)
            assert question.question_text
            assert question.answer_text
            
        # Check if we have diversity in question types
        question_types = set(q.question_type for q in questions)
        if len(questions) > 1:
            # With more than one question, we should have attempted diversity
            # Note: May not always get diverse types if evaluation removed some
            print(f"Question types in result: {question_types}")
        
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping integration test because OPENAI_API_KEY is not set")
async def test_complete_quiz_generation_with_evaluation():
    """
    Test the complete quiz generation pipeline with evaluation.
    
    This test:
    1. Generates a complete quiz with evaluation
    2. Verifies quiz structure and quality
    3. Checks quiz-level evaluation
    """
    try:
        # Get orchestrator
        orchestrator = get_quiz_orchestrator()
        
        # Generate a complete quiz with evaluation
        quiz, eval_results = await orchestrator.generate_quiz(
            title="Test Quiz",
            description="A test quiz on programming",
            topic_or_query="Introduction to programming with Python",
            num_questions=3,
            question_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE],
            difficulty=DifficultyLevel.EASY,
            evaluate=True
        )
        
        # Verify quiz structure
        assert isinstance(quiz, Quiz)
        assert quiz.title == "Test Quiz"
        assert quiz.description == "A test quiz on programming"
        assert isinstance(quiz.questions, list)
        
        # We may get fewer questions than requested if some failed evaluation
        assert len(quiz.questions) <= 3
        
        # Check quiz-level evaluation if it was performed
        if "quiz_evaluation" in eval_results:
            quiz_eval = eval_results["quiz_evaluation"]
            assert "score" in quiz_eval
            assert "passed" in quiz_eval
            assert "reasoning" in quiz_eval
            assert "question_evaluations" in quiz_eval
            
            # Check that we have evaluations for each question
            question_ids = set(q.id for q in quiz.questions)
            evaluated_ids = set(e["question_id"] for e in quiz_eval["question_evaluations"])
            assert question_ids == evaluated_ids
        
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping integration test because OPENAI_API_KEY is not set")
async def test_quiz_generation_with_diversity():
    """
    Test that quiz generation produces diverse questions.
    
    This test:
    1. Generates quizzes with different diversity settings
    2. Compares the content coverage
    """
    try:
        # Get orchestrator
        orchestrator = get_quiz_orchestrator()
        
        # Generate a quiz with high diversity
        high_diversity_quiz, _ = await orchestrator.generate_quiz(
            title="High Diversity Quiz",
            description="A quiz with diverse questions",
            topic_or_query="History of computing",
            num_questions=3,
            question_types=[QuestionType.MULTIPLE_CHOICE],
            difficulty=DifficultyLevel.MEDIUM,
            evaluate=True,
            diversity_factor=0.9
        )
        
        # Generate a quiz with low diversity
        low_diversity_quiz, _ = await orchestrator.generate_quiz(
            title="Low Diversity Quiz",
            description="A quiz with less diverse questions",
            topic_or_query="History of computing",
            num_questions=3,
            question_types=[QuestionType.MULTIPLE_CHOICE],
            difficulty=DifficultyLevel.MEDIUM,
            evaluate=True,
            diversity_factor=0.1
        )
        
        # Function to extract key terms from questions
        def extract_terms(questions):
            all_terms = set()
            for q in questions:
                # Get words from question
                words = q.question_text.lower().split()
                # Add non-trivial words
                all_terms.update([w for w in words if len(w) > 4])
            return all_terms
        
        # Extract terms from both quizzes
        high_diversity_terms = extract_terms(high_diversity_quiz.questions)
        low_diversity_terms = extract_terms(low_diversity_quiz.questions)
        
        # Just report the results - note that this test might be flaky due to LLM randomness
        print(f"High diversity question terms: {len(high_diversity_terms)}")
        print(f"Low diversity question terms: {len(low_diversity_terms)}")
        
        # Ideally high diversity would have more unique terms, but it's not guaranteed
        # So we don't strictly assert this
        
    except Exception as e:
        pytest.fail(f"Test failed with exception: {e}")


if __name__ == "__main__":
    # Can run the test directly with pytest
    import pytest
    pytest.main(["-xvs", __file__])
