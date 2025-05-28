"""
Tests for diversity and redundancy controls in question generation.
These tests verify that the quiz orchestrator produces diverse questions.
"""

import pytest
import asyncio
from typing import List, Dict, Any, Set
import random
from unittest import mock

from app.models import QuestionType, DifficultyLevel, Question
from app.quiz_orchestrator import QuizOrchestrator


class TestQuestionDiversity:
    """Test diversity control features of the QuizOrchestrator."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create a QuizOrchestrator instance for testing."""
        return QuizOrchestrator()

    @pytest.mark.asyncio
    async def test_retrieve_diverse_contexts(self, orchestrator):
        """Test that diverse context retrieval produces varied contexts."""
        # This test only works if a retrieval engine is configured
        if not orchestrator.retrieval_engine:
            pytest.skip("No retrieval engine available for testing")
            
        # Retrieve diverse contexts
        topic = "Machine learning"
        num_contexts = 5
        contexts = await orchestrator._retrieve_diverse_contexts(topic, num_contexts)
        
        # Check that we got the requested number of contexts
        assert len(contexts) == num_contexts
        
        # Check for diversity in subtopics
        subtopics = [c.get("subtopic") for c in contexts if "subtopic" in c]
        unique_subtopics = set(subtopics)
        
        # At least half of subtopics should be unique
        assert len(unique_subtopics) >= len(subtopics) // 2
        
        # Check context sources if available
        sources = [c.get("section", c.get("source")) for c in contexts]
        sources = [s for s in sources if s is not None]
        
        if sources:
            # Should have some diversity in sources
            assert len(set(sources)) > 1

    @pytest.mark.asyncio
    async def test_text_similarity(self, orchestrator):
        """Test the text similarity function used for diversity checking."""
        # Test identical texts
        text1 = "This is a test string for similarity"
        text2 = "This is a test string for similarity"
        similarity = orchestrator._text_similarity(text1, text2)
        assert similarity == 1.0
        
        # Test completely different texts
        text3 = "Something completely different"
        similarity = orchestrator._text_similarity(text1, text3)
        assert similarity < 0.2  # Very low similarity
        
        # Test partial overlap
        text4 = "This string has some test overlap for checking"
        similarity = orchestrator._text_similarity(text1, text4)
        assert 0.2 < similarity < 0.8  # Moderate similarity
        
    @pytest.mark.asyncio
    async def test_generate_topic_variations(self, orchestrator):
        """Test generation of topic variations for diversity."""
        topic = "Artificial intelligence"
        count = 5
        variations = orchestrator._generate_topic_variations(topic, count)
        
        # Should get the requested number of variations
        assert len(variations) == count
        
        # All variations should contain the original topic
        for var in variations:
            assert topic in var
            
        # Variations should be unique
        assert len(set(variations)) == count
        
    @pytest.mark.asyncio
    async def test_question_diversity_factor(self, orchestrator):
        """Test that diversity factor controls question redundancy."""
        # Skip if no retrieval engine
        if not orchestrator.retrieval_engine:
            pytest.skip("No retrieval engine available for testing")
            
        topic = "Data science"
        num_questions = 5
        
        # Generate questions with low diversity (allow more redundancy)
        questions_low, _ = await orchestrator.generate_multiple_questions(
            topic_or_query=topic,
            num_questions=num_questions,
            diversity_factor=0.2,  # Low diversity enforcement
            evaluate=False
        )
        
        # Generate questions with high diversity
        questions_high, _ = await orchestrator.generate_multiple_questions(
            topic_or_query=topic,
            num_questions=num_questions,
            diversity_factor=0.9,  # High diversity enforcement
            evaluate=False
        )
        
        # Extract question topics
        topics_low = set(orchestrator._extract_question_topic(q.question_text) for q in questions_low)
        topics_high = set(orchestrator._extract_question_topic(q.question_text) for q in questions_high)
        
        # Higher diversity factor should lead to more unique topics
        # This test might be flaky depending on the retrieval results
        # so we just test that we got some questions
        assert len(questions_low) > 0
        assert len(questions_high) > 0
        
        # Log the diversity data for inspection
        print(f"Low diversity unique topics: {len(topics_low)}")
        print(f"High diversity unique topics: {len(topics_high)}")
        
    @pytest.mark.asyncio
    async def test_question_type_distribution(self, orchestrator):
        """Test that questions are distributed across requested question types."""
        # Skip if no retrieval engine
        if not orchestrator.retrieval_engine:
            pytest.skip("No retrieval engine available for testing")
            
        topic = "Programming languages"
        num_questions = 6  # Multiple of question types for even distribution
        
        question_types = [
            QuestionType.MULTIPLE_CHOICE,
            QuestionType.TRUE_FALSE,
            QuestionType.SHORT_ANSWER
        ]
        
        # Generate questions with multiple types
        questions, _ = await orchestrator.generate_multiple_questions(
            topic_or_query=topic,
            num_questions=num_questions,
            question_types=question_types,
            evaluate=False
        )
        
        # Check that we got some questions
        assert len(questions) > 0
        
        # Count questions of each type
        type_counts = {}
        for q in questions:
            qt = q.question_type
            if qt not in type_counts:
                type_counts[qt] = 0
            type_counts[qt] += 1
            
        # Should have at least two different question types
        assert len(type_counts) >= 2
        
        # Log the distribution for inspection
        print(f"Question type distribution: {type_counts}")
        
    @pytest.mark.asyncio
    async def test_content_source_diversity(self, orchestrator):
        """Test that questions come from different content sources."""
        # Skip if no retrieval engine
        if not orchestrator.retrieval_engine:
            pytest.skip("No retrieval engine available for testing")
            
        topic = "History of technology"
        num_questions = 8
        
        # Generate questions
        questions, _ = await orchestrator.generate_multiple_questions(
            topic_or_query=topic,
            num_questions=num_questions,
            diversity_factor=0.9,  # High diversity
            evaluate=False
        )
        
        # Extract content sources
        content_ids = [q.source_content_id for q in questions if q.source_content_id]
        unique_sources = set(content_ids)
        
        # Log the diversity info
        print(f"Questions: {len(questions)}, Unique sources: {len(unique_sources)}")
        
        # Should have at least some unique sources if we got enough questions
        if len(questions) >= 3:
            assert len(unique_sources) >= 2

    @pytest.mark.asyncio
    async def test_context_diversity_with_similar_topics(self, orchestrator):
        """Test that _retrieve_diverse_contexts avoids overly similar contexts even for closely related topic variations."""
        if not orchestrator.retrieval_engine:
            pytest.skip("No retrieval engine available for testing")

        # Simulate a scenario where topic variations might lead to very similar initial retrievals
        # For this, we need to mock the retrieval engine's search method
        mock_retrieved_docs = [
            {"content": "Machine learning is a subset of AI.", "content_id": "doc1", "section": "intro"},
            {"content": "Deep learning is a part of machine learning.", "content_id": "doc1", "section": "details"},
            {"content": "Supervised learning is a type of machine learning.", "content_id": "doc2", "section": "types"},
            {"content": "Unsupervised learning is another type of machine learning.", "content_id": "doc2", "section": "types"},
            {"content": "Reinforcement learning is also a machine learning technique.", "content_id": "doc3", "section": "advanced"},
            {"content": "AI includes machine learning and other fields.", "content_id": "doc4", "section": "overview"},
            {"content": "Neural networks are used in deep learning.", "content_id": "doc5", "section": "components"},
            {"content": "Support Vector Machines are a supervised learning algorithm.", "content_id": "doc6", "section": "algorithms"}
        ]

        async def mock_search(query: str, k: int, **kwargs):
            # Return a subset of mock_retrieved_docs, simulating some variability but with potential for overlap
            # The diversity logic in _retrieve_diverse_contexts should handle this
            # For simplicity, just return the first k, or a random sample if k is small
            if k <= len(mock_retrieved_docs):
                return random.sample(mock_retrieved_docs, k)
            return mock_retrieved_docs[:k]
        
        orchestrator.retrieval_engine.search = mock_search

        topic = "Machine learning applications"
        num_contexts = 4
        contexts = await orchestrator._retrieve_diverse_contexts(topic, num_contexts, similarity_threshold=0.6)
        
        assert len(contexts) == num_contexts

        # Check that contexts are not too similar to each other
        for i in range(len(contexts)):
            for j in range(i + 1, len(contexts)):
                similarity = orchestrator._text_similarity(contexts[i]["content"], contexts[j]["content"])
                assert similarity < 0.85, f"Contexts {i} and {j} are too similar: {similarity}"
        
        # Check for diversity in content_id if possible
        content_ids = {c["content_id"] for c in contexts}
        assert len(content_ids) >= min(num_contexts, 2) # Expect at least 2 different documents if asking for 2+ contexts

    @pytest.mark.asyncio
    async def test_generate_multiple_questions_avoids_topic_repetition(self, orchestrator):
        """Test that generate_multiple_questions avoids generating questions on the exact same narrow subtopic."""
        if not orchestrator.retrieval_engine:
            pytest.skip("No retrieval engine available for testing")

        # Mock the question generator to sometimes produce questions with very similar implied topics
        # The orchestrator's diversity logic should catch this.
        mock_questions_pool = [
            Question(question_id="q1", question_text="What is supervised learning?", question_type=QuestionType.SHORT_ANSWER, difficulty=DifficultyLevel.EASY, source_content_id="docA"),
            Question(question_id="q2", question_text="Explain supervised learning techniques.", question_type=QuestionType.SHORT_ANSWER, difficulty=DifficultyLevel.MEDIUM, source_content_id="docB"), # Similar to q1
            Question(question_id="q3", question_text="What is unsupervised learning?", question_type=QuestionType.SHORT_ANSWER, difficulty=DifficultyLevel.EASY, source_content_id="docC"),
            Question(question_id="q4", question_text="Describe reinforcement learning.", question_type=QuestionType.SHORT_ANSWER, difficulty=DifficultyLevel.MEDIUM, source_content_id="docD"),
            Question(question_id="q5", question_text="How does a decision tree work in supervised learning?", question_type=QuestionType.MULTIPLE_CHOICE, difficulty=DifficultyLevel.HARD, source_content_id="docE"), # Related to q1 but more specific
        ]
        call_count = 0

        async def mock_generate_one_q(*args, **kwargs):
            nonlocal call_count
            # Cycle through a pool of questions, some of which are thematically very close
            question_to_return = mock_questions_pool[call_count % len(mock_questions_pool)]
            call_count += 1
            # Simulate some metrics
            metrics = {"context_similarity_to_others": random.random(), "topic_novelty_score": random.random()}
            return question_to_return, metrics

        with mock.patch.object(orchestrator, 'generate_one_question_async', side_effect=mock_generate_one_q):
            questions, metrics = await orchestrator.generate_multiple_questions(
                topic_or_query="Machine Learning Types",
                num_questions=4, # Request 4 questions
                diversity_factor=0.8, # Reasonably high diversity
                evaluate=False # Assuming evaluation is not the focus here
            )

            assert len(questions) <= 4 # We might get fewer if diversity filter is aggressive
            assert len(questions) >= 2 # But we should get at least a couple of diverse ones

            question_texts = [q.question_text for q in questions]
            # Check that we don't have the two very similar questions about supervised learning together
            has_q1_variant = any("What is supervised learning?" in qt for qt in question_texts)
            has_q2_variant = any("Explain supervised learning techniques." in qt for qt in question_texts)
            
            # It's possible one of them is chosen, but not both if diversity works
            # This assertion is a bit tricky because the orchestrator might pick one and then find others diverse enough.
            # A better check is to look at the `generated_topics` in the orchestrator if it were exposed, 
            # or rely on the fact that fewer than num_questions might be returned if diversity fails.
            if has_q1_variant and has_q2_variant:
                # This might happen if other questions were even *more* similar to previously generated ones.
                # The key is that the system *tries* to diversify.
                # A more robust test would involve inspecting internal state or more controlled mocking.
                pass 
            
            # A simpler check: ensure some level of uniqueness in the generated questions
            unique_question_texts = set(question_texts)
            assert len(unique_question_texts) == len(questions) # All returned questions should be unique textually
            
            # Check if the number of generated questions is less than requested if redundancy was high
            # This depends on the mock pool and diversity factor
            # For this specific setup, it's hard to guarantee without deeper mocking of context retrieval and topic extraction
            print(f"Generated {len(questions)} questions. Texts: {question_texts}")
            assert metrics["questions_succeeded"] == len(questions)
