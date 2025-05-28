"""
DSPy optimization module for improving question generation prompts.
This module implements optimization techniques to improve prompt quality.
"""

import dspy
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
import random
import time

from app.models import Question, ContentChunk, QuestionType, DifficultyLevel
from app.dspy_signatures import (
    QuizQuestionGen, 
    MultipleChoiceQuestionGen,
    TrueFalseQuestionGen,
    ShortAnswerQuestionGen,
    EssayQuestionGen,
    QualityChecker
)
from app.dspy_quiz_generator import get_dspy_quiz_generator

logger = logging.getLogger(__name__)


class QuestionGenerationOptimizer:
    """Class for optimizing question generation prompts using DSPy."""
    
    def __init__(self):
        """Initialize the optimizer."""
        self._dspy_generator = get_dspy_quiz_generator()
        self.optimized_modules = {}
        self.training_examples = {}
        
    def is_available(self) -> bool:
        """Check if DSPy optimization is available."""
        return self._dspy_generator.is_available()
        
    def add_training_example(self, 
                          question_type: QuestionType,
                          context: str,
                          question_text: str,
                          answer_text: str,
                          choices: Optional[List[str]] = None,
                          explanation: Optional[str] = None) -> None:
        """
        Add a training example for prompt optimization.
        
        Args:
            question_type: Type of question
            context: Source context
            question_text: Generated question
            answer_text: Correct answer
            choices: Multiple choice options (if applicable)
            explanation: Answer explanation (if available)
        """
        if not question_type in self.training_examples:
            self.training_examples[question_type] = []
            
        example = {
            "context": context,
            "question_text": question_text,
            "answer_text": answer_text
        }
        
        if choices:
            example["choices"] = choices
            
        if explanation:
            example["explanation"] = explanation
            
        self.training_examples[question_type].append(example)
        logger.info(f"Added training example for {question_type.value}")
        
    def _create_dspy_examples(self, question_type: QuestionType) -> List[dspy.Example]:
        """
        Create DSPy examples from training examples.
        
        Args:
            question_type: Question type to create examples for
            
        Returns:
            List of DSPy examples
        """
        examples = []
        type_examples = self.training_examples.get(question_type, [])
        
        if not type_examples:
            logger.warning(f"No training examples for {question_type.value}")
            return examples
            
        if question_type == QuestionType.MULTIPLE_CHOICE:
            for ex in type_examples:
                if not "choices" in ex:
                    continue
                    
                dspy_ex = dspy.Example(
                    context=ex["context"],
                    question=ex["question_text"],
                    answer=ex["answer_text"],
                    choices=ex["choices"],
                    explanation=ex.get("explanation", "")
                )
                examples.append(dspy_ex)
                
        elif question_type == QuestionType.TRUE_FALSE:
            for ex in type_examples:
                dspy_ex = dspy.Example(
                    context=ex["context"],
                    question=ex["question_text"],
                    answer=ex["answer_text"],
                    explanation=ex.get("explanation", "")
                )
                examples.append(dspy_ex)
                
        elif question_type == QuestionType.SHORT_ANSWER:
            for ex in type_examples:
                dspy_ex = dspy.Example(
                    context=ex["context"],
                    question=ex["question_text"],
                    answer=ex["answer_text"],
                    explanation=ex.get("explanation", "")
                )
                examples.append(dspy_ex)
                
        elif question_type == QuestionType.ESSAY:
            for ex in type_examples:
                # For essay questions, we need to convert answer text to points
                answer_points = ex["answer_text"].split("\n")
                if answer_points[0].startswith("- "):
                    answer_points = [point[2:] for point in answer_points]
                    
                dspy_ex = dspy.Example(
                    context=ex["context"],
                    question=ex["question_text"],
                    suggested_answer_points=answer_points
                )
                examples.append(dspy_ex)
        
        return examples
        
    def _evaluate_question_quality(self, pred: Any, gold: Any) -> float:
        """
        Custom metric for evaluating question quality.
        
        Args:
            pred: Prediction from the model
            gold: Gold standard (reference)
            
        Returns:
            Quality score (0-1)
        """
        # Basic validation checks
        if not hasattr(pred, 'question') or not pred.question.strip():
            return 0.0
            
        score = 0.0
        
        # Question should be well-formed (end with question mark)
        if pred.question.strip().endswith('?'):
            score += 0.3
            
        # Check answer validity
        if hasattr(pred, 'answer') and hasattr(gold, 'answer'):
            # For multiple choice and true/false, answer should be in choices
            if hasattr(pred, 'choices') and pred.answer in pred.choices:
                score += 0.3
                
            # For simple questions with no choices, just check that answer exists
            elif not hasattr(pred, 'choices') and pred.answer.strip():
                score += 0.3
        
        # Check explanation if applicable
        if hasattr(pred, 'explanation') and pred.explanation.strip():
            score += 0.2
            
        # For essay questions
        if hasattr(pred, 'suggested_answer_points') and len(pred.suggested_answer_points) > 0:
            score += 0.3
            # Additional points for having multiple points
            if len(pred.suggested_answer_points) >= 3:
                score += 0.2
            
        # Check that question relates to context (simple heuristic)
        if hasattr(gold, 'context') and hasattr(pred, 'question'):
            context_words = set(gold.context.lower().split()[:100])  # Use first 100 words only
            question_words = set(pred.question.lower().split())
            overlap = len(context_words.intersection(question_words))
            
            if overlap >= 2:  # At least a couple words in common
                score += 0.2
                
        return min(1.0, score)  # Cap at 1.0
        
    def optimize_module(self, question_type: QuestionType, num_trials: int = 10) -> Any:
        """
        Optimize a question generation module using BootstrapFewShotWithRandomSearch.
        
        Args:
            question_type: Type of question to optimize
            num_trials: Number of trials for optimization
            
        Returns:
            Optimized module or None if optimization fails
        """
        if not self.is_available():
            logger.warning("DSPy not available for optimization")
            return None
            
        if question_type not in self.training_examples or len(self.training_examples[question_type]) < 3:
            logger.warning(f"Not enough training examples for {question_type.value} optimization")
            return None
            
        try:
            logger.info(f"Starting optimization for {question_type.value} generation")
            examples = self._create_dspy_examples(question_type)
            
            # Split examples into train and test
            random.shuffle(examples)
            train_size = max(3, int(0.7 * len(examples)))
            trainset = examples[:train_size]
            testset = examples[train_size:]
            
            if not testset:  # If we don't have enough for a test set
                testset = trainset[-1:]  # Use last example as test
                
            # Choose the right module based on question type
            if question_type == QuestionType.MULTIPLE_CHOICE:
                base_module = dspy.ChainOfThought(MultipleChoiceQuestionGen)
            elif question_type == QuestionType.TRUE_FALSE:
                base_module = dspy.ChainOfThought(TrueFalseQuestionGen)
            elif question_type == QuestionType.SHORT_ANSWER:
                base_module = dspy.ChainOfThought(ShortAnswerQuestionGen)
            elif question_type == QuestionType.ESSAY:
                base_module = dspy.ChainOfThought(EssayQuestionGen)
            else:
                base_module = dspy.ChainOfThought(QuizQuestionGen)
            
            # Create the optimizer
            optimizer = dspy.BootstrapFewShotWithRandomSearch(
                metric=self._evaluate_question_quality,
                num_candidate_programs=3,  # Generate 3 candidate prompts
                max_bootstrapped_demos=3,  # Use up to 3 demonstrations in prompt
                num_trials=num_trials  # Number of optimization trials
            )
            
            # Start optimization process
            start_time = time.time()
            optimized = optimizer.compile(
                base_module,
                trainset=trainset,
                valset=testset
            )
            duration = time.time() - start_time
            
            # Evaluate the optimized module
            scores = []
            for example in testset:
                pred = optimized(context=example.context)
                score = self._evaluate_question_quality(pred, example)
                scores.append(score)
                
            avg_score = sum(scores) / len(scores) if scores else 0
            
            logger.info(f"Optimization for {question_type.value} completed in {duration:.2f}s")
            logger.info(f"Average quality score: {avg_score:.4f}")
            
            # Store the optimized module
            self.optimized_modules[question_type] = optimized
            return optimized
            
        except Exception as e:
            logger.error(f"Error optimizing module for {question_type.value}: {str(e)}")
            return None
            
    def get_optimized_module(self, question_type: QuestionType) -> Optional[Any]:
        """
        Get an optimized module for question generation.
        
        Args:
            question_type: Type of question
            
        Returns:
            Optimized DSPy module or None if not available
        """
        return self.optimized_modules.get(question_type)


# Global optimizer instance
_question_generation_optimizer = None

def get_question_generation_optimizer() -> QuestionGenerationOptimizer:
    """Get the global question generation optimizer instance."""
    global _question_generation_optimizer
    if _question_generation_optimizer is None:
        _question_generation_optimizer = QuestionGenerationOptimizer()
    return _question_generation_optimizer
