"""
Integration tests for Sprint 4 question generation functionality.
Tests the end-to-end pipeline from retrieval to quiz generation.
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
from app.quiz_orchestrator import get_quiz_orchestrator


@pytest.mark.asyncio
@pytest.mark.skipif(os.environ.get("OPENAI_API_KEY") is None, 
                   reason="Skipping integration test because OPENAI_API_KEY is not set")
async def test_quiz_orchestrator_end_to_end():
    """
    Test the complete quiz generation pipeline.
    
    This test:
    1. Sets up the retrieval engine
    2. Configures the question generation module
    3. Uses the quiz orchestrator to generate questions
    4. Creates a full quiz
    """
    try:
        # Get orchestrator
        orchestrator = get_quiz_orchestrator()
        
        # Generate one question first as a simple test
        question = await orchestrator.generate_one_question_async(
            topic_or_query="What is Python programming?",
            question_type=QuestionType.MULTIPLE_CHOICE,
            difficulty=DifficultyLevel.EASY
        )
        
        # Verify the question
        assert question is not None
        assert isinstance(question, Question)
        assert question.question_text
        assert question.answer_text
        assert isinstance(question.choices, list)
        
        # Now test generating multiple questions
        questions = await orchestrator.generate_multiple_questions(
            topic_or_query="Explain the features of Python",
            num_questions=3,
            question_types=[
                QuestionType.MULTIPLE_CHOICE,
                QuestionType.TRUE_FALSE,
                QuestionType.SHORT_ANSWER
            ],
            difficulty=DifficultyLevel.MEDIUM
        )
        
        # Verify the questions
        assert len(questions) > 0  # We might not get all 3, but should get at least 1
        assert all(isinstance(q, Question) for q in questions)
        
        # Test generating a complete quiz
        quiz = await orchestrator.generate_quiz(
            title="Python Basics",
            description="Test your knowledge of Python programming",
            topic_or_query="Python programming language basics",
            num_questions=2,
            question_types=[QuestionType.MULTIPLE_CHOICE],
            difficulty=DifficultyLevel.EASY
        )
        
        # Verify the quiz
        assert quiz is not None
        assert isinstance(quiz, Quiz)
        assert quiz.title == "Python Basics"
        assert len(quiz.questions) > 0
        
        # Get and verify statistics
        stats = orchestrator.get_statistics()
        assert stats["quizzes_generated"] >= 1
        assert stats["total_questions"] >= 1
        
        print(f"Integration test completed successfully. Generated {len(quiz.questions)} questions.")
        
    except Exception as e:
        pytest.fail(f"Integration test failed: {str(e)}")


@pytest.mark.asyncio
async def test_multiple_question_types():
    """
    Test generating questions of different types.
    """
    orchestrator = get_quiz_orchestrator()
    
    # Dictionary to track generated question types
    generated_types = {
        QuestionType.MULTIPLE_CHOICE: False,
        QuestionType.TRUE_FALSE: False,
        QuestionType.SHORT_ANSWER: False,
        QuestionType.ESSAY: False
    }
    
    # Generate sample questions of each type
    for question_type in [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE,
                         QuestionType.SHORT_ANSWER, QuestionType.ESSAY]:
        question = orchestrator.question_generator.generate_question(
            context="Sample context for testing different question types. This content is about DSPy, the framework for programming language models.",
            question_type=question_type,
            difficulty=DifficultyLevel.MEDIUM
        )
        
        # Mark type as generated
        if question:
            generated_types[question_type] = True
            
            # Basic validation based on question type
            if question_type == QuestionType.MULTIPLE_CHOICE:
                assert "choices" in question
                assert len(question["choices"]) >= 2
                
            elif question_type == QuestionType.TRUE_FALSE:
                assert "choices" in question
                assert len(question["choices"]) == 2
                assert question["choices"][0] in ["True", "False"]
                assert question["choices"][1] in ["True", "False"]
                
            elif question_type == QuestionType.ESSAY:
                assert "\n-" in question["answer_text"]  # Should have bullet points
    
    # Ensure we have at least one sample for each type
    assert all(generated_types.values()), "Failed to generate all question types"


@pytest.fixture
def run_in_event_loop(request):
    """Fixture to provide a running event loop"""
    loop = asyncio.get_event_loop()
    yield loop
    

def write_integration_results(orchestrator):
    """Write integration test results to a file."""
    stats = orchestrator.get_statistics()
    
    with open("sprint4_integration_results.md", "w") as f:
        f.write("# Sprint 4 Integration Test Results\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("## Quiz Generation Statistics\n\n")
        f.write(f"- **Quizzes Generated:** {stats['quizzes_generated']}\n")
        f.write(f"- **Total Questions:** {stats['total_questions']}\n")
        f.write(f"- **Failed Questions:** {stats['failed_questions']}\n")
        f.write(f"- **Average Generation Time:** {stats.get('average_generation_time', 0):.2f}s\n\n")
        
        f.write("### Question Generator Statistics\n\n")
        if "question_generator" in stats:
            qg_stats = stats["question_generator"]
            f.write(f"- **Total Questions Generated:** {qg_stats['total_questions_generated']}\n")
            f.write(f"- **Successful Generations:** {qg_stats['successful_generations']}\n")
            f.write(f"- **Failed Generations:** {qg_stats['failed_generations']}\n")
            f.write(f"- **Quality Checks Performed:** {qg_stats['quality_checks_performed']}\n")
            
            if qg_stats['quality_checks_performed'] > 0:
                f.write(f"- **Average Quality Score:** {qg_stats['average_quality_score']:.2f}\n")
            
            f.write("\n**Questions by Type:**\n\n")
            for qtype, count in qg_stats['questions_by_type'].items():
                f.write(f"- **{qtype.title()}:** {count}\n")
        
        f.write("\n## Integration Status: ✅ PASSED\n")


def test_integration_results():
    """
    Run a simplified integration test and write results to a file.
    This can be run manually to generate a report.
    """
    # Get orchestrator
    orchestrator = get_quiz_orchestrator()
    
    # Run in event loop
    loop = asyncio.get_event_loop()
    
    # Generate a test question synchronously
    question_module = orchestrator.question_generator
    question = question_module.generate_question(
        context="DSPy is a framework for programming language models.",
        question_type=QuestionType.MULTIPLE_CHOICE
    )
    
    assert question is not None
    
    # Write results
    write_integration_results(orchestrator)
    
    print("Integration test results written to sprint4_integration_results.md")


if __name__ == "__main__":
    # Run tests manually
    pytest.main(["-xvs", __file__])
