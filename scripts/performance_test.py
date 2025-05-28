"""
Performance testing script for Quiz-D.
Run this script to test the performance of the quiz generation system.
"""

import asyncio
import time
import logging
import json
import sys
import os
from typing import Dict, Any, List

# Add parent directory to path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import QuestionType, DifficultyLevel
from app.quiz_orchestrator import get_quiz_orchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("performance_test")

# Global flag to track initialization
_semantic_search_initialized = False

async def initialize_semantic_search():
    """Initialize semantic search functionality - mirrors FastAPI startup event."""
    global _semantic_search_initialized
    
    if _semantic_search_initialized:
        return
        
    logger.info("Initializing semantic search for performance testing...")
    
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
        
        _semantic_search_initialized = True
        logger.info("✅ Semantic search initialized successfully for performance testing")
        
    except Exception as e:
        logger.warning(f"⚠️  Could not initialize semantic search: {e}")
        logger.info("Performance tests will run without semantic search capabilities")

# Test topics of varying complexity and length - chosen to be more likely to have relevant content
TEST_TOPICS = [
    "Python programming",
    "Machine Learning basics",
    "Computer science fundamentals",
    "Data structures and algorithms",
    "Software engineering principles"
]


async def run_performance_test(
    topic: str,
    num_questions: int = 5,
    question_types: List[QuestionType] = None,
    difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
    evaluate: bool = True,
    timeout: float = 300.0,
    timeout_per_question: float = 30.0
) -> Dict[str, Any]:
    """
    Run a performance test for quiz generation.
    
    Args:
        topic: Topic for the quiz
        num_questions: Number of questions to generate
        question_types: Types of questions to generate
        difficulty: Difficulty level
        evaluate: Whether to evaluate questions
        timeout: Overall timeout for quiz generation
        timeout_per_question: Timeout per individual question
        
    Returns:
        Performance metrics
    """
    # Ensure semantic search is initialized
    await initialize_semantic_search()
    
    if question_types is None:
        question_types = [QuestionType.MULTIPLE_CHOICE]
        
    orchestrator = get_quiz_orchestrator()
    
    start_time = time.time()
    logger.info(f"Starting performance test for topic: {topic}")
    
    quiz = None
    metrics = {}
    quiz_generated = False
    error_message = None
    
    try:
        # Use asyncio.wait_for to enforce timeout at the test level
        quiz, metrics = await asyncio.wait_for(
            orchestrator.generate_quiz(
                title=f"Performance Test: {topic}",
                description=f"A performance test quiz on {topic}",
                topic_or_query=topic,
                num_questions=num_questions,
                question_types=question_types,
                difficulty=difficulty,
                evaluate=evaluate,
                diversity_factor=0.8,  # High diversity for testing
                timeout=timeout,
                timeout_per_question=timeout_per_question
            ),
            timeout=timeout + 10.0  # Give a little extra time for cleanup
        )
        
        quiz_generated = True
        
    except asyncio.TimeoutError:
        logger.warning(f"Quiz generation timed out for topic '{topic}' after {timeout}s")
        error_message = f"Timeout after {timeout}s"
        metrics = {
            "error": error_message,
            "generation_stats": {
                "error": error_message,
                "total_duration": timeout,
                "questions_per_second": 0
            }
        }
        
    except Exception as e:
        # Quiz generation failed completely
        logger.error(f"Quiz generation failed for topic '{topic}': {str(e)}")
        error_message = str(e)
        metrics = {
            "error": error_message,
            "generation_stats": {
                "error": error_message,
                "total_duration": 0,
                "questions_per_second": 0
            }
        }
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Handle partial generation case
    generated_count = len(quiz.questions) if quiz and hasattr(quiz, 'questions') else 0
    
    if quiz_generated and quiz and generated_count > 0:
        # Successful quiz generation (full or partial)
        result = {
            "topic": topic,
            "requested_questions": num_questions,
            "generated_questions": generated_count,
            "question_types": [qt.value for qt in question_types],
            "total_time_seconds": total_time,
            "questions_per_second": generated_count / total_time if total_time > 0 else 0,
            "evaluation_enabled": evaluate,
            "metrics": metrics.get("generation_stats", {}),
            "success": True,
            "partial_generation": generated_count < num_questions
        }
        
        status = "partial" if generated_count < num_questions else "complete"
        logger.info(f"Completed test for '{topic}' ({status}): {generated_count}/{num_questions} questions in {total_time:.2f}s")
    else:
        # Failed quiz generation
        result = {
            "topic": topic,
            "requested_questions": num_questions,
            "generated_questions": generated_count,
            "question_types": [qt.value for qt in question_types],
            "total_time_seconds": total_time,
            "questions_per_second": 0,
            "evaluation_enabled": evaluate,
            "metrics": metrics.get("generation_stats", {}),
            "success": False,
            "error": error_message,
            "partial_generation": False
        }
        
        logger.warning(f"Failed test for '{topic}': {error_message}")
    
    return result


async def test_question_type_performance() -> Dict[str, Any]:
    """Test performance across different question types."""
    results = {}
    
    for qt in [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER]:
        try:
            logger.info(f"Testing question type: {qt.value}")
            result = await run_performance_test(
                topic="Programming fundamentals",  # Use a topic likely to have content
                num_questions=3,
                question_types=[qt],
                evaluate=False,  # Skip evaluation to focus on generation
                timeout=90.0     # Reasonable timeout
            )
            results[qt.value] = result
        except Exception as e:
            logger.error(f"Question type test failed for {qt.value}: {e}")
            results[qt.value] = {"error": str(e), "success": False, "question_type": qt.value}
        
    return results


async def test_concurrency_scaling() -> Dict[str, Any]:
    """Test how performance scales with different concurrency levels."""
    # Ensure semantic search is initialized
    await initialize_semantic_search()
    
    orchestrator = get_quiz_orchestrator()
    results = {}
    
    # Test different concurrency levels more conservatively
    for max_concurrent in [1, 2, 3]:
        logger.info(f"Testing concurrency with {max_concurrent} concurrent tasks")
        
        try:
            # Modify the semaphore limit for testing
            original_semaphore = orchestrator.generation_semaphore
            orchestrator.generation_semaphore = asyncio.Semaphore(max_concurrent)
            
            result = await run_performance_test(
                topic="Computer programming concepts",
                num_questions=3,  # Fewer questions for concurrency tests
                evaluate=False,   # Skip evaluation to focus on generation performance
                timeout=120.0     # Shorter timeout for concurrency tests
            )
            
            results[f"concurrent_{max_concurrent}"] = result
            
            # Restore original semaphore
            orchestrator.generation_semaphore = original_semaphore
            
        except Exception as e:
            logger.error(f"Concurrency test failed for {max_concurrent} concurrent tasks: {e}")
            results[f"concurrent_{max_concurrent}"] = {
                "error": str(e),
                "success": False,
                "max_concurrent": max_concurrent
            }
        
    return results


async def test_error_handling_and_robustness() -> Dict[str, Any]:
    """Test performance under challenging conditions."""
    # Ensure semantic search is initialized
    await initialize_semantic_search()
    
    results = {}

    # Test 1: Very specific/narrow topic that might not have much content
    logger.info("Testing with a very specific topic")
    try:
        result_narrow = await run_performance_test(
            topic="Very specific niche programming concept xyz123",
            num_questions=3,
            evaluate=False,
            timeout=60.0,  # Shorter timeout
            timeout_per_question=15.0
        )
        results["narrow_topic_test"] = result_narrow
    except Exception as e:
        logger.error(f"Narrow topic test failed: {e}")
        results["narrow_topic_test"] = {"error": str(e), "success": False}

    # Test 2: High diversity requirement with limited content
    logger.info("Testing high diversity requirement")
    try:
        result_diversity = await run_performance_test(
            topic="Basic programming",  # Broad but might have similar content
            num_questions=5,
            evaluate=False,
            timeout=120.0
        )
        results["diversity_stress_test"] = result_diversity
    except Exception as e:
        logger.error(f"Diversity stress test failed: {e}")
        results["diversity_stress_test"] = {"error": str(e), "success": False}

    # Test 3: Timeout scenarios with short timeouts
    logger.info("Testing with very short timeouts")
    try:
        result_timeout = await run_performance_test(
            topic="Computer science fundamentals",
            num_questions=3,
            evaluate=False,
            timeout=15.0,  # Very short overall timeout
            timeout_per_question=5.0  # Very short per-question timeout
        )
        results["short_timeout_test"] = result_timeout
    except Exception as e:
        logger.error(f"Short timeout test failed: {e}")
        results["short_timeout_test"] = {"error": str(e), "success": False}

    # Test 4: Large number of questions
    logger.info("Testing with many questions")
    try:
        result_many = await run_performance_test(
            topic="Programming languages",
            num_questions=10,  # More questions than usual
            evaluate=False,
            timeout=180.0
        )
        results["many_questions_test"] = result_many
    except Exception as e:
        logger.error(f"Many questions test failed: {e}")
        results["many_questions_test"] = {"error": str(e), "success": False}

    return results

async def main():
    """Run the performance tests."""
    try:
        # Initialize semantic search first
        await initialize_semantic_search()
        
        all_results = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tests": {}
        }
        
        # Test 1: Basic performance for different topics
        logger.info("Running topic performance tests")
        topic_results = {}
        for topic in TEST_TOPICS:
            try:
                result = await run_performance_test(topic=topic)
                topic_results[topic] = result
            except Exception as e:
                logger.error(f"Topic test failed for '{topic}': {e}")
                topic_results[topic] = {"error": str(e), "success": False}
        all_results["tests"]["topic_performance"] = topic_results
        
        # Test 2: Question type performance
        logger.info("Running question type performance tests")
        try:
            qt_results = await test_question_type_performance()
            all_results["tests"]["question_type_performance"] = qt_results
        except Exception as e:
            logger.error(f"Question type performance tests failed: {e}")
            all_results["tests"]["question_type_performance"] = {"error": str(e)}
        
        # Test 3: Concurrency scaling
        logger.info("Running concurrency scaling tests")
        try:
            concurrency_results = await test_concurrency_scaling()
            all_results["tests"]["concurrency_scaling"] = concurrency_results
        except Exception as e:
            logger.error(f"Concurrency scaling tests failed: {e}")
            all_results["tests"]["concurrency_scaling"] = {"error": str(e)}
        
        # Test 4: Error handling and robustness tests
        logger.info("Running error handling and robustness tests")
        try:
            stress_test_results = await test_error_handling_and_robustness()
            all_results["tests"]["error_handling_robustness"] = stress_test_results
        except Exception as e:
            logger.error(f"Error handling and robustness tests failed: {e}")
            all_results["tests"]["error_handling_robustness"] = {"error": str(e)}
        
        # Save results to file
        try:
            with open("performance_results.json", "w") as f:
                json.dump(all_results, f, indent=2)
            logger.info("Performance tests completed. Results saved to performance_results.json")
        except Exception as e:
            logger.error(f"Failed to save results to file: {e}")
            # Print results to console as fallback
            print("=== PERFORMANCE TEST RESULTS ===")
            print(json.dumps(all_results, indent=2))
        
    except Exception as e:
        logger.error(f"Performance test suite failed: {e}")
        print(f"Performance test suite failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
