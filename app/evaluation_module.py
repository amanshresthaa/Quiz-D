"""
Question Evaluation Module.
This module provides functionality to evaluate the quality of generated questions
using both LLM-based evaluation and heuristic approaches.
"""

import dspy
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from difflib import SequenceMatcher

from app.models import Question, QuestionType, Quiz
from app.config import get_settings
from app.dspy_signatures import QuestionEvaluator
from app.dspy_quiz_generator import get_dspy_quiz_generator

logger = logging.getLogger(__name__)


class QuestionEvaluationModule:
    """Module for evaluating the quality of generated quiz questions."""
    
    def __init__(self):
        """Initialize the question evaluation module."""
        self.settings = get_settings()
        self._dspy_generator = get_dspy_quiz_generator()
        self._init_dspy_modules()
        self._stats = self._init_stats()
        
    def _init_dspy_modules(self):
        """Initialize DSPy modules for evaluation."""
        if not self._dspy_generator.is_available():
            logger.warning("DSPy not properly configured - evaluation will use fallbacks")
            return
            
        try:
            # Initialize evaluation modules
            self.evaluator = dspy.ChainOfThought(QuestionEvaluator)
            logger.info("Successfully initialized DSPy evaluation module")
        except Exception as e:
            logger.error(f"Failed to initialize DSPy evaluation module: {e}")
            
    def _init_stats(self) -> Dict[str, Any]:
        """Initialize statistics tracking."""
        return {
            "evaluations_performed": 0,
            "llm_evaluations": 0,
            "heuristic_evaluations": 0,
            "questions_passed": 0,
            "questions_failed": 0,
            "average_score": 0.0,
            "total_score": 0.0,
            "evaluations_by_type": {
                "multiple_choice": 0,
                "true_false": 0,
                "short_answer": 0,
                "essay": 0
            }
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get module statistics."""
        if self._stats["evaluations_performed"] > 0:
            self._stats["average_score"] = (
                self._stats["total_score"] / self._stats["evaluations_performed"]
            )
        return self._stats
    
    def evaluate_question_heuristic(self, 
                                  context: str, 
                                  question: Question) -> Tuple[bool, float, str]:
        """
        Evaluate question using heuristic methods.
        
        This function uses simple text matching and other heuristics to determine
        if a question is likely answerable from the context.
        
        Args:
            context: The source context
            question: The question to evaluate
            
        Returns:
            Tuple of (passed_evaluation, score, reasoning)
        """
        # Track this evaluation
        self._stats["evaluations_performed"] += 1
        self._stats["heuristic_evaluations"] += 1
        
        question_type = question.question_type
        if question_type in self._stats["evaluations_by_type"]:
            self._stats["evaluations_by_type"][question_type.value] += 1
        
        # Extract texts for comparison
        question_text = question.question_text.lower()
        answer_text = question.answer_text.lower()
        
        # Check if answer appears in context (basic heuristic)
        context_lower = context.lower()
        
        # For multiple choice, check if the correct answer is in context
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            # Check if the answer appears in context
            if answer_text in context_lower:
                score = 1.0
                reasoning = f"The answer '{answer_text}' appears verbatim in the context."
                self._stats["questions_passed"] += 1
                self._stats["total_score"] += score
                return True, score, reasoning
            else:
                # Try fuzzy matching
                similarity = self._get_best_substring_match(answer_text, context_lower)
                if similarity > 0.8:  # High similarity threshold
                    score = similarity
                    reasoning = f"The answer is similar to text in the context (similarity: {similarity:.2f})."
                    self._stats["questions_passed"] += 1
                    self._stats["total_score"] += score
                    return True, score, reasoning
                else:
                    score = max(0.3, similarity)  # Base score on similarity with minimum
                    reasoning = f"The answer doesn't appear directly in the context (best match: {similarity:.2f})."
                    self._stats["questions_failed"] += 1
                    self._stats["total_score"] += score
                    return False, score, reasoning
                    
        # For true/false questions
        elif question.question_type == QuestionType.TRUE_FALSE:
            # Extract key terms from question
            words = re.findall(r'\b\w+\b', question_text)
            important_words = [w for w in words if len(w) > 3 and w not in ['what', 'when', 'where', 'which', 'how', 'that', 'this', 'these', 'those']]
            
            # Count how many key terms appear in context
            matches = sum(1 for word in important_words if word in context_lower)
            
            if matches >= len(important_words) * 0.7:  # 70% of key terms found
                score = 0.8
                reasoning = f"{matches}/{len(important_words)} key terms from the question found in context."
                self._stats["questions_passed"] += 1
                self._stats["total_score"] += score
                return True, score, reasoning
            else:
                score = max(0.4, matches / max(1, len(important_words)))
                reasoning = f"Only {matches}/{len(important_words)} key terms from the question found in context."
                self._stats["questions_failed"] += 1
                self._stats["total_score"] += score
                return False, score, reasoning
                
        # For short answer questions
        elif question.question_type == QuestionType.SHORT_ANSWER:
            if answer_text in context_lower:
                score = 1.0
                reasoning = f"The answer '{answer_text}' appears verbatim in the context."
                self._stats["questions_passed"] += 1
                self._stats["total_score"] += score
                return True, score, reasoning
            else:
                # Try fuzzy matching for short answers
                similarity = self._get_best_substring_match(answer_text, context_lower)
                if similarity > 0.7:  # Lower threshold for short answers
                    score = similarity
                    reasoning = f"The answer is similar to text in the context (similarity: {similarity:.2f})."
                    self._stats["questions_passed"] += 1
                    self._stats["total_score"] += score
                    return True, score, reasoning
                else:
                    score = max(0.3, similarity)
                    reasoning = f"The answer doesn't appear directly in the context (best match: {similarity:.2f})."
                    self._stats["questions_failed"] += 1
                    self._stats["total_score"] += score
                    return False, score, reasoning
                    
        # For essay questions, just check if key terms are mentioned
        else:
            # Extract key points from answer
            answer_points = answer_text.split("\n")
            answer_keywords = set()
            
            for point in answer_points:
                words = re.findall(r'\b\w+\b', point)
                keywords = [w.lower() for w in words if len(w) > 4 and w.lower() not in ['what', 'when', 'where', 'which', 'how', 'that', 'this', 'these', 'those']]
                answer_keywords.update(keywords)
            
            # Count keyword matches in context
            matches = sum(1 for keyword in answer_keywords if keyword in context_lower)
            
            if matches >= len(answer_keywords) * 0.5:  # 50% threshold for essay
                score = 0.7
                reasoning = f"{matches}/{len(answer_keywords)} key terms from the answer found in context."
                self._stats["questions_passed"] += 1
                self._stats["total_score"] += score
                return True, score, reasoning
            else:
                score = max(0.3, matches / max(1, len(answer_keywords)))
                reasoning = f"Only {matches}/{len(answer_keywords)} key terms from the answer found in context."
                self._stats["questions_failed"] += 1
                self._stats["total_score"] += score
                return False, score, reasoning
    
    def _get_best_substring_match(self, needle: str, haystack: str) -> float:
        """
        Find the best substring match for needle in haystack.
        
        Args:
            needle: The string to search for
            haystack: The string to search in
            
        Returns:
            Float similarity score (0-1)
        """
        if len(needle) > len(haystack):
            return 0
            
        best_ratio = 0
        
        # For very short needles, do direct matching
        if len(needle) < 5:
            return 1.0 if needle in haystack else 0.0
            
        # For longer strings, use sliding window approach
        window_size = min(len(needle) * 3, len(haystack))
        step = max(1, window_size // 10)
        
        for i in range(0, len(haystack) - window_size + 1, step):
            substring = haystack[i:i + window_size]
            ratio = SequenceMatcher(None, needle, substring).ratio()
            best_ratio = max(best_ratio, ratio)
            
            # Early exit if we find a very good match
            if best_ratio > 0.9:
                break
                
        return best_ratio
    
    def evaluate_question_llm(self, 
                            context: str, 
                            question: Question) -> Tuple[bool, float, str, Dict[str, Any]]:
        """
        Evaluate question using LLM-based evaluation.
        
        Args:
            context: The source context
            question: The question to evaluate
            
        Returns:
            Tuple of (passed_evaluation, score, reasoning, detailed_results)
        """
        if not self._dspy_generator.is_available():
            logger.warning("DSPy not available, falling back to heuristic evaluation")
            passed, score, reasoning = self.evaluate_question_heuristic(context, question)
            return passed, score, reasoning, {"error": "LLM evaluation unavailable"}
            
        try:
            # Track this evaluation
            self._stats["evaluations_performed"] += 1
            self._stats["llm_evaluations"] += 1
            
            question_type = question.question_type
            if question_type in self._stats["evaluations_by_type"]:
                self._stats["evaluations_by_type"][question_type.value] += 1
            
            # Prepare choices field (depends on question type)
            choices = None
            if question.question_type == QuestionType.MULTIPLE_CHOICE:
                choices = question.choices
            elif question.question_type == QuestionType.TRUE_FALSE:
                choices = ["True", "False"]
            
            # Run LLM evaluation
            result = self.evaluator(
                context=context,
                question=question.question_text,
                answer=question.answer_text,
                choices=choices
            )
            
            # Parse results
            answerable = result.answerable.lower() == "true"
            correct = result.correct.lower() == "true" 
            score = float(result.score)
            
            # Ensure score is in valid range
            score = max(0.0, min(1.0, score))
            
            # Determine pass/fail based on both criteria
            passed = answerable and correct and score >= 0.7
            
            # Update stats
            if passed:
                self._stats["questions_passed"] += 1
            else:
                self._stats["questions_failed"] += 1
                
            self._stats["total_score"] += score
            
            # Prepare detailed results
            details = {
                "answerable": answerable,
                "correct": correct,
                "score": score,
                "reasoning": result.reasoning,
                "suggested_improvement": result.suggested_improvement
            }
            
            return passed, score, result.reasoning, details
            
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}, falling back to heuristic")
            passed, score, reasoning = self.evaluate_question_heuristic(context, question)
            return passed, score, reasoning, {"error": str(e)}
    
    def evaluate_question(self, 
                        context: str, 
                        question: Question, 
                        use_llm: bool = True) -> Tuple[bool, float, str, Optional[Dict[str, Any]]]:
        """
        Evaluate a question using the best available method.
        
        Args:
            context: The source context
            question: The question to evaluate
            use_llm: Whether to use LLM-based evaluation if available
            
        Returns:
            Tuple of (passed_evaluation, score, reasoning, detailed_results)
        """
        if use_llm and self._dspy_generator.is_available():
            try:
                return self.evaluate_question_llm(context, question)
            except Exception as e:
                logger.error(f"LLM evaluation failed with error: {e}")
                # Fall back to heuristic
                passed, score, reasoning = self.evaluate_question_heuristic(context, question)
                return passed, score, reasoning, {"error": str(e)}
        else:
            # Direct heuristic evaluation
            passed, score, reasoning = self.evaluate_question_heuristic(context, question)
            return passed, score, reasoning, None
    
    def evaluate_quiz(self, quiz: Quiz, contexts: Dict[str, str]) -> Dict[str, Any]:
        """
        Evaluate a complete quiz.
        
        Args:
            quiz: The quiz to evaluate
            contexts: Dictionary mapping content_ids to their contexts
            
        Returns:
            Evaluation results for the quiz
        """
        if not quiz.questions:
            return {
                "score": 0.0,
                "passed": False,
                "reasoning": "Quiz has no questions",
                "question_evaluations": []
            }
            
        # Evaluate each question
        question_evaluations = []
        total_score = 0.0
        passed_questions = 0
        
        for question in quiz.questions:
            # Get context for this question
            content_id = question.source_content_id
            if not content_id or content_id not in contexts:
                # Skip questions without associated context
                logger.warning(f"No context found for question {question.id}")
                continue
                
            context = contexts[content_id]
            
            # Evaluate the question
            passed, score, reasoning, details = self.evaluate_question(context, question)
            
            question_evaluations.append({
                "question_id": question.id,
                "passed": passed,
                "score": score,
                "reasoning": reasoning,
                "details": details
            })
            
            total_score += score
            if passed:
                passed_questions += 1
        
        # Calculate quiz-level metrics
        if question_evaluations:
            avg_score = total_score / len(question_evaluations)
            passed_ratio = passed_questions / len(question_evaluations)
        else:
            avg_score = 0.0
            passed_ratio = 0.0
            
        # Quiz passes if average score >= 0.7 and at least 70% of questions passed
        quiz_passed = avg_score >= 0.7 and passed_ratio >= 0.7
        
        # Generate overall reasoning
        if quiz_passed:
            reasoning = f"Quiz is high quality with an average score of {avg_score:.2f} and {passed_questions}/{len(question_evaluations)} questions passed evaluation."
        else:
            reasoning = f"Quiz needs improvement. Average score: {avg_score:.2f}, with only {passed_questions}/{len(question_evaluations)} questions passing evaluation."
            
        return {
            "score": avg_score,
            "passed": quiz_passed,
            "reasoning": reasoning,
            "question_evaluations": question_evaluations
        }


# Global module instance
_evaluation_module = None

def get_evaluation_module() -> QuestionEvaluationModule:
    """
    Get the global question evaluation module instance.
    
    Returns:
        QuestionEvaluationModule instance
    """
    global _evaluation_module
    if _evaluation_module is None:
        _evaluation_module = QuestionEvaluationModule()
    return _evaluation_module
