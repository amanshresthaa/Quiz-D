"""
Core question generation module using DSPy.
Implements question generation capabilities using retrieval-augmented generation.
"""

import dspy
import logging
from typing import List, Dict, Any, Optional, Tuple
import uuid
from datetime import datetime

from app.models import Question, ContentChunk, QuestionType, DifficultyLevel
from app.config import get_settings
from app.dspy_signatures import (
    QuizQuestionGen, 
    MultipleChoiceQuestionGen,
    TrueFalseQuestionGen,
    ShortAnswerQuestionGen,
    EssayQuestionGen,
    QualityChecker
)
from app.retrieval_engine import RetrievalEngine, SearchMode
from app.dspy_quiz_generator import get_dspy_quiz_generator, DSPyQuizGenerator
from app.dspy_optimizers import get_question_generation_optimizer

logger = logging.getLogger(__name__)


class QuestionGenerationModule:
    """Module for generating quiz questions using DSPy and retrieval."""
    
    def __init__(self, retrieval_engine: RetrievalEngine = None):
        """
        Initialize the question generation module.
        
        Args:
            retrieval_engine: RetrievalEngine instance for context retrieval
        """
        self.settings = get_settings()
        self._dspy_generator = get_dspy_quiz_generator()
        # Add optimizer integration
        self._optimizer = get_question_generation_optimizer()
        self.retrieval_engine = retrieval_engine
        self._init_dspy_modules()
        self._stats = self._init_stats()
        # Track optimized modules status
        self._optimized_modules_status = {
            QuestionType.MULTIPLE_CHOICE: False,
            QuestionType.TRUE_FALSE: False,
            QuestionType.SHORT_ANSWER: False,
            QuestionType.ESSAY: False
        }
        
    def _init_dspy_modules(self):
        """Initialize DSPy modules."""
        if not self._dspy_generator.is_available():
            logger.warning("DSPy not properly configured - generation will use fallbacks")
            return
        
        try:
            # Initialize base question generation modules
            self.basic_qa_generator = dspy.ChainOfThought(QuizQuestionGen)
            self.mc_generator = dspy.ChainOfThought(MultipleChoiceQuestionGen)
            self.tf_generator = dspy.ChainOfThought(TrueFalseQuestionGen)
            self.sa_generator = dspy.ChainOfThought(ShortAnswerQuestionGen)
            self.essay_generator = dspy.ChainOfThought(EssayQuestionGen)
            
            # Quality check module
            self.quality_checker = dspy.ChainOfThought(QualityChecker)
            
            logger.info("Successfully initialized DSPy question generation modules")
        except Exception as e:
            logger.error(f"Failed to initialize DSPy modules: {e}")
            
    def _init_stats(self) -> Dict[str, Any]:
        """Initialize statistics tracking."""
        return {
            "total_questions_generated": 0,
            "successful_generations": 0,
            "failed_generations": 0,
            "questions_by_type": {
                "multiple_choice": 0,
                "true_false": 0,
                "short_answer": 0,
                "essay": 0
            },
            "average_quality_score": 0.0,
            "total_quality_score": 0.0,
            "quality_checks_performed": 0
        }
        
    def get_statistics(self) -> Dict[str, Any]:
        """Get module statistics."""
        if self._stats["quality_checks_performed"] > 0:
            self._stats["average_quality_score"] = (
                self._stats["total_quality_score"] / self._stats["quality_checks_performed"]
            )
        return self._stats
        
    def _parse_choices(self, choices_output) -> List[str]:
        """
        Parse choices from DSPy output that might be a string or list.
        
        Args:
            choices_output: The choices output from DSPy (could be string or list)
            
        Returns:
            List[str]: Parsed choices as a list of strings
        """
        if isinstance(choices_output, list):
            return choices_output
            
        if isinstance(choices_output, str):
            # Try to parse string format like "A. Option 1\nB. Option 2\n..."
            lines = choices_output.strip().split('\n')
            choices = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # Remove letter prefixes like "A. ", "B. ", "A) ", "B) "
                if len(line) > 2 and line[0].isalpha() and line[1] in '.)':
                    choice = line[2:].strip()
                else:
                    choice = line
                if choice:
                    choices.append(choice)
            
            if len(choices) >= 2:  # Valid if at least 2 choices
                return choices
                
        # Fallback: return default choices
        logger.warning(f"Could not parse choices from: {choices_output}")
        return ["Option A", "Option B", "Option C", "Option D"]

    def generate_question(self, 
                         context: str, 
                         question_type: QuestionType = QuestionType.MULTIPLE_CHOICE,
                         difficulty: DifficultyLevel = DifficultyLevel.MEDIUM) -> Optional[Dict[str, Any]]:
        """
        Generate a single question from context with optimized modules when available.
        
        Args:
            context: The content to generate a question from
            question_type: Type of question to generate
            difficulty: Desired difficulty level
            
        Returns:
            Dict containing question data or None if generation fails
        """
        if not self._dspy_generator.is_available():
            logger.warning("DSPy not available, using sample question")
            return self._generate_sample_question(question_type, difficulty)
            
        try:
            self._stats["total_questions_generated"] += 1
            
            # Add difficulty instruction to context
            difficulty_prefix = f"[Generate a {difficulty.value} difficulty level question] "
            augmented_context = difficulty_prefix + context
            
            # Check if we should use an optimized module
            should_use_optimized = (
                self._optimizer.is_available() and 
                question_type in self._optimized_modules_status and 
                self._optimized_modules_status[question_type]
            )
            
            optimized_module = None
            if should_use_optimized:
                optimized_module = self._optimizer.get_optimized_module(question_type)
                
            # Generate question based on type using the appropriate module
            if question_type == QuestionType.MULTIPLE_CHOICE:
                # Use optimized module if available, otherwise fall back to default
                generator = optimized_module if optimized_module else self.mc_generator
                result = generator(context=augmented_context)
                
                question_data = {
                    "question_text": result.question,
                    "answer_text": result.answer,
                    "choices": self._parse_choices(result.choices),
                    "explanation": result.explanation,
                    "question_type": QuestionType.MULTIPLE_CHOICE,
                    "difficulty": difficulty,
                    "used_optimized_module": bool(optimized_module)
                }
                self._stats["questions_by_type"]["multiple_choice"] += 1
                
            elif question_type == QuestionType.TRUE_FALSE:
                generator = optimized_module if optimized_module else self.tf_generator
                result = generator(context=augmented_context)
                
                question_data = {
                    "question_text": result.question,
                    "answer_text": result.answer,
                    "choices": ["True", "False"],
                    "explanation": result.explanation,
                    "question_type": QuestionType.TRUE_FALSE,
                    "difficulty": difficulty,
                    "used_optimized_module": bool(optimized_module)
                }
                self._stats["questions_by_type"]["true_false"] += 1
                
            elif question_type == QuestionType.SHORT_ANSWER:
                generator = optimized_module if optimized_module else self.sa_generator
                result = generator(context=augmented_context)
                
                question_data = {
                    "question_text": result.question,
                    "answer_text": result.answer,
                    "explanation": result.explanation,
                    "question_type": QuestionType.SHORT_ANSWER,
                    "difficulty": difficulty,
                    "used_optimized_module": bool(optimized_module)
                }
                self._stats["questions_by_type"]["short_answer"] += 1
                
            elif question_type == QuestionType.ESSAY:
                generator = optimized_module if optimized_module else self.essay_generator
                result = generator(context=augmented_context)
                
                # Handle different output formats between optimized and standard modules
                answer_points = []
                if hasattr(result, 'suggested_answer_points'):
                    answer_points = result.suggested_answer_points
                
                question_data = {
                    "question_text": result.question,
                    "answer_text": "\n".join([f"- {point}" for point in answer_points]),
                    "question_type": QuestionType.ESSAY,
                    "difficulty": difficulty,
                    "used_optimized_module": bool(optimized_module)
                }
                self._stats["questions_by_type"]["essay"] += 1
                
            else:
                # Fallback to basic QA
                result = self.basic_qa_generator(context=augmented_context)
                question_data = {
                    "question_text": result.question,
                    "answer_text": result.answer,
                    "question_type": question_type,
                    "difficulty": difficulty,
                    "used_optimized_module": False
                }
            
            # Save successful question as potential training example for optimization
            if self._optimizer.is_available():
                try:
                    # Don't add examples from optimized modules to avoid feedback loop
                    if not question_data.get("used_optimized_module", False):
                        self._optimizer.add_training_example(
                            question_type=question_type,
                            context=context,
                            question_text=question_data["question_text"],
                            answer_text=question_data["answer_text"],
                            choices=question_data.get("choices"),
                            explanation=question_data.get("explanation")
                        )
                except Exception as e:
                    logger.warning(f"Failed to add training example: {e}")
            
            self._stats["successful_generations"] += 1
            return question_data
            
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            self._stats["failed_generations"] += 1
            return None
            
    def check_question_quality(self, 
                             context: str, 
                             question: str, 
                             answer: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Check the quality of a generated question.
        
        Args:
            context: Original context
            question: Generated question
            answer: Generated answer
            
        Returns:
            Tuple of (is_high_quality, improvement_data)
        """
        if not self._dspy_generator.is_available():
            return True, None
            
        try:
            result = self.quality_checker(
                context=context,
                question=question,
                answer=answer
            )
            
            is_high_quality = result.is_high_quality.lower() == "true"
            
            # Update quality stats
            self._stats["quality_checks_performed"] += 1
            quality_score = 1.0 if is_high_quality else 0.0
            self._stats["total_quality_score"] += quality_score
            
            if not is_high_quality:
                return False, {
                    "issues": result.issues,
                    "improved_question": result.improved_question,
                    "improved_answer": result.improved_answer
                }
            
            return True, None
            
        except Exception as e:
            logger.error(f"Question quality check failed: {e}")
            return True, None  # Assume it's fine if check fails
    
    async def generate_one_question(self, 
                            topic_or_query: str,
                            question_type: QuestionType = QuestionType.MULTIPLE_CHOICE,
                            difficulty: DifficultyLevel = DifficultyLevel.MEDIUM) -> Optional[Question]:
        """
        Generate one question from a topic or query using retrieval.
        
        Args:
            topic_or_query: Topic or query to generate a question about
            question_type: Type of question to generate
            difficulty: Desired difficulty level
            
        Returns:
            Question object or None if generation fails
        """
        if not self.retrieval_engine:
            logger.error("No retrieval engine available")
            return None
            
        try:
            # Retrieve relevant context
            search_results = await self.retrieval_engine.search(
                query=topic_or_query,
                mode=SearchMode.HYBRID,
                limit=3
            )
            
            if not search_results:
                logger.warning(f"No context found for topic: {topic_or_query}")
                return None
                
            # Combine context from top results
            combined_context = "\n\n".join([
                f"CONTENT: {result.chunk_text}" 
                for result in search_results
            ])
            
            # Generate question
            question_data = self.generate_question(
                context=combined_context,
                question_type=question_type,
                difficulty=difficulty
            )
            
            if not question_data:
                return None
                
            # Check quality (optional improvement step)
            is_high_quality, improvements = self.check_question_quality(
                context=combined_context,
                question=question_data["question_text"],
                answer=question_data["answer_text"]
            )
            
            # Apply improvements if needed
            if not is_high_quality and improvements:
                question_data["question_text"] = improvements["improved_question"]
                question_data["answer_text"] = improvements["improved_answer"]
                
            # Create Question object
            return Question(
                id=str(uuid.uuid4()),
                source_content_id=search_results[0].content_id if search_results else None,
                created_at=datetime.now(),
                **question_data
            )
                
        except Exception as e:
            logger.error(f"Failed to generate question: {e}")
            return None
    
    def _generate_sample_question(self, 
                               question_type: QuestionType,
                               difficulty: DifficultyLevel) -> Dict[str, Any]:
        """Generate a sample question when DSPy is unavailable."""
        if question_type == QuestionType.MULTIPLE_CHOICE:
            return {
                "question_text": "What is the main purpose of DSPy in the context of LLM applications?",
                "answer_text": "To provide a framework for programming language models",
                "choices": [
                    "To provide a framework for programming language models", 
                    "To replace Python as a programming language", 
                    "To generate images using AI", 
                    "To create databases for machine learning"
                ],
                "explanation": "DSPy is a framework designed for programming language models rather than prompting them, enabling more structured and maintainable LLM applications.",
                "question_type": QuestionType.MULTIPLE_CHOICE,
                "difficulty": difficulty
            }
        elif question_type == QuestionType.TRUE_FALSE:
            return {
                "question_text": "DSPy is primarily used for image generation.",
                "answer_text": "False",
                "choices": ["True", "False"],
                "explanation": "DSPy is a framework for programming language models, not specifically for image generation.",
                "question_type": QuestionType.TRUE_FALSE,
                "difficulty": difficulty
            }
        elif question_type == QuestionType.SHORT_ANSWER:
            return {
                "question_text": "What does DSPy stand for?",
                "answer_text": "Declarative Systems for Python",
                "explanation": "DSPy stands for Declarative Systems for Python, highlighting its role in creating declarative interfaces for language models.",
                "question_type": QuestionType.SHORT_ANSWER,
                "difficulty": difficulty
            }
        else:
            return {
                "question_text": "Explain how DSPy improves the development of LLM-powered applications compared to traditional prompting approaches.",
                "answer_text": "- Provides structured interfaces via Signatures\n- Enables modular composition of LLM calls\n- Supports optimization of prompts\n- Allows for testing and evaluation of LLM components\n- Creates reproducible pipelines",
                "question_type": QuestionType.ESSAY,
                "difficulty": difficulty
            }
    
    def optimize_question_generators(self, question_types: List[QuestionType] = None, num_trials: int = 10) -> Dict[str, bool]:
        """
        Optimize question generation modules using training examples.
        
        Args:
            question_types: List of question types to optimize (or all if None)
            num_trials: Number of optimization trials per question type
            
        Returns:
            Dict mapping question types to optimization success status
        """
        if not self._optimizer.is_available():
            logger.warning("DSPy optimization not available")
            return {qt.value: False for qt in QuestionType}
            
        if question_types is None:
            question_types = [
                QuestionType.MULTIPLE_CHOICE,
                QuestionType.TRUE_FALSE,
                QuestionType.SHORT_ANSWER,
                QuestionType.ESSAY
            ]
            
        results = {}
        
        for qt in question_types:
            try:
                logger.info(f"Optimizing {qt.value} question generator")
                optimized_module = self._optimizer.optimize_module(qt, num_trials=num_trials)
                
                if optimized_module:
                    self._optimized_modules_status[qt] = True
                    results[qt.value] = True
                    logger.info(f"Successfully optimized {qt.value} question generator")
                else:
                    results[qt.value] = False
                    logger.warning(f"Failed to optimize {qt.value} question generator")
            except Exception as e:
                logger.error(f"Error optimizing {qt.value} question generator: {e}")
                results[qt.value] = False
                
        return results
        
    def get_optimization_status(self) -> Dict[str, bool]:
        """Get the status of optimized modules."""
        return {k.value: v for k, v in self._optimized_modules_status.items()}
        

# Global module instance
_question_generation_module = None

def get_question_generation_module(retrieval_engine: Optional[RetrievalEngine] = None) -> QuestionGenerationModule:
    """
    Get the global question generation module instance.
    
    Args:
        retrieval_engine: Optional retrieval engine to use
        
    Returns:
        QuestionGenerationModule instance
    """
    global _question_generation_module
    if _question_generation_module is None:
        _question_generation_module = QuestionGenerationModule(retrieval_engine)
    return _question_generation_module
