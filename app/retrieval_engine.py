"""
Unified retrieval interface combining semantic, lexical, and hybrid search for Sprint 3.
This is the main interface that quiz generation and other components will use.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union
from enum import Enum

from app.models import VectorSearchResult, ContentChunk
from app.config import get_settings
from app.lexical_search import get_bm25_search_engine, search_keyword
from app.hybrid_search import get_hybrid_search_engine, HybridStrategy

logger = logging.getLogger(__name__)


class SearchMode(str, Enum):
    """Available search modes."""
    SEMANTIC_ONLY = "semantic_only"
    LEXICAL_ONLY = "lexical_only"
    HYBRID = "hybrid"
    AUTO = "auto"  # Automatically choose best mode


class RetrievalEngine:
    """
    Unified retrieval engine that orchestrates semantic, lexical, and hybrid search.
    This is the main interface for content retrieval in the quiz generation system.
    """
    
    def __init__(self):
        """Initialize the unified retrieval engine."""
        self.settings = get_settings()
        
        # Search engines
        self.lexical_engine = get_bm25_search_engine()
        self.hybrid_engine = get_hybrid_search_engine()
        
        # Semantic search will be provided by dependency injection
        self._semantic_search_func = None
        
        # Performance tracking
        self._search_stats = {
            "total_searches": 0,
            "semantic_searches": 0,
            "lexical_searches": 0,
            "hybrid_searches": 0,
            "average_results": 0,
            "errors": 0,
            "search_modes_used": {}
        }
        
        logger.info("Initialized unified retrieval engine")
    
    def set_semantic_search_function(self, search_func):
        """
        Set the semantic search function from external component.
        
        Args:
            search_func: Async function that takes (query, max_results) and returns List[VectorSearchResult]
        """
        self._semantic_search_func = search_func
        logger.info("Semantic search function registered with retrieval engine")
    
    def set_semantic_search(self, semantic_search_func):
        """
        Set the semantic search function/object.
        
        Args:
            semantic_search_func: Function or object that can perform semantic search
        """
        self._semantic_search_func = semantic_search_func
        
        # Also set it for hybrid engine
        if self.hybrid_engine and hasattr(self.hybrid_engine, 'set_semantic_search'):
            try:
                self.hybrid_engine.set_semantic_search(semantic_search_func)
                logger.info("Connected semantic search to hybrid engine")
            except Exception as e:
                logger.warning(f"Failed to connect semantic search to hybrid engine: {e}")
    
    async def search_semantic(self, query: str, max_results: int = None) -> List[VectorSearchResult]:
        """
        Perform semantic search.
        
        Args:
            query: Search query text
            max_results: Maximum number of results
            
        Returns:
            List[VectorSearchResult]: Semantic search results
        """
        if not self._semantic_search_func:
            logger.warning("Semantic search function not available")
            return []
        
        try:
            results = await self._semantic_search_func(query, max_results)
            self._search_stats["semantic_searches"] += 1
            logger.debug(f"Semantic search for '{query[:50]}...' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            self._search_stats["errors"] += 1
            return []
    
    def search_lexical(self, query: str, max_results: int = None) -> List[VectorSearchResult]:
        """
        Perform lexical search.
        
        Args:
            query: Search query text
            max_results: Maximum number of results
            
        Returns:
            List[VectorSearchResult]: Lexical search results
        """
        try:
            results = search_keyword(query, max_results)
            self._search_stats["lexical_searches"] += 1
            logger.debug(f"Lexical search for '{query[:50]}...' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Lexical search failed: {e}")
            self._search_stats["errors"] += 1
            return []
    
    async def search_hybrid(
        self,
        query: str,
        max_results: int = None,
        strategy: HybridStrategy = None,
        semantic_weight: float = None,
        lexical_weight: float = None,
        **kwargs
    ) -> List[VectorSearchResult]:
        """
        Perform hybrid search combining semantic and lexical results.
        
        Args:
            query: Search query text
            max_results: Maximum number of results
            strategy: Hybrid fusion strategy
            semantic_weight: Weight for semantic results
            lexical_weight: Weight for lexical results
            **kwargs: Additional strategy-specific parameters
            
        Returns:
            List[VectorSearchResult]: Hybrid search results
        """
        try:
            # Perform both searches concurrently
            semantic_task = self.search_semantic(query, max_results)
            lexical_results = self.search_lexical(query, max_results)
            
            # Wait for semantic search to complete
            semantic_results = await semantic_task
            
            # Combine using hybrid engine
            hybrid_results = self.hybrid_engine.combine_results(
                semantic_results=semantic_results,
                lexical_results=lexical_results,
                strategy=strategy,
                max_results=max_results,
                semantic_weight=semantic_weight,
                lexical_weight=lexical_weight,
                **kwargs
            )
            
            # Convert back to VectorSearchResult
            results = [result.to_vector_search_result() for result in hybrid_results]
            
            self._search_stats["hybrid_searches"] += 1
            logger.debug(f"Hybrid search for '{query[:50]}...' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            self._search_stats["errors"] += 1
            return []
    
    async def retrieve(
        self,
        query: str,
        mode: SearchMode = SearchMode.AUTO,
        max_results: int = None,
        **kwargs
    ) -> List[VectorSearchResult]:
        """
        Main retrieval function that automatically selects the best search strategy.
        
        Args:
            query: Search query text
            mode: Search mode to use
            max_results: Maximum number of results to return
            **kwargs: Additional parameters for specific search modes
            
        Returns:
            List[VectorSearchResult]: Retrieved results
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to retrieve function")
            return []
        
        if max_results is None:
            max_results = self.settings.max_retrieval_results
        
        try:
            self._search_stats["total_searches"] += 1

            # Choose search mode
            if mode == SearchMode.AUTO:
                # If semantic search not configured, fallback directly to lexical
                if not self._semantic_search_func and self.settings.fallback_to_lexical:
                    mode = SearchMode.LEXICAL_ONLY
                else:
                    mode = self._auto_select_mode(query)
            
            # Perform search based on mode
            if mode == SearchMode.SEMANTIC_ONLY:
                results = await self.search_semantic(query, max_results)
                # Fallback to lexical if semantic yields nothing and configured
                if not results and self.settings.fallback_to_lexical:
                    results = self.search_lexical(query, max_results)
            elif mode == SearchMode.LEXICAL_ONLY:
                results = self.search_lexical(query, max_results)
            elif mode == SearchMode.HYBRID:
                results = await self.search_hybrid(query, max_results, **kwargs)
            else:
                logger.warning(f"Unknown search mode {mode}, falling back to hybrid")
                results = await self.search_hybrid(query, max_results, **kwargs)
            
            # Update statistics
            if results:
                self._search_stats["average_results"] = (
                    (self._search_stats["average_results"] * (self._search_stats["total_searches"] - 1) + len(results))
                    / self._search_stats["total_searches"]
                )
            
            logger.info(f"Retrieved {len(results)} results for query '{query[:50]}...' using {mode}")
            return results
            
        except Exception as e:
            logger.error(f"Retrieval failed for query '{query[:50]}...': {e}")
            self._search_stats["errors"] += 1
            return []
    
    def _auto_select_mode(self, query: str) -> SearchMode:
        """
        Automatically select the best search mode based on query characteristics.
        
        Args:
            query: Search query text
            
        Returns:
            SearchMode: Recommended search mode
        """
        query = query.strip().lower()
        
        # Simple heuristics for mode selection
        
        # If query is very short (1-2 words), lexical might be better for exact matches
        words = query.split()
        if len(words) <= 2 and any(len(word) > 3 for word in words):
            return SearchMode.LEXICAL_ONLY
        
        # If query contains quoted phrases, prioritize lexical search
        if '"' in query:
            return SearchMode.LEXICAL_ONLY
        
        # If query contains technical terms or specific keywords, use hybrid
        technical_indicators = ['function', 'class', 'method', 'variable', 'algorithm', 'implementation']
        if any(indicator in query for indicator in technical_indicators):
            return SearchMode.HYBRID
        
        # If query is long and descriptive, semantic search might be better
        if len(words) > 5:
            return SearchMode.SEMANTIC_ONLY
        
        # Default to hybrid for balanced results
        return SearchMode.HYBRID
    
    def add_chunk(self, chunk: ContentChunk) -> bool:
        """
        Add a chunk to all search indexes.
        
        Args:
            chunk: Content chunk to add
            
        Returns:
            bool: True if successfully added to at least one index
        """
        success = False
        
        # Add to lexical index
        try:
            if self.lexical_engine.add_chunk(chunk):
                success = True
                logger.debug(f"Added chunk {chunk.id} to lexical index")
        except Exception as e:
            logger.warning(f"Failed to add chunk {chunk.id} to lexical index: {e}")
        
        return success
    
    def add_chunks(self, chunks: List[ContentChunk]) -> Dict[str, int]:
        """
        Add multiple chunks to all search indexes.
        
        Args:
            chunks: List of content chunks to add
            
        Returns:
            Dict[str, int]: Count of chunks added to each index type
        """
        if not chunks:
            return {"lexical": 0}
        
        results = {}
        
        # Add to lexical index
        try:
            lexical_count = self.lexical_engine.add_chunks(chunks)
            results["lexical"] = lexical_count
            logger.info(f"Added {lexical_count}/{len(chunks)} chunks to lexical index")
        except Exception as e:
            logger.error(f"Failed to add chunks to lexical index: {e}")
            results["lexical"] = 0
        
        return results
    
    def remove_chunk(self, chunk_id: str) -> Dict[str, bool]:
        """
        Remove a chunk from all search indexes.
        
        Args:
            chunk_id: ID of chunk to remove
            
        Returns:
            Dict[str, bool]: Success status for each index type
        """
        results = {}
        
        # Remove from lexical index
        try:
            results["lexical"] = self.lexical_engine.remove_chunk(chunk_id)
        except Exception as e:
            logger.warning(f"Failed to remove chunk {chunk_id} from lexical index: {e}")
            results["lexical"] = False
        
        return results
    
    def clear(self):
        """
        Clear all data from the retrieval engine.
        """
        try:
            if hasattr(self.lexical_engine, 'clear'):
                self.lexical_engine.clear()
                logger.info("Cleared lexical search index")
            
            # Reset statistics
            self._search_stats = {
                "total_searches": 0,
                "semantic_searches": 0,
                "lexical_searches": 0,
                "hybrid_searches": 0,
                "average_results": 0,
                "errors": 0,
                "search_modes_used": {}
            }
            
        except Exception as e:
            logger.error(f"Failed to clear retrieval engine: {e}")
    
    def clear_indexes(self):
        """Clear all search indexes."""
        try:
            self.lexical_engine.clear()
            logger.info("Cleared all search indexes")
        except Exception as e:
            logger.error(f"Failed to clear indexes: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive retrieval statistics.
        
        Returns:
            Dict[str, Any]: Statistics about the retrieval system
        """
        lexical_stats = self.lexical_engine.get_stats()
        
        return {
            "search_stats": self._search_stats.copy(),
            "lexical_index": lexical_stats,
            "capabilities": {
                "semantic_search": self._semantic_search_func is not None,
                "lexical_search": True,
                "hybrid_search": self._semantic_search_func is not None
            },
            "configuration": {
                "max_retrieval_results": self.settings.max_retrieval_results,
                "hybrid_semantic_weight": self.hybrid_engine.semantic_weight,
                "hybrid_lexical_weight": self.hybrid_engine.lexical_weight,
                "default_strategy": self.hybrid_engine.default_strategy
            }
        }
    
    def save_indexes(self, base_path: str = None) -> Dict[str, bool]:
        """
        Save all search indexes to disk.
        
        Args:
            base_path: Base path for saving indexes
            
        Returns:
            Dict[str, bool]: Save status for each index type
        """
        results = {}
        
        # Save lexical index
        try:
            lexical_path = None
            if base_path:
                lexical_path = f"{base_path}_lexical.pkl"
            results["lexical"] = self.lexical_engine.save_index(lexical_path)
        except Exception as e:
            logger.error(f"Failed to save lexical index: {e}")
            results["lexical"] = False
        
        return results
    
    def load_indexes(self, base_path: str = None) -> Dict[str, bool]:
        """
        Load all search indexes from disk.
        
        Args:
            base_path: Base path for loading indexes
            
        Returns:
            Dict[str, bool]: Load status for each index type
        """
        results = {}
        
        # Load lexical index
        try:
            lexical_path = None
            if base_path:
                lexical_path = f"{base_path}_lexical.pkl"
            results["lexical"] = self.lexical_engine.load_index(lexical_path)
        except Exception as e:
            logger.error(f"Failed to load lexical index: {e}")
            results["lexical"] = False
        
        return results
    
    async def search(
        self,
        query: str,
        max_results: int = None,
        mode: SearchMode = SearchMode.AUTO,
        **kwargs
    ) -> List[VectorSearchResult]:
        """
        Main search interface - alias for retrieve method for consistency.
        
        Args:
            query: Search query text
            max_results: Maximum number of results to return
            mode: Search mode to use
            **kwargs: Additional parameters for specific search modes
            
        Returns:
            List[VectorSearchResult]: Search results
        """
        return await self.retrieve(query, mode, max_results, **kwargs)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the retrieval engine.
        
        Returns:
            Dict[str, Any]: Statistics including search counts, performance metrics, etc.
        """
        stats = dict(self._search_stats)
        
        # Add engine-specific stats
        stats["lexical_chunks"] = len(self.lexical_engine._chunks) if hasattr(self.lexical_engine, '_chunks') else 0
        stats["semantic_search_available"] = self._semantic_search_func is not None
        stats["hybrid_search_available"] = self.hybrid_engine is not None
        
        # Search mode breakdown
        total_searches = self._search_stats.get("total_searches", 0)
        if total_searches > 0:
            stats["search_mode_distribution"] = {
                "semantic_percentage": (self._search_stats.get("semantic_searches", 0) / total_searches) * 100,
                "lexical_percentage": (self._search_stats.get("lexical_searches", 0) / total_searches) * 100,
                "hybrid_percentage": (self._search_stats.get("hybrid_searches", 0) / total_searches) * 100
            }
        else:
            stats["search_mode_distribution"] = {
                "semantic_percentage": 0,
                "lexical_percentage": 0,
                "hybrid_percentage": 0
            }
        
        # Calculate average results per search
        if total_searches > 0:
            stats["average_results_per_search"] = stats.get("average_results", 0)
        else:
            stats["average_results_per_search"] = 0
        
        return stats


# Global retrieval engine instance
retrieval_engine = RetrievalEngine()


def get_retrieval_engine() -> RetrievalEngine:
    """Get the global retrieval engine instance."""
    return retrieval_engine


# Convenience functions for backward compatibility
async def search_semantic(query: str, max_results: int = None) -> List[VectorSearchResult]:
    """Convenience function for semantic search."""
    engine = get_retrieval_engine()
    return await engine.search_semantic(query, max_results)


def search_lexical(query: str, max_results: int = None) -> List[VectorSearchResult]:
    """Convenience function for lexical search."""
    engine = get_retrieval_engine()
    return engine.search_lexical(query, max_results)


async def search_hybrid(query: str, max_results: int = None, **kwargs) -> List[VectorSearchResult]:
    """Convenience function for hybrid search."""
    engine = get_retrieval_engine()
    return await engine.search_hybrid(query, max_results, **kwargs)


async def retrieve(query: str, **kwargs) -> List[VectorSearchResult]:
    """Main convenience function for content retrieval."""
    engine = get_retrieval_engine()
    return await engine.retrieve(query, **kwargs)
