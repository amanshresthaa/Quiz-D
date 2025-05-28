"""
DSPy Optimizer Script for Quiz-D.
Run this script to optimize the prompts used in question generation.
"""

import asyncio
import logging
import sys
import os
import json
import time
from typing import Dict, Any, List

# Add parent directory to path to import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import QuestionType
from app.quiz_orchestrator import get_quiz_orchestrator
from app.question_generation import get_question_generation_module

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("dspy_optimizer")

# Sample questions to generate for training examples
SAMPLE_TOPICS = [
    "Python programming language",
    "Machine learning algorithms",
    "Deep learning concepts",
    "Natural language processing",
    "Computer vision techniques",
    # Added more diverse and specific topics for better training data
    "The French Revolution: Causes and Consequences",
    "Photosynthesis: The Process in Plants",
    "Basic Algebra: Solving Linear Equations",
    "Introduction to Object-Oriented Programming in Java",
    "The Water Cycle and Its Importance"
]


async def generate_training_examples(num_examples_per_topic: int = 2) -> Dict[str, int]:
    """
    Generate training examples for DSPy optimization.
    
    Args:
        num_examples_per_topic: Number of examples to generate per topic
        
    Returns:
        Dictionary with counts of examples by question type
    """
    orchestrator = get_quiz_orchestrator()
    generation_module = get_question_generation_module()
    
    # Count of examples generated per type
    example_counts = {
        QuestionType.MULTIPLE_CHOICE.value: 0,
        QuestionType.TRUE_FALSE.value: 0,
        QuestionType.SHORT_ANSWER.value: 0,
        QuestionType.ESSAY.value: 0
    }
    
    for topic in SAMPLE_TOPICS:
        logger.info(f"Generating training examples for topic: {topic}")
        
        for qt in [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER]:
            try:
                # Generate questions for this topic and type
                # Use a slightly higher number of questions to ensure enough good examples
                # And use the orchestrator's built-in diversity and retry logic
                quiz_task = asyncio.create_task(
                    orchestrator.generate_quiz(
                        title=f"Training Data: {topic} - {qt.value}",
                        description="Generating training data for DSPy optimization",
                        topic_or_query=topic,
                        num_questions=num_examples_per_topic + 1, # Generate a bit more to pick from
                        question_types=[qt],
                        difficulty=None, # Allow various difficulties
                        evaluate=True, # Ensure questions are evaluated for quality
                        diversity_factor=0.7, # Encourage diverse examples
                        timeout=120.0 # 2 min timeout for this batch
                    )
                )
                
                quiz, metrics = await quiz_task
                
                # The QuestionGenerationModule now automatically adds good examples
                # to the optimizer via add_training_example when questions are generated.
                # So, we just need to count them here based on what was successfully generated and evaluated.
                
                # We can inspect the generation_module's optimizer to see how many were added for this type if needed,
                # but for now, just log success based on quiz generation.
                successful_for_type = sum(1 for q in quiz.questions if q.question_type == qt and q.evaluation and q.evaluation.is_valid)
                example_counts[qt.value] += successful_for_type
                
                logger.info(f"Generated {len(quiz.questions)} questions for topic '{topic}', type {qt.value}. {successful_for_type} considered good training examples.")
                if metrics.get("generation_stats", {}).get("questions_failed", 0) > 0:
                    logger.warning(f"Failures during training example generation for {topic}, {qt.value}: {metrics['generation_stats']['questions_failed']}")

            except Exception as e:
                logger.error(f"Error generating examples for {topic}, {qt.value}: {str(e)}")
    
    return example_counts


async def run_dspy_optimization(num_trials: int = 5) -> Dict[str, Any]:
    """
    Run DSPy optimization for question generation modules.
    
    Args:
        num_trials: Number of optimization trials per question type
        
    Returns:
        Results of optimization
    """
    start_time = time.time()
    
    # Get the question generation module
    question_module = get_question_generation_module()
    
    # Check if DSPy is available
    if not question_module._dspy_generator.is_available():
        logger.error("DSPy not available for optimization")
        return {"success": False, "error": "DSPy not available"}
        
    # Get training examples counts before optimization
    existing_examples = {
        qt.value: len(question_module._optimizer.training_examples.get(qt, []))
        for qt in [QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER, QuestionType.ESSAY]
    }
    
    logger.info(f"Existing training examples: {existing_examples}")
    
    # If we don't have enough examples, generate some
    # Increased threshold for generating examples
    if sum(existing_examples.values()) < 20: # Ensure at least 20 good examples across types
        logger.info("Generating additional training examples as current count is low.")
        # Generate 3-4 examples per topic to get a good pool
        generated_counts = await generate_training_examples(num_examples_per_topic=3)
        logger.info(f"Generated training examples: {generated_counts}")
    
    # Run optimization
    # Increased number of trials for potentially better optimization
    logger.info(f"Starting optimization with {num_trials if num_trials else 10} trials per question type")
    
    optimization_results = question_module.optimize_question_generators(
        question_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.TRUE_FALSE, QuestionType.SHORT_ANSWER],
        num_trials=num_trials if num_trials else 10, # Default to 10 trials
        max_bootstrapped_demos=num_trials if num_trials else 10 # Align demos with trials
    )
    
    end_time = time.time()
    
    # Get updated optimization status
    status = question_module.get_optimization_status()
    
    return {
        "success": True,
        "duration_seconds": end_time - start_time,
        "optimization_results": optimization_results,
        "status": status
    }


async def main():
    """Run the DSPy optimization process."""
    logger.info("Starting DSPy optimization process")
    
    # Default number of trials, can be overridden by command line arg in future
    num_optimization_trials = 10 

    try:
        # Run optimization
        results = await run_dspy_optimization(num_trials=num_optimization_trials)
        
        # Save results
        with open("optimization_results.json", "w") as f:
            json.dump(results, f, indent=2)
            
        logger.info(f"Optimization completed: {results}")
        logger.info("Results saved to optimization_results.json")
        
    except Exception as e:
        logger.error(f"Error in optimization process: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
