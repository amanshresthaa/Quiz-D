"""
Tests for error handling and robustness in the quiz orchestrator.
These tests verify the orchestrator's behavior under various failure conditions.
"""

import pytest
import asyncio
from unittest import mock
from typing import List, Dict, Any, Optional

from app.models import QuestionType, DifficultyLevel, Question
from app.quiz_orchestrator import QuizOrchestrator


class TestQuizOrchestratorErrorHandling:
    """Test error handling capabilities of the QuizOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a QuizOrchestrator instance for testing."""
        return QuizOrchestrator()

    @pytest.mark.asyncio
    async def test_generate_one_question_retries(self, orchestrator):
        """Test that question generation retries on failure."""
        # Mock the question_generator's generate_one_question method to fail once then succeed
        original_method = orchestrator.question_generator.generate_one_question
        
        call_count = 0
        
        def mock_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First call fails
                return None
            # Second call succeeds
            return original_method(*args, **kwargs)
        
        orchestrator.question_generator.generate_one_question = mock_generate
        
        # Call the method with retry logic
        question, metrics = await orchestrator.generate_one_question_async(
            topic_or_query="Test topic",
            evaluate=False,
            max_retries=2
        )
        
        # Verify that we retried and eventually succeeded
        assert call_count == 2
        assert question is not None
        
        # Restore the original method
        orchestrator.question_generator.generate_one_question = original_method

    @pytest.mark.asyncio
    async def test_generate_one_question_with_timeout(self, orchestrator):
        """Test that question generation handles timeouts gracefully."""
        # Mock a question generation that takes too long
        async def slow_task(*args, **kwargs):
            await asyncio.sleep(2)  # Simulate long-running task
            return None, {}
            
        # Create a task with a short timeout
        with mock.patch.object(orchestrator, 'generate_one_question_async', side_effect=slow_task):
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(
                    orchestrator.generate_one_question_async("Test topic"),
                    timeout=0.5
                )

    @pytest.mark.asyncio
    async def test_generate_multiple_questions_partial_failure(self, orchestrator):
        """Test that multiple questions generation works even if some questions fail."""
        # Mock question generation to succeed for odd indices and fail for even
        original_method = orchestrator.generate_one_question_async
        
        async def mock_generate(*args, **kwargs):
            # Get the position of this call using task counter
            task_counter = len(mock_results)
            if task_counter % 2 == 0:
                # Even calls succeed
                result = await original_method(*args, **kwargs)
                mock_results.append(True)
                return result
            else:
                # Odd calls fail
                mock_results.append(False)
                return None, {"error": "Mock failure"}
        
        mock_results = []
        
        # Patch the method temporarily
        with mock.patch.object(orchestrator, 'generate_one_question_async', side_effect=mock_generate):
            # Request 4 questions, should get 2 successes and 2 failures
            questions, metrics = await orchestrator.generate_multiple_questions(
                topic_or_query="Test topic",
                num_questions=4,
                evaluate=False
            )
            
            # Verify that we got some questions despite failures
            assert len(questions) > 0
            assert len(questions) < 4  # Should be less than requested due to failures
            assert metrics["questions_failed"] > 0
            
    @pytest.mark.asyncio
    async def test_generate_quiz_handles_total_failure(self, orchestrator):
        """Test that quiz generation handles complete failure gracefully."""
        # Mock generate_multiple_questions to fail completely
        async def mock_failure(*args, **kwargs):
            return [], {"error": "Complete failure"}
            
        # Patch the method temporarily
        with mock.patch.object(orchestrator, 'generate_multiple_questions', side_effect=mock_failure):
            # Try to generate a quiz
            quiz, metrics = await orchestrator.generate_quiz(
                title="Test Quiz",
                description="Test Description",
                topic_or_query="Test topic",
                num_questions=3
            )
            
            # Verify that we got an empty quiz with error info
            assert len(quiz.questions) == 0
            assert "error" in metrics or "warning" in metrics

    @pytest.mark.asyncio
    async def test_generate_quiz_with_timeout(self, orchestrator):
        """Test that quiz generation handles timeouts gracefully."""
        # Mock a quiz generation that takes too long
        async def slow_quiz(*args, **kwargs):
            await asyncio.sleep(5)  # Simulate very long-running task
            return [], {}
            
        # Create a quiz with a short timeout
        with mock.patch.object(orchestrator, 'generate_multiple_questions', side_effect=slow_quiz):
            # Should not raise exception, but return empty quiz with error info
            quiz, metrics = await orchestrator.generate_quiz(
                title="Test Quiz",
                description="Test Description",
                topic_or_query="Test topic",
                num_questions=3,
                timeout=1.0  # Short timeout
            )
            
            assert len(quiz.questions) == 0
            assert "error" in metrics or "warning" in metrics

    @pytest.mark.asyncio
    async def test_generate_multiple_questions_timeout_handling(self, orchestrator):
        """Test that generate_multiple_questions handles per-question timeouts."""
        original_method = orchestrator.generate_one_question_async
        call_count = 0
        mock_results = []

        async def mock_generate_with_potential_timeout(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second question times out
                await asyncio.sleep(2)  # Longer than timeout_per_question
                # This part won't be reached if timeout works
                result = await original_method(*args, **kwargs) 
                mock_results.append(True)
                return result
            else: # First and third questions succeed quickly
                # Ensure some context is passed to avoid issues if retrieval is attempted
                kwargs['context'] = "Sample context for testing"
                result = await original_method(*args, **kwargs)
                mock_results.append(True)
                return result

        with mock.patch.object(orchestrator, 'generate_one_question_async', side_effect=mock_generate_with_potential_timeout):
            questions, metrics = await orchestrator.generate_multiple_questions(
                topic_or_query="Test topic for timeout",
                num_questions=3,
                evaluate=False,
                timeout_per_question=0.5 # Short timeout for one question
            )

            assert len(questions) == 2  # Should get 2 questions, one timed out
            assert metrics["questions_succeeded"] == 2
            assert metrics["questions_failed"] == 1
            assert any("timeout" in str(err).lower() for err in metrics.get("errors", []))
            assert call_count == 3 # All three were attempted

    @pytest.mark.asyncio
    async def test_generate_quiz_partial_generation_on_timeout(self, orchestrator):
        """Test that generate_quiz returns partial results if overall timeout occurs mid-generation."""
        
        async def mock_generate_multiple_questions_with_delay(*args, **kwargs):
            # Generate one question successfully
            q1 = Question(question_id="q1", question_text="Q1", question_type=QuestionType.SHORT_ANSWER, difficulty=DifficultyLevel.EASY, options=[], correct_answers=[])
            await asyncio.sleep(0.2) # Time for one question
            
            # Then simulate a long delay for subsequent questions
            if kwargs.get("num_questions", 1) > 1:
                 # Simulate work that would exceed the quiz's overall timeout
                await asyncio.sleep(2) # This sleep will cause the main quiz timeout
            
            # This return will likely be cut off by the timeout in generate_quiz
            return [q1], {"questions_succeeded": 1, "questions_failed": kwargs.get("num_questions",1) - 1, "perf_metrics": {}}

        with mock.patch.object(orchestrator, 'generate_multiple_questions', side_effect=mock_generate_multiple_questions_with_delay):
            quiz, metrics = await orchestrator.generate_quiz(
                title="Partial Quiz Test",
                description="Test partial generation on timeout",
                topic_or_query="Test topic",
                num_questions=3,
                timeout=0.5  # Overall timeout for the quiz generation
            )

            assert len(quiz.questions) == 1 # Should get the first question
            assert quiz.questions[0].question_id == "q1"
            assert "warning" in metrics # Should have a warning about timeout
            assert "timeout" in metrics.get("warning", "").lower()
            assert metrics.get("questions_generated", 0) == 1
            assert metrics.get("questions_requested", 0) == 3
