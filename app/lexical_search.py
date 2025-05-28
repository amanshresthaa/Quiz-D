"""
Lexical search implementation using BM25 algorithm for Sprint 3.
Provides keyword-based search capabilities to complement semantic search.
"""

import logging
import string
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import pickle
import os

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import PorterStemmer
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

from app.models import ContentChunk, VectorSearchResult
from app.config import get_settings

logger = logging.getLogger(__name__)

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab', quiet=True)


@dataclass
class LexicalSearchResult:
    """Result from lexical search with BM25 scoring."""
    chunk_id: str
    content_id: str
    chunk_text: str
    bm25_score: float
    chunk_index: int
    metadata: Dict[str, Any]
    
    def to_vector_search_result(self) -> VectorSearchResult:
        """Convert to VectorSearchResult for consistency."""
        return VectorSearchResult(
            chunk_id=self.chunk_id,
            content_id=self.content_id,
            chunk_text=self.chunk_text,
            similarity_score=self.bm25_score,
            chunk_index=self.chunk_index,
            metadata=self.metadata
        )


class TextPreprocessor:
    """
    Text preprocessing utilities for lexical search.
    Handles tokenization, stopword removal, and stemming.
    """
    
    def __init__(self, language: str = 'english'):
        self.language = language
        self.stemmer = PorterStemmer()
        
        try:
            self.stop_words = set(stopwords.words(language))
        except LookupError:
            logger.warning(f"Stopwords for {language} not found, using empty set")
            self.stop_words = set()
        
        # Add common punctuation and symbols to remove
        self.punctuation = set(string.punctuation)
    
    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Input text to tokenize
            
        Returns:
            List[str]: List of tokens
        """
        if not text:
            return []
        
        try:
            tokens = word_tokenize(text.lower())
            return tokens
        except Exception as e:
            logger.warning(f"Error tokenizing text: {e}, falling back to simple split")
            return text.lower().split()
    
    def remove_stopwords(self, tokens: List[str]) -> List[str]:
        """
        Remove stopwords from token list.
        
        Args:
            tokens: List of tokens
            
        Returns:
            List[str]: Filtered tokens
        """
        return [token for token in tokens if token not in self.stop_words]
    
    def remove_punctuation(self, tokens: List[str]) -> List[str]:
        """
        Remove punctuation from token list.
        
        Args:
            tokens: List of tokens
            
        Returns:
            List[str]: Tokens without punctuation
        """
        return [token for token in tokens if token not in self.punctuation and token.strip()]
    
    def stem_tokens(self, tokens: List[str]) -> List[str]:
        """
        Apply stemming to tokens.
        
        Args:
            tokens: List of tokens
            
        Returns:
            List[str]: Stemmed tokens
        """
        return [self.stemmer.stem(token) for token in tokens]
    
    def preprocess(self, text: str, use_stemming: bool = True) -> List[str]:
        """
        Complete preprocessing pipeline.
        
        Args:
            text: Input text
            use_stemming: Whether to apply stemming
            
        Returns:
            List[str]: Preprocessed tokens
        """
        if not text:
            return []
        
        # Tokenize
        tokens = self.tokenize(text)
        
        # Remove punctuation
        tokens = self.remove_punctuation(tokens)
        
        # Remove stopwords
        tokens = self.remove_stopwords(tokens)
        
        # Filter empty tokens and very short tokens
        tokens = [token for token in tokens if len(token) > 1]
        
        # Apply stemming if requested
        if use_stemming:
            tokens = self.stem_tokens(tokens)
        
        return tokens


class BM25SearchEngine:
    """
    BM25-based lexical search engine.
    Provides keyword matching and ranking for text chunks.
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize BM25 search engine.
        
        Args:
            k1: BM25 parameter controlling term frequency scaling
            b: BM25 parameter controlling document length normalization
        """
        self.settings = get_settings()
        self.k1 = k1
        self.b = b
        
        # Components
        self.preprocessor = TextPreprocessor()
        self.bm25 = None
        
        # Storage
        self._chunks: List[ContentChunk] = []
        self._chunk_id_to_index: Dict[str, int] = {}
        self._processed_texts: List[List[str]] = []
        
        logger.info(f"Initialized BM25 search engine with k1={k1}, b={b}")
        
        # Try to load existing index
        self.load_index()
    
    def add_chunk(self, chunk: ContentChunk) -> bool:
        """
        Add a chunk to the search index.
        
        Args:
            chunk: Content chunk to add
            
        Returns:
            bool: True if successfully added
        """
        if chunk.id in self._chunk_id_to_index:
            logger.warning(f"Chunk {chunk.id} already exists in BM25 index")
            return False
        
        try:
            # Preprocess the chunk text
            processed_text = self.preprocessor.preprocess(chunk.text)
            
            if not processed_text:
                logger.warning(f"Chunk {chunk.id} produced no tokens after preprocessing")
                return False
            
            # Store chunk and processed text
            chunk_index = len(self._chunks)
            self._chunks.append(chunk)
            self._processed_texts.append(processed_text)
            self._chunk_id_to_index[chunk.id] = chunk_index
            
            # Rebuild BM25 index
            self._rebuild_index()
            
            logger.debug(f"Added chunk {chunk.id} to BM25 index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add chunk {chunk.id} to BM25 index: {e}")
            return False
    
    def add_chunks(self, chunks: List[ContentChunk]) -> int:
        """
        Add multiple chunks to the search index.
        
        Args:
            chunks: List of content chunks
            
        Returns:
            int: Number of chunks successfully added
        """
        if not chunks:
            return 0
        
        added_count = 0
        initial_size = len(self._chunks)
        
        for chunk in chunks:
            if chunk.id in self._chunk_id_to_index:
                logger.warning(f"Chunk {chunk.id} already exists, skipping")
                continue
            
            try:
                # Preprocess the chunk text
                processed_text = self.preprocessor.preprocess(chunk.text)
                
                if not processed_text:
                    logger.warning(f"Chunk {chunk.id} produced no tokens after preprocessing")
                    continue
                
                # Store chunk and processed text
                chunk_index = len(self._chunks)
                self._chunks.append(chunk)
                self._processed_texts.append(processed_text)
                self._chunk_id_to_index[chunk.id] = chunk_index
                added_count += 1
                
            except Exception as e:
                logger.warning(f"Failed to process chunk {chunk.id}: {e}")
        
        # Rebuild index once for all chunks
        if added_count > 0:
            self._rebuild_index()
        
        logger.info(f"Added {added_count}/{len(chunks)} chunks to BM25 index")
        return added_count
    
    def _rebuild_index(self):
        """Rebuild the BM25 index with current processed texts."""
        try:
            if self._processed_texts:
                self.bm25 = BM25Okapi(self._processed_texts, k1=self.k1, b=self.b)
                logger.debug(f"Rebuilt BM25 index with {len(self._processed_texts)} documents")
        except Exception as e:
            logger.error(f"Failed to rebuild BM25 index: {e}")
            self.bm25 = None
    
    def search(self, query: str, k: int = None) -> List[LexicalSearchResult]:
        """
        Search for chunks using BM25 scoring.
        
        Args:
            query: Search query text
            k: Maximum number of results to return
            
        Returns:
            List[LexicalSearchResult]: Search results ordered by BM25 score
        """
        if k is None:
            k = self.settings.max_retrieval_results
        
        if not query.strip():
            return []
        
        if not self.bm25 or not self._chunks:
            logger.warning("BM25 index is empty or not built")
            return []
        
        try:
            # Preprocess query
            query_tokens = self.preprocessor.preprocess(query)
            
            if not query_tokens:
                logger.warning(f"Query '{query}' produced no tokens after preprocessing")
                return []
            
            # Get BM25 scores
            scores = self.bm25.get_scores(query_tokens)
            
            # Create scored results
            scored_results = []
            for i, score in enumerate(scores):
                if score > 0:  # Only include results with positive scores
                    chunk = self._chunks[i]
                    result = LexicalSearchResult(
                        chunk_id=chunk.id,
                        content_id=chunk.content_id,
                        chunk_text=chunk.text,
                        bm25_score=float(score),
                        chunk_index=chunk.chunk_index,
                        metadata=chunk.metadata or {}
                    )
                    scored_results.append(result)
            
            # Sort by score (descending) and take top k
            scored_results.sort(key=lambda x: x.bm25_score, reverse=True)
            results = scored_results[:k]
            
            logger.debug(f"BM25 search for '{query[:50]}...' returned {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    def get_chunk_by_id(self, chunk_id: str) -> Optional[ContentChunk]:
        """
        Retrieve chunk by ID.
        
        Args:
            chunk_id: Chunk ID to retrieve
            
        Returns:
            Optional[ContentChunk]: Chunk if found
        """
        if chunk_id in self._chunk_id_to_index:
            index = self._chunk_id_to_index[chunk_id]
            return self._chunks[index]
        return None
    
    def remove_chunk(self, chunk_id: str) -> bool:
        """
        Remove a chunk from the search index.
        
        Args:
            chunk_id: ID of chunk to remove
            
        Returns:
            bool: True if successfully removed
        """
        if chunk_id not in self._chunk_id_to_index:
            return False
        
        try:
            index = self._chunk_id_to_index[chunk_id]
            
            # Remove from storage
            del self._chunks[index]
            del self._processed_texts[index]
            del self._chunk_id_to_index[chunk_id]
            
            # Update indices for remaining chunks
            updated_mapping = {}
            for cid, idx in self._chunk_id_to_index.items():
                if idx > index:
                    updated_mapping[cid] = idx - 1
                else:
                    updated_mapping[cid] = idx
            
            self._chunk_id_to_index = updated_mapping
            
            # Rebuild index
            self._rebuild_index()
            
            logger.debug(f"Removed chunk {chunk_id} from BM25 index")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove chunk {chunk_id}: {e}")
            return False
    
    def clear(self):
        """Clear all chunks from the search index."""
        self._chunks.clear()
        self._chunk_id_to_index.clear()
        self._processed_texts.clear()
        self.bm25 = None
        logger.info("Cleared BM25 search index")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get search engine statistics.
        
        Returns:
            Dict[str, Any]: Statistics about the search index
        """
        return {
            "total_chunks": len(self._chunks),
            "total_documents": len(self._processed_texts),
            "index_built": self.bm25 is not None,
            "average_doc_length": np.mean([len(doc) for doc in self._processed_texts]) if self._processed_texts else 0,
            "vocabulary_size": len(set(token for doc in self._processed_texts for token in doc)) if self._processed_texts else 0,
            "parameters": {
                "k1": self.k1,
                "b": self.b
            }
        }
    
    def save_index(self, filepath: str = None) -> bool:
        """
        Save the search index to disk.
        
        Args:
            filepath: Path to save the index
            
        Returns:
            bool: True if successfully saved
        """
        if filepath is None:
            filepath = os.path.join(os.path.dirname(self.settings.vector_index_path), "bm25_index.pkl")
        
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            index_data = {
                'chunks': self._chunks,
                'chunk_id_to_index': self._chunk_id_to_index,
                'processed_texts': self._processed_texts,
                'parameters': {'k1': self.k1, 'b': self.b}
            }
            
            with open(filepath, 'wb') as f:
                pickle.dump(index_data, f)
            
            logger.info(f"Saved BM25 index to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save BM25 index: {e}")
            return False
    
    def load_index(self, filepath: str = None) -> bool:
        """
        Load the search index from disk.
        
        Args:
            filepath: Path to load the index from
            
        Returns:
            bool: True if successfully loaded
        """
        if filepath is None:
            filepath = os.path.join(os.path.dirname(self.settings.vector_index_path), "bm25_index.pkl")
        
        if not os.path.exists(filepath):
            logger.info(f"BM25 index file not found at {filepath}")
            return False
        
        try:
            with open(filepath, 'rb') as f:
                index_data = pickle.load(f)
            
            self._chunks = index_data['chunks']
            self._chunk_id_to_index = index_data['chunk_id_to_index']
            self._processed_texts = index_data['processed_texts']
            
            # Update parameters if they exist
            if 'parameters' in index_data:
                self.k1 = index_data['parameters'].get('k1', self.k1)
                self.b = index_data['parameters'].get('b', self.b)
            
            # Rebuild BM25 index
            self._rebuild_index()
            
            logger.info(f"Loaded BM25 index from {filepath} with {len(self._chunks)} chunks")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load BM25 index: {e}")
            return False


# Global search engine instance
bm25_search_engine = BM25SearchEngine()


def get_bm25_search_engine() -> BM25SearchEngine:
    """Get the global BM25 search engine instance."""
    return bm25_search_engine


def search_keyword(query: str, max_results: int = None) -> List[VectorSearchResult]:
    """
    Convenience function for keyword search.
    
    Args:
        query: Search query text
        max_results: Maximum number of results
        
    Returns:
        List[VectorSearchResult]: Search results in consistent format
    """
    engine = get_bm25_search_engine()
    lexical_results = engine.search(query, k=max_results)
    
    # Convert to VectorSearchResult for consistency
    return [result.to_vector_search_result() for result in lexical_results]
