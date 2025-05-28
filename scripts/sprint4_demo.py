#!/usr/bin/env python
"""
Sprint 4 Demo Script: DSPy Question Generation
This script demonstrates the core functionality implemented in Sprint 4.
"""

import os
import sys
import asyncio
import time
from typing import List, Dict, Any
from pprint import pprint

# Ensure script can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import QuestionType, DifficultyLevel, Question, Quiz
from app.question_generation import get_question_generation_module
from app.retrieval_engine import get_retrieval_engine, SearchMode
from app.quiz_orchestrator import get_quiz_orchestrator


def print_section(title):
    """Print a section title."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80 + "\n")


def print_question(question, index=None):
    """Pretty print a question object."""
    prefix = f"Question {index}: " if index is not None else ""
    
    print(f"{prefix}{question.question_text}")
    
    if question.question_type == QuestionType.MULTIPLE_CHOICE:
        for i, choice in enumerate(question.choices):
            print(f"  {chr(65+i)}. {choice}")
    
    print(f"\nAnswer: {question.answer_text}")
    
    if question.explanation:
        print(f"Explanation: {question.explanation}")
    
    print()


async def main():
    """Main demo function."""
    print_section("DSPy Question Generation Demo (Sprint 4)")
    
    # Initialize modules
    retrieval_engine = get_retrieval_engine()
    qgen = get_question_generation_module(retrieval_engine)
    orchestrator = get_quiz_orchestrator()
    
    print("✅ All modules initialized successfully")
    
    # Demo 1: Generate a single question using direct context
    print_section("Demo 1: Generate a single question using direct context")
    
    context = """
    Python is a high-level, interpreted programming language created by Guido van Rossum and released in 1991. 
    It emphasizes code readability with its notable use of significant whitespace. Its language constructs and 
    object-oriented approach aim to help programmers write clear, logical code for small and large-scale projects.
    Python is dynamically typed and garbage-collected. It supports multiple programming paradigms, including 
    structured, object-oriented, and functional programming.
    """
    
    print("Generating multiple choice question...\n")
    mc_data = qgen.generate_question(context, QuestionType.MULTIPLE_CHOICE)
    mc_question = Question(id="demo-1", **mc_data)
    print_question(mc_question)
    
    print("Generating true/false question...\n")
    tf_data = qgen.generate_question(context, QuestionType.TRUE_FALSE)
    tf_question = Question(id="demo-2", **tf_data)
    print_question(tf_question)
    
    # Demo 2: Generate a question using retrieval
    print_section("Demo 2: Generate a question using retrieval")
    
    print("Retrieving context and generating question about 'machine learning'...\n")
    ml_question = qgen.generate_one_question(
        topic_or_query="What is machine learning?",
        question_type=QuestionType.MULTIPLE_CHOICE
    )
    
    if ml_question:
        print_question(ml_question)
    else:
        print("❌ Failed to generate question. Ensure content is ingested for this topic.")
    
    # Demo 3: Generate multiple questions concurrently
    print_section("Demo 3: Generate multiple questions concurrently")
    
    print("Generating 3 questions about 'artificial intelligence'...\n")
    start_time = time.time()
    
    ai_questions = await orchestrator.generate_multiple_questions(
        topic_or_query="artificial intelligence concepts and applications",
        num_questions=3,
        question_types=[
            QuestionType.MULTIPLE_CHOICE, 
            QuestionType.TRUE_FALSE,
            QuestionType.SHORT_ANSWER
        ],
        difficulty=DifficultyLevel.MEDIUM
    )
    
    end_time = time.time()
    
    print(f"Generated {len(ai_questions)} questions in {end_time - start_time:.2f} seconds\n")
    
    for i, question in enumerate(ai_questions):
        print_question(question, i+1)
    
    # Demo 4: Generate a complete quiz
    print_section("Demo 4: Generate a complete quiz")
    
    print("Generating a quiz about 'data science'...\n")
    start_time = time.time()
    
    quiz = await orchestrator.generate_quiz(
        title="Data Science Fundamentals",
        description="Test your knowledge of data science concepts",
        topic_or_query="fundamental concepts in data science",
        num_questions=3,
        question_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.SHORT_ANSWER],
        difficulty=DifficultyLevel.MEDIUM
    )
    
    end_time = time.time()
    
    print(f"Generated quiz '{quiz.title}' with {len(quiz.questions)} questions in {end_time - start_time:.2f} seconds\n")
    print(f"Description: {quiz.description}\n")
    
    for i, question in enumerate(quiz.questions):
        print_question(question, i+1)
    
    # Demo 5: Check statistics
    print_section("Demo 5: Generation Statistics")
    
    stats = orchestrator.get_statistics()
    pprint(stats)


if __name__ == "__main__":
    # Ensure OpenAI API key is set
    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set. Demo may use fallback sample questions.")
    
    # Run the demo
    asyncio.run(main())
