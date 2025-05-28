"""
Hybrid search implementation combining semantic and lexical search for Sprint 3.
Provides multiple merging strategies including weighted fusion and reciprocal rank fusion.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from dataclasses import dataclass
from enum import Enum
import math

from app.models import VectorSearchResult, ContentChunk
from app.config import get_settings

logger = logging.getLogger(__name__)


class HybridStrategy(str, Enum):
    """Strategies for combining semantic and lexical search results."""
    WEIGHTED_FUSION = "weighted_fusion"
    RECIPROCAL_RANK_FUSION = "reciprocal_rank_fusion"
    SEMANTIC_FIRST = "semantic_first"
    LEXICAL_FIRST = "lexical_first"
    INTERSECTION_BOOST = "intersection_boost"


@dataclass
class HybridSearchResult:
    """Result from hybrid search with combined scoring."""
    chunk_id: str
    content_id: str
    chunk_text: str
    hybrid_score: float
    semantic_score: Optional[float]
    lexical_score: Optional[float]
    semantic_rank: Optional[int]
    lexical_rank: Optional[int]
    chunk_index: int
    metadata: Dict[str, Any]
    
    def to_vector_search_result(self) -> VectorSearchResult:
        """Convert to VectorSearchResult for API consistency."""
        return VectorSearchResult(
            chunk_id=self.chunk_id,
            content_id=self.content_id,
            chunk_text=self.chunk_text,
            similarity_score=self.hybrid_score,
            chunk_index=self.chunk_index,
            metadata={
                **self.metadata,
                "hybrid_metadata": {
                    "semantic_score": self.semantic_score,
                    "lexical_score": self.lexical_score,
                    "semantic_rank": self.semantic_rank,
                    "lexical_rank": self.lexical_rank
                }
            }
        )


class ScoreNormalizer:
    """Utilities for normalizing and scaling search scores."""
    
    @staticmethod
    def min_max_normalize(scores: List[float]) -> List[float]:
        """
        Min-max normalization to [0, 1] range.
        
        Args:
            scores: List of scores to normalize
            
        Returns:
            List[float]: Normalized scores
        """
        if not scores:
            return []
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [1.0] * len(scores)
        
        return [(score - min_score) / (max_score - min_score) for score in scores]
    
    @staticmethod
    def z_score_normalize(scores: List[float]) -> List[float]:
        """
        Z-score normalization (mean=0, std=1).
        
        Args:
            scores: List of scores to normalize
            
        Returns:
            List[float]: Normalized scores
        """
        if not scores:
            return []
        
        mean_score = sum(scores) / len(scores)
        variance = sum((score - mean_score) ** 2 for score in scores) / len(scores)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0
        
        return [(score - mean_score) / std_dev for score in scores]
    
    @staticmethod
    def rank_based_normalize(ranks: List[int], total_docs: int) -> List[float]:
        """
        Convert ranks to normalized scores.
        
        Args:
            ranks: List of ranks (1-based)
            total_docs: Total number of documents
            
        Returns:
            List[float]: Normalized scores based on ranks
        """
        if not ranks:
            return []
        
        return [(total_docs - rank + 1) / total_docs for rank in ranks]


class HybridSearchEngine:
    """
    Hybrid search engine combining semantic and lexical search.
    Supports multiple fusion strategies and configurable parameters.
    """
    
    def __init__(
        self,
        semantic_weight: float = 0.7,
        lexical_weight: float = 0.3,
        rrf_k: int = 60,
        strategy: HybridStrategy = HybridStrategy.WEIGHTED_FUSION
    ):
        """
        Initialize hybrid search engine.
        
        Args:
            semantic_weight: Weight for semantic search results
            lexical_weight: Weight for lexical search results  
            rrf_k: Parameter for reciprocal rank fusion
            strategy: Default fusion strategy
        """
        self.settings = get_settings()
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.rrf_k = rrf_k
        self.default_strategy = strategy
        
        # Ensure weights sum to 1.0
        total_weight = semantic_weight + lexical_weight
        if total_weight > 0:
            self.semantic_weight = semantic_weight / total_weight
            self.lexical_weight = lexical_weight / total_weight
        
        logger.info(f"Initialized hybrid search with semantic_weight={self.semantic_weight:.2f}, "
                   f"lexical_weight={self.lexical_weight:.2f}, strategy={strategy}")
    
    def weighted_fusion(
        self,
        semantic_results: List[VectorSearchResult],
        lexical_results: List[VectorSearchResult],
        semantic_weight: float = None,
        lexical_weight: float = None
    ) -> List[HybridSearchResult]:
        """
        Combine results using weighted score fusion.
        
        Args:
            semantic_results: Results from semantic search
            lexical_results: Results from lexical search
            semantic_weight: Weight for semantic scores (override default)
            lexical_weight: Weight for lexical scores (override default)
            
        Returns:
            List[HybridSearchResult]: Combined results
        """
        if semantic_weight is None:
            semantic_weight = self.semantic_weight
        if lexical_weight is None:
            lexical_weight = self.lexical_weight
        
        # Normalize weights
        total_weight = semantic_weight + lexical_weight
        if total_weight > 0:
            semantic_weight /= total_weight
            lexical_weight /= total_weight
        
        # Create lookup maps
        semantic_map = {result.chunk_id: result for result in semantic_results}
        lexical_map = {result.chunk_id: result for result in lexical_results}
        
        # Get all unique chunk IDs
        all_chunk_ids = set(semantic_map.keys()) | set(lexical_map.keys())
        
        # Normalize scores
        semantic_scores = [result.similarity_score for result in semantic_results]
        lexical_scores = [result.similarity_score for result in lexical_results]
        
        normalized_semantic = ScoreNormalizer.min_max_normalize(semantic_scores)
        normalized_lexical = ScoreNormalizer.min_max_normalize(lexical_scores)
        
        # Create normalized score maps
        semantic_score_map = {
            semantic_results[i].chunk_id: normalized_semantic[i] 
            for i in range(len(semantic_results))
        } if normalized_semantic else {}
        
        lexical_score_map = {
            lexical_results[i].chunk_id: normalized_lexical[i] 
            for i in range(len(lexical_results))
        } if normalized_lexical else {}
        
        # Combine scores
        hybrid_results = []
        for chunk_id in all_chunk_ids:
            semantic_score = semantic_score_map.get(chunk_id, 0.0)
            lexical_score = lexical_score_map.get(chunk_id, 0.0)
            
            # Calculate weighted combination
            hybrid_score = (semantic_weight * semantic_score + 
                          lexical_weight * lexical_score)
            
            # Get chunk info from either result set
            source_result = semantic_map.get(chunk_id) or lexical_map.get(chunk_id)
            
            if source_result:
                result = HybridSearchResult(
                    chunk_id=chunk_id,
                    content_id=source_result.content_id,
                    chunk_text=source_result.chunk_text,
                    hybrid_score=hybrid_score,
                    semantic_score=semantic_score if chunk_id in semantic_map else None,
                    lexical_score=lexical_score if chunk_id in lexical_map else None,
                    semantic_rank=None,  # Will be set later if needed
                    lexical_rank=None,
                    chunk_index=source_result.chunk_index,
                    metadata=source_result.metadata
                )
                hybrid_results.append(result)
        
        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        logger.debug(f"Weighted fusion combined {len(semantic_results)} semantic + "
                    f"{len(lexical_results)} lexical results into {len(hybrid_results)} hybrid results")
        
        return hybrid_results
    
    def reciprocal_rank_fusion(
        self,
        semantic_results: List[VectorSearchResult],
        lexical_results: List[VectorSearchResult],
        k: int = None
    ) -> List[HybridSearchResult]:
        """
        Combine results using Reciprocal Rank Fusion (RRF).
        
        Args:
            semantic_results: Results from semantic search
            lexical_results: Results from lexical search
            k: RRF parameter (default uses instance setting)
            
        Returns:
            List[HybridSearchResult]: Combined results
        """
        if k is None:
            k = self.rrf_k
        
        # Create rank maps (1-based ranking)
        semantic_ranks = {result.chunk_id: i + 1 for i, result in enumerate(semantic_results)}
        lexical_ranks = {result.chunk_id: i + 1 for i, result in enumerate(lexical_results)}
        
        # Create lookup maps for metadata
        semantic_map = {result.chunk_id: result for result in semantic_results}
        lexical_map = {result.chunk_id: result for result in lexical_results}
        
        # Get all unique chunk IDs
        all_chunk_ids = set(semantic_ranks.keys()) | set(lexical_ranks.keys())
        
        # Calculate RRF scores
        hybrid_results = []
        for chunk_id in all_chunk_ids:
            # RRF formula: 1/(k + rank)
            semantic_rrf = 1.0 / (k + semantic_ranks[chunk_id]) if chunk_id in semantic_ranks else 0.0
            lexical_rrf = 1.0 / (k + lexical_ranks[chunk_id]) if chunk_id in lexical_ranks else 0.0
            
            hybrid_score = semantic_rrf + lexical_rrf
            
            # Get chunk info from either result set
            source_result = semantic_map.get(chunk_id) or lexical_map.get(chunk_id)
            
            if source_result:
                result = HybridSearchResult(
                    chunk_id=chunk_id,
                    content_id=source_result.content_id,
                    chunk_text=source_result.chunk_text,
                    hybrid_score=hybrid_score,
                    semantic_score=semantic_map[chunk_id].similarity_score if chunk_id in semantic_map else None,
                    lexical_score=lexical_map[chunk_id].similarity_score if chunk_id in lexical_map else None,
                    semantic_rank=semantic_ranks.get(chunk_id),
                    lexical_rank=lexical_ranks.get(chunk_id),
                    chunk_index=source_result.chunk_index,
                    metadata=source_result.metadata
                )
                hybrid_results.append(result)
        
        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        logger.debug(f"RRF fusion with k={k} combined {len(semantic_results)} semantic + "
                    f"{len(lexical_results)} lexical results into {len(hybrid_results)} hybrid results")
        
        return hybrid_results
    
    def intersection_boost(
        self,
        semantic_results: List[VectorSearchResult],
        lexical_results: List[VectorSearchResult],
        boost_factor: float = 1.5
    ) -> List[HybridSearchResult]:
        """
        Boost results that appear in both semantic and lexical results.
        
        Args:
            semantic_results: Results from semantic search
            lexical_results: Results from lexical search
            boost_factor: Multiplication factor for intersection boost
            
        Returns:
            List[HybridSearchResult]: Combined results with boosted intersections
        """
        # First apply weighted fusion
        base_results = self.weighted_fusion(semantic_results, lexical_results)
        
        # Find intersections
        semantic_chunk_ids = {result.chunk_id for result in semantic_results}
        lexical_chunk_ids = {result.chunk_id for result in lexical_results}
        intersection_ids = semantic_chunk_ids & lexical_chunk_ids
        
        # Apply boost to intersection results
        for result in base_results:
            if result.chunk_id in intersection_ids:
                result.hybrid_score *= boost_factor
        
        # Re-sort
        base_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        logger.debug(f"Intersection boost applied to {len(intersection_ids)} results "
                    f"with boost_factor={boost_factor}")
        
        return base_results
    
    def semantic_first(
        self,
        semantic_results: List[VectorSearchResult],
        lexical_results: List[VectorSearchResult],
        semantic_limit: int = None
    ) -> List[HybridSearchResult]:
        """
        Prioritize semantic results, fill remaining slots with lexical results.
        
        Args:
            semantic_results: Results from semantic search
            lexical_results: Results from lexical search
            semantic_limit: Maximum number of semantic results to include
            
        Returns:
            List[HybridSearchResult]: Combined results with semantic priority
        """
        if semantic_limit is None:
            semantic_limit = max(len(semantic_results) // 2, 1)
        
        # Take top semantic results
        top_semantic = semantic_results[:semantic_limit]
        semantic_chunk_ids = {result.chunk_id for result in top_semantic}
        
        # Add lexical results not already included
        remaining_lexical = [
            result for result in lexical_results 
            if result.chunk_id not in semantic_chunk_ids
        ]
        
        # Convert to hybrid results
        hybrid_results = []
        
        # Add semantic results with higher base scores
        for i, result in enumerate(top_semantic):
            hybrid_score = 1.0 - (i * 0.01)  # Slight decrease for each rank
            hybrid_results.append(HybridSearchResult(
                chunk_id=result.chunk_id,
                content_id=result.content_id,
                chunk_text=result.chunk_text,
                hybrid_score=hybrid_score,
                semantic_score=result.similarity_score,
                lexical_score=None,
                semantic_rank=i + 1,
                lexical_rank=None,
                chunk_index=result.chunk_index,
                metadata=result.metadata
            ))
        
        # Add lexical results with lower base scores
        base_lexical_score = 0.5
        for i, result in enumerate(remaining_lexical):
            hybrid_score = base_lexical_score - (i * 0.01)
            
            # Find lexical rank
            lexical_rank = next(
                (j + 1 for j, r in enumerate(lexical_results) if r.chunk_id == result.chunk_id),
                None
            )
            
            hybrid_results.append(HybridSearchResult(
                chunk_id=result.chunk_id,
                content_id=result.content_id,
                chunk_text=result.chunk_text,
                hybrid_score=max(0.0, hybrid_score),
                semantic_score=None,
                lexical_score=result.similarity_score,
                semantic_rank=None,
                lexical_rank=lexical_rank,
                chunk_index=result.chunk_index,
                metadata=result.metadata
            ))
        
        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        logger.debug(f"Semantic-first strategy: {len(top_semantic)} semantic + "
                    f"{len(remaining_lexical)} lexical results")
        
        return hybrid_results
    
    def lexical_first(
        self,
        semantic_results: List[VectorSearchResult],
        lexical_results: List[VectorSearchResult],
        lexical_limit: int = None
    ) -> List[HybridSearchResult]:
        """
        Prioritize lexical results, fill remaining slots with semantic results.
        Similar to semantic_first but with lexical priority.
        """
        if lexical_limit is None:
            lexical_limit = max(len(lexical_results) // 2, 1)
        
        # Take top lexical results
        top_lexical = lexical_results[:lexical_limit]
        lexical_chunk_ids = {result.chunk_id for result in top_lexical}
        
        # Add semantic results not already included
        remaining_semantic = [
            result for result in semantic_results 
            if result.chunk_id not in lexical_chunk_ids
        ]
        
        # Convert to hybrid results (similar logic as semantic_first but reversed)
        hybrid_results = []
        
        # Add lexical results with higher base scores
        for i, result in enumerate(top_lexical):
            hybrid_score = 1.0 - (i * 0.01)
            
            # Find lexical rank
            lexical_rank = next(
                (j + 1 for j, r in enumerate(lexical_results) if r.chunk_id == result.chunk_id),
                None
            )
            
            hybrid_results.append(HybridSearchResult(
                chunk_id=result.chunk_id,
                content_id=result.content_id,
                chunk_text=result.chunk_text,
                hybrid_score=hybrid_score,
                semantic_score=None,
                lexical_score=result.similarity_score,
                semantic_rank=None,
                lexical_rank=lexical_rank,
                chunk_index=result.chunk_index,
                metadata=result.metadata
            ))
        
        # Add semantic results with lower base scores
        base_semantic_score = 0.5
        for i, result in enumerate(remaining_semantic):
            hybrid_score = base_semantic_score - (i * 0.01)
            
            hybrid_results.append(HybridSearchResult(
                chunk_id=result.chunk_id,
                content_id=result.content_id,
                chunk_text=result.chunk_text,
                hybrid_score=max(0.0, hybrid_score),
                semantic_score=result.similarity_score,
                lexical_score=None,
                semantic_rank=i + 1,
                lexical_rank=None,
                chunk_index=result.chunk_index,
                metadata=result.metadata
            ))
        
        # Sort by hybrid score
        hybrid_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        
        logger.debug(f"Lexical-first strategy: {len(top_lexical)} lexical + "
                    f"{len(remaining_semantic)} semantic results")
        
        return hybrid_results
    
    def combine_results(
        self,
        semantic_results: List[VectorSearchResult],
        lexical_results: List[VectorSearchResult],
        strategy: HybridStrategy = None,
        max_results: int = None,
        **kwargs
    ) -> List[HybridSearchResult]:
        """
        Combine semantic and lexical results using specified strategy.
        
        Args:
            semantic_results: Results from semantic search
            lexical_results: Results from lexical search
            strategy: Fusion strategy to use
            max_results: Maximum number of results to return
            **kwargs: Additional parameters for specific strategies
            
        Returns:
            List[HybridSearchResult]: Combined results
        """
        if strategy is None:
            strategy = self.default_strategy
        
        if max_results is None:
            max_results = self.settings.max_retrieval_results
        
        # Apply the selected strategy
        if strategy == HybridStrategy.WEIGHTED_FUSION:
            results = self.weighted_fusion(
                semantic_results, lexical_results,
                kwargs.get('semantic_weight'), kwargs.get('lexical_weight')
            )
        elif strategy == HybridStrategy.RECIPROCAL_RANK_FUSION:
            results = self.reciprocal_rank_fusion(
                semantic_results, lexical_results,
                kwargs.get('k')
            )
        elif strategy == HybridStrategy.INTERSECTION_BOOST:
            results = self.intersection_boost(
                semantic_results, lexical_results,
                kwargs.get('boost_factor', 1.5)
            )
        elif strategy == HybridStrategy.SEMANTIC_FIRST:
            results = self.semantic_first(
                semantic_results, lexical_results,
                kwargs.get('semantic_limit')
            )
        elif strategy == HybridStrategy.LEXICAL_FIRST:
            results = self.lexical_first(
                semantic_results, lexical_results,
                kwargs.get('lexical_limit')
            )
        else:
            logger.warning(f"Unknown strategy {strategy}, falling back to weighted fusion")
            results = self.weighted_fusion(semantic_results, lexical_results)
        
        # Limit results
        results = results[:max_results]
        
        logger.info(f"Combined {len(semantic_results)} semantic + {len(lexical_results)} lexical "
                   f"results into {len(results)} hybrid results using {strategy}")
        
        return results


# Global hybrid search engine instance
hybrid_search_engine = HybridSearchEngine()


def get_hybrid_search_engine() -> HybridSearchEngine:
    """Get the global hybrid search engine instance."""
    return hybrid_search_engine
