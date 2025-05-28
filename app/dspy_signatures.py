"""
DSPy signatures for question generation tasks.
Defines the input and output fields for various question generation operations.
"""

import dspy
from typing import Literal, List, Dict


class QuizQuestionGen(dspy.Signature):
    """Generate a quiz question from given context."""
    
    context = dspy.InputField(desc="The text content to generate a question from")
    question = dspy.OutputField(desc="A clear, specific question based on the context")
    answer = dspy.OutputField(desc="The correct answer to the question")


class MultipleChoiceQuestionGen(dspy.Signature):
    """Generate a multiple-choice question from given context."""
    
    context = dspy.InputField(desc="The text content to generate a question from")
    question = dspy.OutputField(desc="A clear, specific multiple-choice question")
    answer = dspy.OutputField(desc="The correct answer option (one of the choices)")
    choices = dspy.OutputField(desc="List of 4 answer choices including the correct answer")
    explanation = dspy.OutputField(desc="Explanation of why the answer is correct")


class TrueFalseQuestionGen(dspy.Signature):
    """Generate a true/false question from given context."""
    
    context = dspy.InputField(desc="The text content to generate a question from")
    question = dspy.OutputField(desc="A statement that is either true or false according to the context")
    answer = dspy.OutputField(desc="The correct answer: either 'True' or 'False'")
    explanation = dspy.OutputField(desc="Explanation of why the statement is true or false")


class ShortAnswerQuestionGen(dspy.Signature):
    """Generate a short-answer question from given context."""
    
    context = dspy.InputField(desc="The text content to generate a question from")
    question = dspy.OutputField(desc="A clear question requiring a short answer (1-5 words)")
    answer = dspy.OutputField(desc="The correct short answer to the question")
    explanation = dspy.OutputField(desc="Explanation of why this is the correct answer")


class EssayQuestionGen(dspy.Signature):
    """Generate an essay/open-ended question from given context."""
    
    context = dspy.InputField(desc="The text content to generate a question from")
    question = dspy.OutputField(desc="An open-ended question that requires an essay-style response")
    suggested_answer_points = dspy.OutputField(desc="Key points that should be included in a good answer")


class QualityChecker(dspy.Signature):
    """Evaluate the quality of a generated question-answer pair."""
    
    context = dspy.InputField(desc="The original context used to generate the question")
    question = dspy.InputField(desc="The generated question")
    answer = dspy.InputField(desc="The generated answer")
    is_high_quality = dspy.OutputField(desc="Whether the Q&A pair is high quality (True/False)")
    issues = dspy.OutputField(desc="List of identified issues with the Q&A pair, if any")
    improved_question = dspy.OutputField(desc="Improved version of the question if needed")
    improved_answer = dspy.OutputField(desc="Improved version of the answer if needed")


class QuestionEvaluator(dspy.Signature):
    """Evaluate a question-answer pair against the source context."""
    
    context = dspy.InputField(desc="The original source text used to generate the question")
    question = dspy.InputField(desc="The question to evaluate")
    answer = dspy.InputField(desc="The suggested answer to evaluate")
    choices = dspy.InputField(desc="The multiple choice options, if applicable")
    
    answerable = dspy.OutputField(desc="Is the question directly answerable from the context? (True/False)")
    correct = dspy.OutputField(desc="Is the answer correct based on the context? (True/False)")
    score = dspy.OutputField(desc="Evaluation score from 0.0 to 1.0 where 1.0 is perfect")
    reasoning = dspy.OutputField(desc="Step-by-step reasoning for the evaluation")
    suggested_improvement = dspy.OutputField(desc="Suggestion for improving the question or answer if needed")
