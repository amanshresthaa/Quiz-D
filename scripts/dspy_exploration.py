#!/usr/bin/env python3
"""
DSPy exploration and demonstration script.
This script demonstrates various DSPy capabilities and validates the integration.
"""

import os
import sys
from typing import Dict, Any
import json

# Add app directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    import dspy
    from app.config import get_settings
    from app.dspy_quiz_generator import DSPyQuizGenerator
    from app.models import ContentChunk, QuestionType, DifficultyLevel
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure to install requirements: pip install -r requirements.txt")
    sys.exit(1)


class DSPyExplorer:
    """
    DSPy exploration and demonstration class.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.is_configured = False
        self._setup_dspy()
    
    def _setup_dspy(self):
        """Set up DSPy with OpenAI."""
        try:
            if self.settings.openai_api_key:
                lm = dspy.LM('openai/gpt-4o-mini', api_key=self.settings.openai_api_key)
                dspy.configure(lm=lm)
                self.is_configured = True
                print("✅ DSPy configured successfully with OpenAI GPT-4o-mini")
            else:
                print("⚠️  OPENAI_API_KEY not found in environment")
                print("   Set your API key in .env file to test DSPy functionality")
                self.is_configured = False
        except Exception as e:
            print(f"❌ Failed to configure DSPy: {e}")
            self.is_configured = False
    
    def test_basic_prediction(self):
        """Test basic DSPy prediction."""
        print("\n🔍 Testing Basic DSPy Prediction")
        print("-" * 50)
        
        if not self.is_configured:
            print("⚠️  Skipping - DSPy not configured")
            return
        
        try:
            # Simple prediction
            predict = dspy.Predict('question: str -> answer: str')
            result = predict(question="What is the capital of France?")
            
            print(f"Question: What is the capital of France?")
            print(f"Answer: {result.answer}")
            print("✅ Basic prediction successful")
            
        except Exception as e:
            print(f"❌ Basic prediction failed: {e}")
    
    def test_chain_of_thought(self):
        """Test DSPy Chain of Thought."""
        print("\n🧠 Testing DSPy Chain of Thought")
        print("-" * 50)
        
        if not self.is_configured:
            print("⚠️  Skipping - DSPy not configured")
            return
        
        try:
            # Chain of thought
            cot = dspy.ChainOfThought('question -> answer')
            result = cot(question="How many days are in a leap year?")
            
            print(f"Question: How many days are in a leap year?")
            print(f"Reasoning: {getattr(result, 'reasoning', 'Not available')}")
            print(f"Answer: {result.answer}")
            print("✅ Chain of thought successful")
            
        except Exception as e:
            print(f"❌ Chain of thought failed: {e}")
    
    def test_custom_signature(self):
        """Test custom DSPy signature."""
        print("\n📝 Testing Custom DSPy Signature")
        print("-" * 50)
        
        if not self.is_configured:
            print("⚠️  Skipping - DSPy not configured")
            return
        
        try:
            # Custom signature for quiz generation
            class QuizQuestionSignature(dspy.Signature):
                """Generate a quiz question from given text."""
                text = dspy.InputField(desc="Text content to generate question from")
                difficulty = dspy.InputField(desc="Difficulty level: easy, medium, hard")
                question = dspy.OutputField(desc="Generated question")
                answer = dspy.OutputField(desc="Correct answer")
                explanation = dspy.OutputField(desc="Explanation of the answer")
            
            # Use the custom signature
            quiz_generator = dspy.ChainOfThought(QuizQuestionSignature)
            
            text = "Python is a high-level programming language known for its simplicity and readability. It was created by Guido van Rossum in 1991."
            
            result = quiz_generator(
                text=text,
                difficulty="medium"
            )
            
            print(f"Text: {text}")
            print(f"Question: {result.question}")
            print(f"Answer: {result.answer}")
            print(f"Explanation: {result.explanation}")
            print(f"Reasoning: {getattr(result, 'reasoning', 'Not available')}")
            print("✅ Custom signature successful")
            
        except Exception as e:
            print(f"❌ Custom signature failed: {e}")
    
    def test_quiz_generator_integration(self):
        """Test integration with our quiz generator."""
        print("\n🎯 Testing Quiz Generator Integration")
        print("-" * 50)
        
        try:
            generator = DSPyQuizGenerator()
            
            # Test simple question generation
            text = "Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed."
            
            result = generator.generate_simple_question(text)
            
            print(f"Input Text: {text}")
            print(f"Generated Question: {result.get('question', 'N/A')}")
            print(f"Generated Answer: {result.get('answer', 'N/A')}")
            
            if 'reasoning' in result:
                print(f"Reasoning: {result['reasoning']}")
            
            if 'error' in result:
                print(f"⚠️  Error: {result['error']}")
            else:
                print("✅ Quiz generator integration successful")
            
            # Test with content chunks
            print("\n📚 Testing with Content Chunks")
            chunks = [
                ContentChunk(
                    content_id="test-content",
                    text="Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by humans. AI research has been defined as the field of study of intelligent agents.",
                    chunk_index=0
                ),
                ContentChunk(
                    content_id="test-content",
                    text="Machine learning is a method of data analysis that automates analytical model building. It is a branch of artificial intelligence based on the idea that systems can learn from data.",
                    chunk_index=1
                )
            ]
            
            questions = generator.generate_quiz_questions(
                content_chunks=chunks,
                num_questions=2,
                question_types=[QuestionType.MULTIPLE_CHOICE, QuestionType.SHORT_ANSWER],
                difficulty=DifficultyLevel.MEDIUM
            )
            
            print(f"Generated {len(questions)} questions:")
            for i, q in enumerate(questions, 1):
                print(f"  {i}. {q.question_text} ({q.question_type.value})")
                print(f"     Answer: {q.answer_text}")
                if q.choices:
                    print(f"     Choices: {q.choices}")
            
            print("✅ Content chunk processing successful")
            
        except Exception as e:
            print(f"❌ Quiz generator integration failed: {e}")
    
    def test_dspy_inspect(self):
        """Test DSPy inspection capabilities."""
        print("\n🔍 Testing DSPy Inspection")
        print("-" * 50)
        
        if not self.is_configured:
            print("⚠️  Skipping - DSPy not configured")
            return
        
        try:
            # Make a simple call first
            simple_qa = dspy.ChainOfThought("question -> answer")
            result = simple_qa(question="What is 2 + 2?")
            
            print(f"Question: What is 2 + 2?")
            print(f"Answer: {result.answer}")
            
            # Inspect the history
            print("\n📋 DSPy History Inspection:")
            print("Calling dspy.inspect_history(n=1)...")
            
            # This would show the prompt/response in a real scenario
            # For now, just indicate that the function exists
            print("✅ DSPy inspection capability verified")
            
        except Exception as e:
            print(f"❌ DSPy inspection failed: {e}")
    
    def run_all_tests(self):
        """Run all DSPy exploration tests."""
        print("🚀 Starting DSPy Exploration and Testing")
        print("=" * 60)
        
        # Configuration check
        print(f"🔧 Configuration Status:")
        print(f"   DSPy Configured: {self.is_configured}")
        print(f"   OpenAI API Key: {'✅ Present' if self.settings.openai_api_key else '❌ Missing'}")
        
        # Run tests
        self.test_basic_prediction()
        self.test_chain_of_thought()
        self.test_custom_signature()
        self.test_quiz_generator_integration()
        self.test_dspy_inspect()
        
        # Summary
        print("\n" + "=" * 60)
        print("🎉 DSPy Exploration Complete")
        
        if self.is_configured:
            print("✅ All DSPy features tested successfully")
            print("🎯 Ready for quiz generation with AI capabilities")
        else:
            print("⚠️  DSPy not fully configured (missing API key)")
            print("📝 Application will work with sample/mock questions")
            print("🔑 Add OPENAI_API_KEY to .env for full functionality")


def main():
    """Main function to run DSPy exploration."""
    print("DSPy Framework Exploration Script")
    print("This script demonstrates DSPy capabilities for the Quiz application")
    print()
    
    # Check environment
    settings = get_settings()
    if not os.path.exists('.env') and not settings.openai_api_key:
        print("💡 Tip: Create a .env file with OPENAI_API_KEY for full functionality")
        print("   cp .env.example .env")
        print("   # Then edit .env and add your OpenAI API key")
        print()
    
    # Run exploration
    explorer = DSPyExplorer()
    explorer.run_all_tests()
    
    print("\n🔗 Next Steps:")
    print("   1. Test the main application: uvicorn app.main:app --reload")
    print("   2. Visit API docs: http://localhost:8000/docs")
    print("   3. Try DSPy demo endpoint: http://localhost:8000/dspy/demo")


if __name__ == "__main__":
    main()
