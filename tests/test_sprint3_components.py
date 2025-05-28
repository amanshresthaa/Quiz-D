"""
Test suite for Sprint 3 hybrid search components.
"""

import pytest
import asyncio
import tempfile
import os
from typing import List
from unittest.mock import Mock, AsyncMock

from app.models import ContentChunk, VectorSearchResult
from app.lexical_search import BM25SearchEngine, TextPreprocessor, LexicalSearchResult
from app.hybrid_search import HybridSearchEngine, ScoreNormalizer, FusionStrategy
from app.retrieval_engine import RetrievalEngine, SearchMode


class TestTextPreprocessor:
    """Test the text preprocessing functionality."""
    
    def test_tokenization(self):
        """Test text tokenization."""
        processor = TextPreprocessor()
        
        text = "Hello world! This is a test."
        tokens = processor.tokenize(text)
        
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(token, str) for token in tokens)
    
    def test_preprocessing_pipeline(self):
        """Test the complete preprocessing pipeline."""
        processor = TextPreprocessor()
        
        text = "The quick brown foxes are running quickly!"
        processed = processor.preprocess(text)
        
        assert isinstance(processed, list)
        assert len(processed) > 0
        # Should have stemmed words
        assert any('run' in token or 'quick' in token for token in processed)


class TestBM25SearchEngine:
    """Test the BM25 lexical search engine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = BM25SearchEngine()
        
        # Add test chunks
        self.test_chunks = [
            ContentChunk(
                id="chunk1",
                content_id="content1", 
                text="Python is a programming language used for web development",
                chunk_index=0
            ),
            ContentChunk(
                id="chunk2",
                content_id="content1",
                text="Machine learning algorithms use Python for data analysis",
                chunk_index=1
            ),
            ContentChunk(
                id="chunk3", 
                content_id="content2",
                text="Web development frameworks like FastAPI are built with Python",
                chunk_index=0
            )
        ]
        
        self.engine.add_chunks(self.test_chunks)
    
    def test_add_chunk(self):
        """Test adding a single chunk."""
        engine = BM25SearchEngine()
        chunk = self.test_chunks[0]
        
        success = engine.add_chunk(chunk)
        assert success is True
        assert len(engine._chunks) == 1
        assert engine._chunks[0].id == chunk.id
    
    def test_add_chunks(self):
        """Test adding multiple chunks."""
        engine = BM25SearchEngine()
        
        count = engine.add_chunks(self.test_chunks)
        assert count == len(self.test_chunks)
        assert len(engine._chunks) == len(self.test_chunks)
    
    def test_search(self):
        """Test basic search functionality."""
        results = self.engine.search("Python programming", k=5)
        
        assert isinstance(results, list)
        assert len(results) > 0
        assert all(isinstance(r, LexicalSearchResult) for r in results)
        
        # Results should be sorted by score (descending)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)
    
    def test_search_no_results(self):
        """Test search with no matching results."""
        results = self.engine.search("nonexistent query terms", k=5)
        
        # Should return empty list for no matches
        assert isinstance(results, list)
        assert len(results) == 0
    
    def test_remove_chunk(self):
        """Test removing a chunk."""
        initial_count = len(self.engine._chunks)
        
        success = self.engine.remove_chunk("chunk1")
        assert success is True
        assert len(self.engine._chunks) == initial_count - 1
        
        # Should not be able to remove again
        success = self.engine.remove_chunk("chunk1")
        assert success is False
    
    def test_clear(self):
        """Test clearing all chunks."""
        assert len(self.engine._chunks) > 0
        
        self.engine.clear()
        assert len(self.engine._chunks) == 0
    
    def test_persistence(self):
        """Test saving and loading index."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            # Save index
            success = self.engine.save_index(tmp_path)
            assert success is True
            
            # Create new engine and load
            new_engine = BM25SearchEngine()
            success = new_engine.load_index(tmp_path)
            assert success is True
            
            # Should have same chunks
            assert len(new_engine._chunks) == len(self.test_chunks)
            
            # Should return same search results
            original_results = self.engine.search("Python", k=3)
            loaded_results = new_engine.search("Python", k=3)
            
            assert len(original_results) == len(loaded_results)
            
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)


class TestScoreNormalizer:
    """Test score normalization utilities."""
    
    def test_min_max_normalization(self):
        """Test min-max normalization."""
        scores = [0.1, 0.5, 0.8, 1.0, 0.3]
        normalized = ScoreNormalizer.min_max_normalize(scores)
        
        assert len(normalized) == len(scores)
        assert min(normalized) == 0.0
        assert max(normalized) == 1.0
        assert all(0.0 <= score <= 1.0 for score in normalized)
    
    def test_z_score_normalization(self):
        """Test z-score normalization."""
        scores = [1.0, 2.0, 3.0, 4.0, 5.0]
        normalized = ScoreNormalizer.z_score_normalize(scores)
        
        assert len(normalized) == len(scores)
        # Z-scores should have mean close to 0
        assert abs(sum(normalized) / len(normalized)) < 0.01
    
    def test_normalization_edge_cases(self):
        """Test normalization with edge cases."""
        # Empty list
        assert ScoreNormalizer.min_max_normalize([]) == []
        assert ScoreNormalizer.z_score_normalize([]) == []
        
        # Single value
        assert ScoreNormalizer.min_max_normalize([1.0]) == [1.0]
        assert ScoreNormalizer.z_score_normalize([1.0]) == [0.0]
        
        # All same values
        assert ScoreNormalizer.min_max_normalize([0.5, 0.5, 0.5]) == [0.5, 0.5, 0.5]


class TestHybridSearchEngine:
    """Test the hybrid search engine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Mock semantic search
        self.mock_semantic = AsyncMock()
        self.mock_semantic.search = AsyncMock(return_value=[
            VectorSearchResult(
                chunk_id="chunk1",
                similarity_score=0.9,
                chunk_text="Python programming language",
                content_id="content1",
                chunk_index=0
            ),
            VectorSearchResult(
                chunk_id="chunk2", 
                similarity_score=0.7,
                chunk_text="Machine learning with Python",
                content_id="content1",
                chunk_index=1
            )
        ])
        
        # Mock lexical search
        self.mock_lexical = Mock()
        self.mock_lexical.search = Mock(return_value=[
            LexicalSearchResult(
                chunk_id="chunk2",
                score=2.5,
                chunk=ContentChunk(
                    id="chunk2",
                    content_id="content1", 
                    text="Machine learning algorithms",
                    chunk_index=1
                )
            ),
            LexicalSearchResult(
                chunk_id="chunk3",
                score=1.8,
                chunk=ContentChunk(
                    id="chunk3",
                    content_id="content2",
                    text="Web development",
                    chunk_index=0
                )
            )
        ])
        
        self.engine = HybridSearchEngine(
            semantic_search=self.mock_semantic,
            lexical_search=self.mock_lexical
        )
    
    @pytest.mark.asyncio
    async def test_weighted_fusion(self):
        """Test weighted fusion strategy."""
        results = await self.engine.search(
            query="Python programming",
            k=5,
            strategy=FusionStrategy.WEIGHTED_FUSION
        )
        
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Should call both search engines
        self.mock_semantic.search.assert_called_once()
        self.mock_lexical.search.assert_called_once()
        
        # Results should be sorted by combined score
        scores = [r.combined_score for r in results]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio 
    async def test_reciprocal_rank_fusion(self):
        """Test reciprocal rank fusion strategy."""
        results = await self.engine.search(
            query="Python machine learning",
            k=5,
            strategy=FusionStrategy.RECIPROCAL_RANK_FUSION
        )
        
        assert isinstance(results, list)
        assert len(results) > 0
        
        # Check that reciprocal rank scores are calculated
        for result in results:
            assert hasattr(result, 'combined_score')
            assert result.combined_score > 0
    
    @pytest.mark.asyncio
    async def test_semantic_first_strategy(self):
        """Test semantic-first strategy."""
        results = await self.engine.search(
            query="Python",
            k=5,
            strategy=FusionStrategy.SEMANTIC_FIRST
        )
        
        assert isinstance(results, list)
        
        # Should prioritize semantic results
        if len(results) > 0:
            # First result should be from semantic search if available
            semantic_chunk_ids = ["chunk1", "chunk2"]  # From mock
            assert any(r.chunk_id in semantic_chunk_ids for r in results[:1])
    
    @pytest.mark.asyncio
    async def test_intersection_boost(self):
        """Test intersection boost strategy."""
        results = await self.engine.search(
            query="machine learning",
            k=5,
            strategy=FusionStrategy.INTERSECTION_BOOST
        )
        
        assert isinstance(results, list)
        
        # Check for boosted results (chunk2 appears in both searches)
        chunk2_results = [r for r in results if r.chunk_id == "chunk2"]
        if chunk2_results:
            # Should have intersection boost applied
            assert chunk2_results[0].metadata.get("intersection_boost", False)


class TestRetrievalEngine:
    """Test the unified retrieval engine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = RetrievalEngine()
        
        # Mock semantic search
        mock_semantic = AsyncMock()
        mock_semantic.search = AsyncMock(return_value=[])
        self.engine.set_semantic_search(mock_semantic)
        
        # Add test chunks to lexical search
        test_chunks = [
            ContentChunk(
                id="chunk1",
                content_id="content1",
                text="Python programming language for beginners",
                chunk_index=0
            )
        ]
        self.engine.add_chunks(test_chunks)
    
    @pytest.mark.asyncio
    async def test_auto_mode_selection(self):
        """Test automatic mode selection."""
        # Short query should prefer semantic
        results = await self.engine.search("Python", k=5, mode=SearchMode.AUTO)
        assert isinstance(results, list)
        
        # Long query should prefer hybrid
        long_query = "How to learn Python programming language for web development and data science"
        results = await self.engine.search(long_query, k=5, mode=SearchMode.AUTO)
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_semantic_only_mode(self):
        """Test semantic-only search mode."""
        results = await self.engine.search("Python", k=5, mode=SearchMode.SEMANTIC_ONLY)
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_lexical_only_mode(self):
        """Test lexical-only search mode."""
        results = await self.engine.search("Python", k=5, mode=SearchMode.LEXICAL_ONLY)
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_hybrid_mode(self):
        """Test hybrid search mode."""
        results = await self.engine.search("Python", k=5, mode=SearchMode.HYBRID)
        assert isinstance(results, list)
    
    def test_add_chunks(self):
        """Test adding chunks to the engine."""
        initial_count = len(self.engine.lexical_search._chunks)
        
        new_chunks = [
            ContentChunk(
                id="chunk2",
                content_id="content2",
                text="Machine learning algorithms",
                chunk_index=0
            )
        ]
        
        count = self.engine.add_chunks(new_chunks)
        assert count == len(new_chunks)
        assert len(self.engine.lexical_search._chunks) == initial_count + len(new_chunks)
    
    def test_statistics(self):
        """Test statistics collection."""
        stats = self.engine.get_statistics()
        
        assert isinstance(stats, dict)
        assert "total_searches" in stats
        assert "lexical_chunks" in stats
        assert "search_modes_used" in stats


# Integration test fixtures
@pytest.fixture
async def integrated_pipeline():
    """Fixture providing an integrated pipeline for testing."""
    from app.ingestion_pipeline import get_data_ingestion_pipeline
    
    pipeline = get_data_ingestion_pipeline()
    
    # Add some test content
    await pipeline.ingest_content(
        title="Test Document",
        text="This is a test document about Python programming and machine learning.",
        source="test"
    )
    
    return pipeline


@pytest.mark.asyncio
async def test_end_to_end_hybrid_search(integrated_pipeline):
    """Test end-to-end hybrid search through the pipeline."""
    pipeline = integrated_pipeline
    
    # Test different search modes
    modes = ["SEMANTIC_ONLY", "LEXICAL_ONLY", "HYBRID", "AUTO"]
    
    for mode in modes:
        results = await pipeline.search_content(
            query="Python programming",
            max_results=5,
            search_mode=mode
        )
        
        assert isinstance(results, list)
        # Should have at least some results given our test content
        print(f"Mode {mode}: {len(results)} results")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
