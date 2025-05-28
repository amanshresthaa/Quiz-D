"""
DSPy module for quiz generation using language models.
This module demonstrates DSPy capabilities and will be extended in future sprints.
"""

import dspy
import asyncio
import os
from typing import List, Dict, Any
import json
import uuid
from datetime import datetime

from app.models import Question, Quiz, QuestionType, DifficultyLevel, ContentChunk
from app.config import get_settings


class QuizGenerationSignature(dspy.Signature):
    """
    DSPy signature for generating quiz questions from content.
    """
    context = dspy.InputField(desc="The content text to generate questions from")
    num_questions = dspy.InputField(desc="Number of questions to generate")
    question_types = dspy.InputField(desc="Types of questions to generate (multiple_choice, true_false, short_answer)")
    difficulty = dspy.InputField(desc="Difficulty level (easy, medium, hard)")
    questions_json = dspy.OutputField(desc="Generated questions in JSON format with fields: question_text, question_type, answer_text, choices (if applicable), explanation")


class SimpleQuestionGenerationSignature(dspy.Signature):
    """
    Simple DSPy signature for basic question generation demonstration.
    """
    text = dspy.InputField(desc="Text content to generate a question from")
    question = dspy.OutputField(desc="A question based on the text")
    answer = dspy.OutputField(desc="The answer to the question")


class DSPyQuizGenerator:
    """
    Quiz generation using DSPy modules.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._is_configured = False
        self._configure_dspy()
    
    def _configure_dspy(self):
        """Configure DSPy with language model."""
        try:
            # Check for OpenAI API key
            openai_key = getattr(self.settings, 'openai_api_key', None) or os.getenv('OPENAI_API_KEY')
            
            if openai_key:
                # Try to configure DSPy with OpenAI
                lm = dspy.LM('openai/gpt-4o-mini', api_key=openai_key)
                dspy.configure(lm=lm)
                self._is_configured = True
                print("✅ DSPy configured with OpenAI GPT-4o-mini")
            else:
                print("⚠️  DSPy not configured: OPENAI_API_KEY not found")
                print("   Set OPENAI_API_KEY environment variable or run: python configure_openai.py")
                self._is_configured = False
        except Exception as e:
            print(f"❌ Failed to configure DSPy: {e}")
            print("   Check your OpenAI API key and network connection")
            self._is_configured = False
    
    def is_available(self) -> bool:
        """Check if DSPy is properly configured."""
        return self._is_configured
    
    def generate_simple_question(self, text: str) -> Dict[str, str]:
        """
        Generate a simple question using DSPy (demonstration purpose).
        
        Args:
            text: Input text to generate question from
            
        Returns:
            Dict containing question and answer
        """
        if not self._is_configured:
            return {
                "question": "Sample question (DSPy not configured)?",
                "answer": "Sample answer",
                "error": "DSPy not configured - missing OpenAI API key"
            }
        
        try:
            # Use simple signature for demonstration
            generator = dspy.ChainOfThought(SimpleQuestionGenerationSignature)
            result = generator(text=text)
            
            return {
                "question": result.question,
                "answer": result.answer,
                "reasoning": getattr(result, 'reasoning', 'No reasoning available')
            }
        except Exception as e:
            return {
                "question": "Error generating question",
                "answer": "Error in generation",
                "error": str(e)
            }
    
    def generate_quiz_questions(self, content_chunks: List[ContentChunk], 
                               num_questions: int = 5,
                               question_types: List[QuestionType] = None,
                               difficulty: DifficultyLevel = DifficultyLevel.MEDIUM) -> List[Question]:
        """
        Generate quiz questions from content chunks using DSPy.
        
        Args:
            content_chunks: List of content chunks to generate questions from
            num_questions: Number of questions to generate
            question_types: Types of questions to generate
            difficulty: Difficulty level
            
        Returns:
            List[Question]: Generated questions
        """
        if not self._is_configured:
            # Return sample questions when DSPy is not configured
            return self._generate_sample_questions(content_chunks, num_questions, question_types, difficulty)
        
        if not question_types:
            question_types = [QuestionType.MULTIPLE_CHOICE]
        
        try:
            # Combine content from chunks
            context = "\n\n".join([chunk.text for chunk in content_chunks])
            
            # Prepare question types string
            types_str = ", ".join([qtype.value for qtype in question_types])
            
            # Use DSPy to generate questions
            generator = dspy.ChainOfThought(QuizGenerationSignature)
            result = generator(
                context=context,
                num_questions=str(num_questions),
                question_types=types_str,
                difficulty=difficulty.value
            )
            
            # Parse the JSON response
            try:
                questions_data = json.loads(result.questions_json)
                if not isinstance(questions_data, list):
                    questions_data = [questions_data]
            except json.JSONDecodeError:
                # Fallback to sample questions if JSON parsing fails
                return self._generate_sample_questions(content_chunks, num_questions, question_types, difficulty)
            
            # Convert to Question objects
            questions = []
            for i, q_data in enumerate(questions_data[:num_questions]):
                try:
                    question = Question(
                        id=str(uuid.uuid4()),
                        question_text=q_data.get('question_text', f'Question {i+1}'),
                        question_type=QuestionType(q_data.get('question_type', QuestionType.MULTIPLE_CHOICE.value)),
                        answer_text=q_data.get('answer_text', 'Answer'),
                        choices=q_data.get('choices'),
                        difficulty=difficulty,
                        explanation=q_data.get('explanation'),
                        source_content_id=content_chunks[0].content_id if content_chunks else None,
                        created_at=datetime.now()
                    )
                    questions.append(question)
                except Exception as e:
                    print(f"Error creating question {i+1}: {e}")
                    continue
            
            return questions
            
        except Exception as e:
            print(f"Error generating questions with DSPy: {e}")
            return self._generate_sample_questions(content_chunks, num_questions, question_types, difficulty)
    
    async def generate_quiz_questions_async(self, content_chunks: List[ContentChunk], 
                                           num_questions: int = 5,
                                           question_types: List[QuestionType] = None,
                                           difficulty: DifficultyLevel = DifficultyLevel.MEDIUM) -> List[Question]:
        """
        Async version of generate_quiz_questions for timeout compatibility.
        
        Args:
            content_chunks: List of content chunks to generate questions from
            num_questions: Number of questions to generate
            question_types: Types of questions to generate
            difficulty: Difficulty level
            
        Returns:
            List[Question]: Generated questions
        """
        # Run the sync method in a thread pool to make it async-compatible
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.generate_quiz_questions,
            content_chunks,
            num_questions,
            question_types,
            difficulty
        )
    
    def _generate_sample_questions(self, content_chunks: List[ContentChunk], 
                                   num_questions: int,
                                   question_types: List[QuestionType],
                                   difficulty: DifficultyLevel) -> List[Question]:
        """
        Generate sample questions when DSPy is not available.
        
        Args:
            content_chunks: Content chunks (used for source reference)
            num_questions: Number of questions to generate
            question_types: Types of questions
            difficulty: Difficulty level
            
        Returns:
            List[Question]: Sample questions
        """
        questions = []
        source_content_id = content_chunks[0].content_id if content_chunks else None
        
        for i in range(num_questions):
            question_type = question_types[i % len(question_types)] if question_types else QuestionType.MULTIPLE_CHOICE
            
            if question_type == QuestionType.MULTIPLE_CHOICE:
                question = Question(
                    id=str(uuid.uuid4()),
                    question_text=f"Sample multiple choice question {i+1} based on the provided content?",
                    question_type=QuestionType.MULTIPLE_CHOICE,
                    answer_text="Option A",
                    choices=["Option A", "Option B", "Option C", "Option D"],
                    difficulty=difficulty,
                    explanation="This is a sample explanation for the correct answer.",
                    source_content_id=source_content_id,
                    created_at=datetime.now()
                )
            elif question_type == QuestionType.TRUE_FALSE:
                question = Question(
                    id=str(uuid.uuid4()),
                    question_text=f"Sample true/false statement {i+1} about the content.",
                    question_type=QuestionType.TRUE_FALSE,
                    answer_text="True",
                    choices=["True", "False"],
                    difficulty=difficulty,
                    explanation="This is a sample explanation for why this statement is true.",
                    source_content_id=source_content_id,
                    created_at=datetime.now()
                )
            else:
                question = Question(
                    id=str(uuid.uuid4()),
                    question_text=f"Sample {question_type.value} question {i+1} about the content?",
                    question_type=question_type,
                    answer_text=f"Sample answer {i+1}",
                    difficulty=difficulty,
                    explanation="This is a sample explanation for the answer.",
                    source_content_id=source_content_id,
                    created_at=datetime.now()
                )
            
            questions.append(question)
        
        return questions


# Global DSPy quiz generator instance
dspy_quiz_generator = DSPyQuizGenerator()


def get_dspy_quiz_generator() -> DSPyQuizGenerator:
    """Get the global DSPy quiz generator instance."""
    return dspy_quiz_generator
