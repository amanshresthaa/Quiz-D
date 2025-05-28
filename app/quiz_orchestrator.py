"""
Orchestrator for the quiz generation process.
This module connects retrieval with generation to produce complete quizzes.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional, Set, Tuple
import uuid
from datetime import datetime
import heapq
import random
import time
import weakref
import re # Added import

from app.models import Question, Quiz, ContentChunk, QuestionType, DifficultyLevel
from app.config import get_settings
from app.question_generation import get_question_generation_module, QuestionGenerationModule
from app.retrieval_engine import RetrievalEngine, SearchMode, get_retrieval_engine
from app.evaluation_module import get_evaluation_module

logger = logging.getLogger(__name__)


class QuizOrchestrator:
    """
    Orchestrates the complete process of generating quiz questions including:
    1. Content retrieval
    2. Question generation
    3. Answer verification
    4. Quiz composition
    """
    
    _PREDEFINED_STOPWORDS = set([
        'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should', 'can',
        'could', 'may', 'might', 'must', 'i', 'you', 'he', 'she', 'it', 'we', 'they',
        'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their',
        'mine', 'yours', 'hers', 'ours', 'theirs', 'to', 'of', 'in', 'on', 'at',
        'by', 'for', 'with', 'about', 'against', 'between', 'into', 'through',
        'during', 'before', 'after', 'above', 'below', 'from', 'up', 'down', 'out',
        'off', 'over', 'under', 'again', 'further', 'then', 'once', 'here', 'there',
        'when', 'where', 'why', 'how', 'all', 'any', 'both', 'each', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
        'so', 'than', 'too', 'very', 's', 't', 'just', 'don', 'shouldve', 'now',
        'd', 'll', 'm', 'o', 're', 've', 'y', 'ain', 'aren', 'couldn', 'didn',
        'doesn', 'hadn', 'hasn', 'haven', 'isn', 'ma', 'mightn', 'mustn',
        'needn', 'shan', 'shouldn', 'wasn', 'weren', 'won', 'wouldn', 'what', 'which',
        'who', 'whom', 'this', 'that', 'these', 'those', 'tell', 'explain', 'describe',
        'list', 'define', 'compare', 'contrast', 'summarize' # Common instruction verbs
    ])
    
    def __init__(self):
        """Initialize the quiz orchestrator."""
        self.settings = get_settings()
        self.retrieval_engine = get_retrieval_engine()
        self.question_generator = get_question_generation_module(retrieval_engine=self.retrieval_engine)
        self.evaluator = get_evaluation_module()
        # Add a semaphore for rate limiting
        self.generation_semaphore = asyncio.Semaphore(3)  # Allow up to 3 concurrent generations
        self._stats = {
            "quizzes_generated": 0,
            "total_questions": 0,
            "failed_questions": 0,
            "average_generation_time": 0,
            "total_generation_time": 0,
            "evaluation_stats": {
                "questions_evaluated": 0,
                "questions_passed": 0,
                "questions_failed": 0,
                "average_quality_score": 0,
            },
            "concurrency": {
                "max_concurrent_tasks": 3,
                "rate_limited_count": 0,
                "retry_count": 0
            },
            "caching": {
                "cache_hits": 0,
                "cache_misses": 0
            }
        }
        # Add cache for context retrieval
        self._context_cache = {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        # Add question generator stats to orchestrator stats
        stats = {**self._stats}
        generator_stats = self.question_generator.get_statistics()
        stats["question_generator"] = generator_stats
        
        # Add evaluator stats
        evaluator_stats = self.evaluator.get_statistics()
        stats["evaluator"] = evaluator_stats
        
        # Calculate average time if we've generated quizzes
        if stats["quizzes_generated"] > 0:
            stats["average_generation_time"] = stats["total_generation_time"] / stats["quizzes_generated"]
        
        return stats
    
    async def _get_cached_context(self, topic_or_query: str, limit: int = 3) -> List[Any]:
        """
        Retrieve and cache context for a topic or query.
        
        Args:
            topic_or_query: Topic or query to retrieve context for
            limit: Maximum number of results to return
            
        Returns:
            List of search results
        """
        if not self.retrieval_engine:
            return []
            
        # Create cache key
        cache_key = f"{topic_or_query}_{limit}"
        
        # Check cache first
        if cache_key in self._context_cache:
            self._stats["caching"]["cache_hits"] += 1
            return self._context_cache[cache_key]
        
        self._stats["caching"]["cache_misses"] += 1
            
        try:
            # Retrieve relevant context using unified retrieve API
            search_results = await self.retrieval_engine.retrieve(
                query=topic_or_query,
                mode=SearchMode.LEXICAL_ONLY,
                max_results=limit
            )
            
            # Cache the results (limit cache size to prevent memory issues)
            if len(self._context_cache) < 100:  # Simple cache size limit
                self._context_cache[cache_key] = search_results
            
            return search_results
        except Exception as e:
            logger.error(f"Error retrieving context: {e}")
            return []
            
    async def generate_one_question_async(self, 
                                   topic_or_query: str,
                                   question_type: QuestionType = QuestionType.MULTIPLE_CHOICE,
                                   difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
                                   evaluate: bool = True,
                                   max_retries: int = 2) -> Tuple[Optional[Question], Dict[str, Any]]:
        """
        Generate one question asynchronously with retry logic.
        
        Args:
            topic_or_query: Topic or query to generate question about
            question_type: Type of question to generate
            difficulty: Difficulty level
            evaluate: Whether to evaluate the question
            max_retries: Maximum number of retry attempts
            
        Returns:
            Tuple of (Question object or None, evaluation results)
        """
        attempt = 0
        evaluation_results = {}
        
        while attempt <= max_retries:
            try:
                # Use semaphore for rate limiting
                async with self.generation_semaphore:
                    # Call the async method directly
                    question = await self.question_generator.generate_one_question(
                        topic_or_query,
                        question_type,
                        difficulty
                    )
                    
                    # If question generation failed, retry
                    if not question:
                        attempt += 1
                        if attempt <= max_retries:
                            logger.warning(f"Generation attempt {attempt} failed, retrying for {topic_or_query}")
                            self._stats["concurrency"]["retry_count"] += 1
                            await asyncio.sleep(1)  # Add a small delay before retry
                            continue
                        return None, {"error": f"Failed to generate question after {max_retries} attempts"}
                
                # Evaluate the question if requested and a question was generated
                if evaluate and question:
                    # Get context for evaluation 
                    if not self.retrieval_engine:
                        logger.error("No retrieval engine available for evaluation")
                        return question, {"error": "No retrieval engine available"}
                        
                    # Use cached context retrieval
                    search_results = await self._get_cached_context(topic_or_query)
                    
                    if not search_results:
                        logger.warning(f"No context found for evaluation: {topic_or_query}")
                        return question, {"error": "No context available for evaluation"}
                        
                    # Combine context from top results
                    combined_context = "\n\n".join([
                        f"CONTENT: {result.chunk_text}" 
                        for result in search_results
                    ])
                    
                    # Evaluate the question
                    passed, score, reasoning, details = self.evaluator.evaluate_question(
                        context=combined_context,
                        question=question
                    )
                    
                    evaluation_results = {
                        "passed": passed,
                        "score": score,
                        "reasoning": reasoning,
                        "details": details
                    }
                    
                    # Update evaluation stats
                    self._stats["evaluation_stats"]["questions_evaluated"] += 1
                    if passed:
                        self._stats["evaluation_stats"]["questions_passed"] += 1
                    else:
                        self._stats["evaluation_stats"]["questions_failed"] += 1
                        
                    # Update average quality score
                    current_total = self._stats["evaluation_stats"]["average_quality_score"] * (
                        self._stats["evaluation_stats"]["questions_evaluated"] - 1
                    )
                    new_total = current_total + score
                    self._stats["evaluation_stats"]["average_quality_score"] = new_total / self._stats["evaluation_stats"]["questions_evaluated"]
                    
                    # If question failed evaluation but we have retries left, try again
                    if not passed and attempt < max_retries:
                        attempt += 1
                        logger.warning(f"Question failed evaluation, retry {attempt} for {topic_or_query}")
                        self._stats["concurrency"]["retry_count"] += 1
                        continue
                    
                    # If question failed evaluation and no retries left, return None
                    if not passed:
                        return None, evaluation_results
                
                return question, evaluation_results
                
            except Exception as e:
                logger.error(f"Error generating question: {e}")
                attempt += 1
                if attempt <= max_retries:
                    logger.warning(f"Error in attempt {attempt}, retrying: {str(e)}")
                    await asyncio.sleep(1)  # Add a small delay before retry
                else:
                    return None, {"error": f"Exception during question generation: {str(e)}"}
    
    async def generate_multiple_questions(self,
                                     topic_or_query: str,
                                     num_questions: int = 5,
                                     question_types: List[QuestionType] = None,
                                     difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
                                     evaluate: bool = True,
                                     diversity_factor: float = 0.7,
                                     max_concurrent: int = 5,
                                     timeout_per_question: float = 30.0) -> Tuple[List[Question], Dict[str, Any]]:
        """
        Generate multiple questions asynchronously with improved concurrency and diversity.
        
        Args:
            topic_or_query: Topic or query for questions
            num_questions: Number of questions to generate
            question_types: Types of questions to generate
            difficulty: Difficulty level
            evaluate: Whether to evaluate questions
            diversity_factor: How much to prioritize diverse contexts (0-1)
            max_concurrent: Maximum number of concurrent generation tasks
            timeout_per_question: Timeout in seconds for each question generation
            
        Returns:
            Tuple of (List of Question objects, evaluation results)
        """
        start_time = time.time()
        
        if question_types is None:
            question_types = [QuestionType.MULTIPLE_CHOICE]
        
        # Track failures to ensure we keep trying until we get enough questions
        questions = []
        failed_questions = []
        failures = 0
        max_failures = num_questions * 2  # Allow up to twice as many failures as requested questions
        
        # Used content tracking for diversity
        used_content_ids = set()
        used_topics = set()
        generated_topics = set()
        
        # Performance tracking
        perf_metrics = {
            "context_retrieval_time": 0,
            "total_generation_time": 0,
            "evaluation_time": 0,
            "question_generation_attempts": 0,
            "concurrent_tasks_peak": 0
        }
        
        # First, retrieve diverse contexts for questions
        context_start = time.time()
        diverse_contexts = await self._retrieve_diverse_contexts(topic_or_query, num_questions * 2)
        perf_metrics["context_retrieval_time"] = time.time() - context_start
        
        # Create tasks for concurrent execution - limit concurrency for stability
        pending_tasks = []
        context_assignments = {}  # Map task to context
        task_start_times = {}     # Track when each task started
        
        # Initialize with context-specific questions - control concurrency
        initial_batch = min(num_questions, max_concurrent)
        logger.info(f"Starting initial batch of {initial_batch} question tasks")
        
        for i in range(initial_batch):
            if i < len(diverse_contexts):
                # Use a specific diverse context
                context = diverse_contexts[i]
                subtopic = context.get("subtopic", topic_or_query)
                question_type = question_types[i % len(question_types)]
                
                task = asyncio.create_task(
                    self.generate_one_question_async(
                        topic_or_query=subtopic,
                        question_type=question_type,
                        difficulty=difficulty,
                        evaluate=evaluate,
                        max_retries=1  # Limited retries for speed
                    )
                )
                task_start_times[task] = time.time()
                context_assignments[task] = context
            else:
                # Fallback to general topic
                question_type = question_types[i % len(question_types)]
                task = asyncio.create_task(
                    self.generate_one_question_async(
                        topic_or_query=topic_or_query,
                        question_type=question_type,
                        difficulty=difficulty,
                        evaluate=evaluate,
                        max_retries=1
                    )
                )
                task_start_times[task] = time.time()
            
            pending_tasks.append(task)
            perf_metrics["question_generation_attempts"] += 1
        
        perf_metrics["concurrent_tasks_peak"] = len(pending_tasks)
        
        # Process completed tasks and add new ones as needed
        all_evaluation_results = []
        
        try:
            while pending_tasks and len(questions) < num_questions and failures < max_failures:
                # Check for timeout on any tasks
                current_time = time.time()
                timed_out_tasks = []
                
                for task in pending_tasks:
                    if current_time - task_start_times.get(task, current_time) > timeout_per_question:
                        logger.warning(f"Task timed out after {timeout_per_question}s")
                        timed_out_tasks.append(task)
                
                # Cancel timed out tasks
                for task in timed_out_tasks:
                    if not task.done():
                        task.cancel()
                    pending_tasks.remove(task)
                    failures += 1
                    failed_questions.append((None, {"error": "Generation timed out"}, "Timeout"))
                
                if not pending_tasks:
                    break
                
                # Wait for the next completed task with timeout
                try:
                    done, pending_set = await asyncio.wait(
                        pending_tasks, 
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=5.0  # Short timeout to check for cancellations
                    )
                    
                    # Convert pending set back to list to maintain consistency
                    pending_tasks = list(pending_set)
                    
                    # If no tasks completed within timeout, continue checking
                    if not done:
                        continue
                    
                    # Process completed tasks
                    for task in done:
                        try:
                            question, evaluation = task.result()
                            task_duration = time.time() - task_start_times.get(task, time.time())
                            perf_metrics["total_generation_time"] += task_duration
                            
                            if question:
                                # Check if this question covers content we already have
                                content_id = question.source_content_id
                                question_topic = self._extract_question_topic(question.question_text)
                                
                                # Calculate similarity to existing questions for better diversity
                                similar_to_existing = False
                                for existing_topic in generated_topics:
                                    if self._text_similarity(question_topic, existing_topic) > 0.6:
                                        similar_to_existing = True
                                        break
                                
                                # Apply diversity control
                                if (content_id in used_content_ids or similar_to_existing) and random.random() < diversity_factor:
                                    # Skip this question as it covers similar content
                                    logger.info(f"Skipping similar question about '{question_topic}' for diversity")
                                    failed_questions.append((question, evaluation, "Similar content already covered"))
                                    failures += 1
                                else:
                                    # Add the question
                                    logger.info(f"Adding question about '{question_topic}'")
                                    questions.append(question)
                                    all_evaluation_results.append(evaluation)
                                    
                                    # Track used content
                                    if content_id:
                                        used_content_ids.add(content_id)
                                    if question_topic:
                                        generated_topics.add(question_topic)
                            else:
                                # Question failed or was rejected by evaluation
                                failures += 1
                                reason = "Unknown failure"
                                if evaluation and "error" in evaluation:
                                    reason = evaluation["error"]
                                elif evaluation and "reasoning" in evaluation:
                                    reason = evaluation["reasoning"]
                                logger.warning(f"Question generation failed: {reason}")
                                failed_questions.append((None, evaluation, reason))
                                
                        except asyncio.CancelledError:
                            logger.warning("Task was cancelled")
                            failures += 1
                            failed_questions.append((None, {"error": "Task cancelled"}, "Cancelled"))
                        except Exception as e:
                            logger.error(f"Error processing task result: {e}")
                            failures += 1
                            failed_questions.append((None, {"error": f"Processing error: {str(e)}"}, "Error"))
                        
                        # Add a new task if we need more questions and haven't hit max concurrency
                        if (len(questions) < num_questions and 
                            failures < max_failures and 
                            len(pending_tasks) < max_concurrent):
                            
                            # Pick a new context if available
                            next_context_idx = len(questions) + failures
                            
                            if next_context_idx < len(diverse_contexts):
                                # Use a context that hasn't been used yet
                                unused_contexts = [
                                    ctx for ctx in diverse_contexts 
                                    if ctx.get("content_id") not in used_content_ids
                                ]
                                
                                if unused_contexts:
                                    # Prioritize unused contexts for diversity
                                    context = unused_contexts[0]
                                    subtopic = context.get("subtopic", topic_or_query)
                                else:
                                    # Fall back to the next context in the list
                                    context = diverse_contexts[next_context_idx % len(diverse_contexts)]
                                    subtopic = context.get("subtopic", topic_or_query)
                                
                                question_type = question_types[next_context_idx % len(question_types)]
                                
                                new_task = asyncio.create_task(
                                    self.generate_one_question_async(
                                        topic_or_query=subtopic,
                                        question_type=question_type,
                                        difficulty=difficulty,
                                        evaluate=evaluate,
                                        max_retries=1
                                    )
                                )
                                task_start_times[new_task] = time.time()
                                context_assignments[new_task] = context
                            else:
                                # Fallback to general topic with variation
                                question_type = question_types[next_context_idx % len(question_types)]
                                
                                # Create variation of the topic for more diversity
                                topic_variations = self._generate_topic_variations(topic_or_query, 1)
                                variation = topic_variations[0] if topic_variations else topic_or_query
                                
                                new_task = asyncio.create_task(
                                    self.generate_one_question_async(
                                        topic_or_query=variation,
                                        question_type=question_type,
                                        difficulty=difficulty, 
                                        evaluate=evaluate,
                                        max_retries=1
                                    )
                                )
                                task_start_times[new_task] = time.time()
                                
                            pending_tasks.append(new_task)
                            perf_metrics["question_generation_attempts"] += 1
                            perf_metrics["concurrent_tasks_peak"] = max(
                                perf_metrics["concurrent_tasks_peak"], 
                                len(pending_tasks)
                            )
                
                except asyncio.TimeoutError:
                    logger.debug("Wait timeout, continuing loop")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in question generation loop: {e}")
        finally:
            # Cancel any remaining tasks
            for task in pending_tasks:
                if not task.done():
                    task.cancel()
        
        # Sort questions by difficulty (if we have that info)
        # This produces a nice experience where questions get progressively harder
        try:
            questions.sort(key=lambda q: {
                DifficultyLevel.EASY: 0,
                DifficultyLevel.MEDIUM: 1,
                DifficultyLevel.HARD: 2
            }.get(q.difficulty, 1))
        except Exception as e:
            logger.warning(f"Error sorting questions by difficulty: {e}")
        
        # Update statistics
        self._stats["total_questions"] += len(questions)
        self._stats["failed_questions"] += failures
        
        # Complete performance metrics
        total_time = time.time() - start_time
        perf_metrics["total_time"] = total_time
        perf_metrics["questions_per_second"] = len(questions) / total_time if total_time > 0 else 0
        
        # Create evaluation summary
        evaluation_summary = {
            "questions_evaluated": len(all_evaluation_results),
            "questions_passed": len(questions),
            "questions_failed": failures,
            "average_score": sum(e.get("score", 0) for e in all_evaluation_results) / max(1, len(all_evaluation_results)),
            "failed_details": [{"reason": reason, "evaluation": eval} for _, eval, reason in failed_questions if eval],
            "performance": perf_metrics
        }
        
        # Log completion information
        logger.info(f"Generation completed: {len(questions)} questions in {total_time:.2f}s ({perf_metrics['questions_per_second']:.2f} q/s)")
        
        return questions[:num_questions], evaluation_summary  # Ensure we don't return more than requested
    
    async def _retrieve_diverse_contexts(self, topic_or_query: str, num_contexts: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve diverse contexts for questions with improved diversity controls.
        
        Args:
            topic_or_query: Main topic or query
            num_contexts: Number of diverse contexts to retrieve
            
        Returns:
            List of context dictionaries with subtopics
        """
        if not self.retrieval_engine:
            logger.error("No retrieval engine available for diversity")
            return [{"subtopic": topic_or_query} for _ in range(num_contexts)]
            
        try:
            # Get search results - increased limit for better diversity sampling
            search_results = await self.retrieval_engine.search(
                query=topic_or_query,
                mode=SearchMode.LEXICAL_ONLY,
                limit=num_contexts * 3  # Get significantly more for diversity
            )
            
            if not search_results:
                logger.warning(f"No search results for diversity: {topic_or_query}")
                return [{"subtopic": topic_or_query} for _ in range(num_contexts)]
            
            # Extract diverse contexts
            diverse_contexts = []
            
            # Group by content_id to avoid excessive duplication
            grouped_results = {}
            
            for result in search_results:
                content_id = result.content_id
                if content_id not in grouped_results:
                    grouped_results[content_id] = []
                grouped_results[content_id].append(result)
            
            # STRATEGY 1: Take chunks from different sections of the document
            # Sort all results by chunk_index to get a sense of document flow
            all_sorted_results = sorted(search_results, key=lambda x: x.chunk_index)
            
            # Divide document into sections and sample from each
            if all_sorted_results:
                total_chunks = max(r.chunk_index for r in all_sorted_results) + 1
                
                # Divide document into segments and get a sample from each
                segment_size = max(1, total_chunks // num_contexts)
                
                for i in range(0, total_chunks, segment_size):
                    segment_end = min(total_chunks, i + segment_size)
                    segment_results = [r for r in all_sorted_results if i <= r.chunk_index < segment_end]
                    
                    if segment_results:
                        # Take the chunk with highest relevance in this segment
                        best_result = max(segment_results, key=lambda x: x.similarity_score)
                        
                        # Extract useful subtopic from the content text
                        subtopic = self._extract_subtopic(best_result.chunk_text, topic_or_query)
                        
                        diverse_contexts.append({
                            "content_id": best_result.content_id,
                            "text": best_result.chunk_text,
                            "subtopic": subtopic,
                            "similarity": best_result.similarity_score,
                            "chunk_index": best_result.chunk_index,
                            "section": f"Section {i // segment_size + 1}"
                        })
            
            # STRATEGY 2: Ensure topical diversity by analyzing content
            # Take the best chunk from each content group with distinct topics
            for content_id, results in grouped_results.items():
                # Skip if we already have a context from this content via strategy 1
                if any(c.get("content_id") == content_id for c in diverse_contexts):
                    continue
                    
                best_result = max(results, key=lambda x: x.similarity_score)
                
                # Extract useful subtopic
                subtopic = self._extract_subtopic(best_result.chunk_text, topic_or_query)
                
                # Check if we already have a similar subtopic
                if not any(self._text_similarity(c.get("subtopic", ""), subtopic) > 0.7 for c in diverse_contexts):
                    diverse_contexts.append({
                        "content_id": content_id,
                        "text": best_result.chunk_text,
                        "subtopic": subtopic,
                        "similarity": best_result.similarity_score,
                        "chunk_index": best_result.chunk_index,
                        "source": "content_diversity"
                    })
            
            # Sort by relevance (similarity score)
            diverse_contexts = sorted(diverse_contexts, key=lambda x: x.get("similarity", 0), reverse=True)
            
            # If we still need more contexts, generate variations of the topic
            if len(diverse_contexts) < num_contexts:
                remaining = num_contexts - len(diverse_contexts)
                logger.info(f"Adding {remaining} generated topic variations for diversity")
                
                # Generate topic variations
                variations = self._generate_topic_variations(topic_or_query, remaining)
                
                for i, variation in enumerate(variations):
                    diverse_contexts.append({
                        "subtopic": variation,
                        "text": "",
                        "similarity": 0.5,
                        "source": "generated_variation"
                    })
            
            return diverse_contexts[:num_contexts]
            
        except Exception as e:
            logger.error(f"Error retrieving diverse contexts: {e}")
            return [{"subtopic": topic_or_query} for _ in range(num_contexts)]
    
    def _text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate simple text similarity between two strings.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score (0-1)
        """
        # Simple word overlap ratio
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        overlap = len(words1.intersection(words2))
        total = len(words1.union(words2))
        
        return overlap / total if total > 0 else 0.0
        
    def _generate_topic_variations(self, topic: str, count: int) -> List[str]:
        """
        Generate variations of a topic for improved diversity.
        
        Args:
            topic: Base topic
            count: Number of variations to generate
            
        Returns:
            List of topic variations
        """
        # Simple implementation: Add prefixes for different aspects
        prefixes = [
            "Key concepts in", "Introduction to", "Advanced topics in", 
            "Applications of", "History of", "Future of", 
            "Controversies in", "Examples of", "Analysis of",
            "Comparison of", "Benefits of", "Limitations of"
        ]
        
        variations = []
        for i in range(min(count, len(prefixes))):
            variations.append(f"{prefixes[i]} {topic}")
            
        # If we need more variations, add numbered aspects
        for i in range(len(variations), count):
            variations.append(f"Aspect {i+1} of {topic}")
            
        return variations
    
    def _extract_subtopic(self, text: str, main_topic: str) -> str:
        """
        Extract a subtopic from text content.
        
        Args:
            text: The content text
            main_topic: The main topic
            
        Returns:
            A subtopic string
        """
        # Extract the first sentence as a simple approach
        sentences = text.split('.')
        if sentences:
            first_sentence = sentences[0].strip()
            if len(first_sentence) > 10:
                return first_sentence
                
        # Fallback to the main topic
        return main_topic
    
    def _extract_question_topic(self, question_text: str, max_length: int = 75) -> str:
        """Extracts a concise topic phrase from the question text for diversity checking."""
        if not question_text:
            return ""

        # Normalize: lowercase, remove punctuation (except hyphens if part of words)
        text = question_text.lower()
        text = re.sub(r'[^\w\s-]', '', text) # Keep words, spaces, hyphens

        # Tokenize and remove stopwords and very short words
        words = [word for word in text.split() if word not in self._PREDEFINED_STOPWORDS and len(word) > 2]

        topic_phrase = " ".join(words)

        # Fallback if all words are stopwords or too short
        if not topic_phrase:
            original_words = re.sub(r'[^\w\s-]', '', question_text.lower()).split()
            non_leading_stopwords = []
            leading_stopwords_passed = False
            # Try to skip leading common question words/stopwords
            for i, word in enumerate(original_words):
                if not leading_stopwords_passed and word in self._PREDEFINED_STOPWORDS and i < 3: # Check first few words
                    continue
                leading_stopwords_passed = True
                non_leading_stopwords.append(word)
            
            topic_phrase = " ".join(non_leading_stopwords)
            if not topic_phrase: # Ultimate fallback: first few words of original
                 topic_phrase = " ".join(original_words[:5])


        return topic_phrase[:max_length].strip()
    
    async def generate_quiz(self,
                      title: str,
                      description: str,
                      topic_or_query: str,
                      num_questions: int = 5,
                      question_types: List[QuestionType] = None,
                      difficulty: DifficultyLevel = DifficultyLevel.MEDIUM,
                      evaluate: bool = True,
                      min_quality_score: float = 0.7,
                      diversity_factor: float = 0.7,
                      timeout: float = 120.0,  # Overall timeout for the quiz
                      timeout_per_question: Optional[float] = None) -> Tuple[Quiz, Dict[str, Any]]:
        """
        Generate a complete quiz from a topic or query with improved robustness.
        
        Args:
            title: Quiz title
            description: Quiz description
            topic_or_query: Topic or query for questions
            num_questions: Number of questions to generate
            question_types: Types of questions to generate
            difficulty: Difficulty level
            evaluate: Whether to evaluate questions
            min_quality_score: Minimum quality score for quiz (0-1)
            diversity_factor: How much to prioritize diverse contexts (0-1)
            timeout: Maximum time in seconds for quiz generation
            timeout_per_question: Optional timeout in seconds for each individual question generation.
                                  If None, it's derived from the overall timeout and num_questions.
            
        Returns:
            Tuple of (Completed Quiz object, evaluation results)
        """
        if question_types is None:
            question_types = [QuestionType.MULTIPLE_CHOICE]
        
        start_time = time.time()
        generation_stats = {
            "start_time": start_time,
            "topic": topic_or_query,
            "requested_questions": num_questions,
            "phases": {}
        }
        
        try:
            # Phase 1: Generate questions with evaluation
            phase_start = time.time()
            logger.info(f"Starting question generation for topic: {topic_or_query}")
            
            # Use asyncio.wait_for to apply a timeout to the entire operation
            try:
                questions, evaluation_results = await asyncio.wait_for(
                    self.generate_multiple_questions(
                        topic_or_query=topic_or_query,
                        num_questions=num_questions,
                        question_types=question_types,
                        difficulty=difficulty,
                        evaluate=evaluate,
                        diversity_factor=diversity_factor,
                        # Use provided timeout_per_question or derive it
                        timeout_per_question=timeout_per_question if timeout_per_question is not None 
                                             else min(30.0, timeout / max(1, num_questions))
                    ),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Quiz generation timed out after {timeout} seconds")
                # Get whatever questions we have so far (recovery mechanism)
                # The generate_multiple_questions should have been cancelled, so we'll create a partial quiz
                
                # Create a minimal quiz with any questions that might have been generated
                # This is a placeholder to be replaced with proper recovery logic
                questions = []  # In a real implementation, we would try to salvage any completed questions
                evaluation_results = {"error": f"Quiz generation timed out after {timeout} seconds"}
            except Exception as e:
                logger.error(f"Error in question generation: {str(e)}")
                questions = []
                evaluation_results = {"error": f"Question generation failed: {str(e)}"}
            
            generation_stats["phases"]["question_generation"] = {
                "duration": time.time() - phase_start,
                "questions_generated": len(questions),
                "evaluation_results": evaluation_results.get("performance", {})
            }
            
            # Phase 2: Create quiz object
            phase_start = time.time()
            
            # Generate a better title if none provided
            if not title:
                if len(questions) > 0:
                    title = f"Quiz on {topic_or_query}"
                    # Try to extract a more specific title from the questions
                    topics = set()
                    for question in questions:
                        topic = self._extract_question_topic(question.question_text)
                        if topic:
                            topics.add(topic)
                    
                    if len(topics) > 0:
                        common_topics = ", ".join(list(topics)[:3])
                        title = f"Quiz on {common_topics}"
                else:
                    title = f"Quiz on {topic_or_query}"
            
            # Check if we got any questions before creating quiz
            if not questions:
                # No questions were generated - handle gracefully
                end_time = time.time()
                generation_time = end_time - start_time
                
                error_message = f"No questions could be generated for topic: {topic_or_query}"
                logger.warning(error_message)
                
                # Return error information without creating a Quiz object
                generation_stats["total_duration"] = generation_time
                generation_stats["questions_per_second"] = 0
                evaluation_results.update({
                    "error": error_message,
                    "warning": "No content found or questions could not be generated",
                    "generation_stats": generation_stats
                })
                
                # Instead of returning a Quiz object, raise an exception or return None
                # For now, let's raise a descriptive exception
                raise ValueError(f"Quiz generation failed: {error_message}")
            
            # Create quiz with available questions (even if fewer than requested)
            quiz_id = str(uuid.uuid4())
            quiz = Quiz(
                id=quiz_id,
                title=title,
                description=description or f"Generated quiz about {topic_or_query}",
                questions=questions,
                created_at=datetime.now()
            )
            
            generation_stats["phases"]["quiz_creation"] = {
                "duration": time.time() - phase_start
            }
            
            # Phase 3: Evaluate the quiz as a whole if we have questions
            if evaluate and questions:
                phase_start = time.time()
                
                try:
                    # Get contexts for all questions using cached retrieval
                    contexts = {}
                    source_content_ids = set()
                    
                    for question in questions:
                        if question.source_content_id:
                            source_content_ids.add(question.source_content_id)
                    
                    # Retrieve contexts for evaluation using cached context retrieval
                    if self.retrieval_engine and source_content_ids:
                        for content_id in source_content_ids:
                            # _get_cached_context is async, so we need to await it
                            search_results_list = await self._get_cached_context(f"content:{content_id}", limit=1)
                            
                            if search_results_list: # Check if list is not empty
                                contexts[content_id] = search_results_list[0].text
                    
                    # Only do quiz-level evaluation if we have contexts
                    if contexts:
                        quiz_eval = self.evaluator.evaluate_quiz(quiz, contexts)
                        evaluation_results["quiz_evaluation"] = quiz_eval
                        
                        # Check if quiz meets minimum quality threshold
                        if quiz_eval["score"] < min_quality_score:
                            logger.warning(f"Quiz quality score {quiz_eval['score']} below threshold {min_quality_score}")
                            evaluation_results["warning"] = f"Quiz quality score {quiz_eval['score']:.2f} below threshold {min_quality_score}"
                    else:
                        evaluation_results["warning"] = "Unable to perform quiz-level evaluation: no contexts available"
                        
                except Exception as e:
                    logger.error(f"Error in quiz evaluation: {str(e)}")
                    evaluation_results["error_quiz_eval"] = f"Quiz evaluation failed: {str(e)}"
                
                generation_stats["phases"]["quiz_evaluation"] = {
                    "duration": time.time() - phase_start,
                    "contexts_found": len(contexts)
                }
            
            # Check if we have enough questions
            if len(questions) < num_questions:
                logger.warning(f"Generated only {len(questions)}/{num_questions} requested questions")
                evaluation_results["warning_count"] = f"Generated only {len(questions)}/{num_questions} questions"
            
            # Update statistics
            end_time = time.time()
            generation_time = end_time - start_time
            
            generation_stats["total_duration"] = generation_time
            generation_stats["questions_per_second"] = len(questions) / generation_time if generation_time > 0 else 0
            evaluation_results["generation_stats"] = generation_stats
            
            self._stats["quizzes_generated"] += 1
            self._stats["total_generation_time"] += generation_time
            
            logger.info(f"Quiz generation completed in {generation_time:.2f}s with {len(questions)} questions")
            
            return quiz, evaluation_results
            
        except Exception as e:
            # Final fallback for unexpected errors
            end_time = time.time()
            generation_time = end_time - start_time
            
            logger.error(f"Unexpected error in quiz generation: {str(e)}", exc_info=True)
            
            # Don't try to create an empty quiz - just re-raise the exception
            # The calling code should handle the error appropriately
            raise e


# Global orchestrator instance
_quiz_orchestrator = None


def get_quiz_orchestrator() -> QuizOrchestrator:
    """Get the global quiz orchestrator instance."""
    global _quiz_orchestrator
    if _quiz_orchestrator is None:
        _quiz_orchestrator = QuizOrchestrator()
    return _quiz_orchestrator
