"""
Enhanced content ingestion module with token-aware chunking and embedding support.
Implements Sprint 2 requirements for intelligent content processing.
"""

import uuid
import tiktoken
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.models import ContentItem, ContentChunk
from app.config import get_settings


class TokenAwareChunker:
    """
    Advanced text chunker that respects token limits and sentence boundaries.
    """
    
    def __init__(self, max_tokens: int = 500, overlap_tokens: int = 100, preserve_sentences: bool = True):
        """
        Initialize the chunker.
        
        Args:
            max_tokens: Maximum tokens per chunk
            overlap_tokens: Number of tokens to overlap between chunks
            preserve_sentences: Whether to preserve sentence boundaries
        """
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.preserve_sentences = preserve_sentences
        
        # Initialize tokenizer (OpenAI's tokenizer for consistency)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            # Fallback to simple word-based tokenization
            self.tokenizer = None
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using OpenAI's tokenizer.
        
        Args:
            text: Text to count tokens for
            
        Returns:
            int: Number of tokens
        """
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback: approximate token count (1 token ≈ 4 characters)
            return len(text) // 4
    
    def split_by_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences using regex patterns.
        
        Args:
            text: Text to split
            
        Returns:
            List[str]: List of sentences
        """
        # Enhanced sentence splitting pattern
        sentence_pattern = r'(?<=[.!?])\s+(?=[A-Z])'
        sentences = re.split(sentence_pattern, text.strip())
        
        # Clean up sentences
        cleaned_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence:
                cleaned_sentences.append(sentence)
        
        return cleaned_sentences
    
    def chunk_text(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text into token-aware pieces.
        
        Args:
            text: Text to chunk
            
        Returns:
            List[Tuple[str, int]]: List of (chunk_text, token_count) tuples
        """
        if not text.strip():
            return []
        
        # If text is already within token limit, return as single chunk
        total_tokens = self.count_tokens(text)
        if total_tokens <= self.max_tokens:
            return [(text.strip(), total_tokens)]
        
        chunks = []
        
        if self.preserve_sentences:
            chunks = self._chunk_by_sentences(text)
        else:
            chunks = self._chunk_by_tokens(text)
        
        return chunks
    
    def _chunk_by_sentences(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text while preserving sentence boundaries.
        
        Args:
            text: Text to chunk
            
        Returns:
            List[Tuple[str, int]]: List of (chunk_text, token_count) tuples
        """
        sentences = self.split_by_sentences(text)
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            # If adding this sentence would exceed the limit
            if current_tokens + sentence_tokens > self.max_tokens and current_chunk:
                # Finalize current chunk
                chunk_text = ' '.join(current_chunk)
                chunks.append((chunk_text, current_tokens))
                
                # Start new chunk with overlap
                overlap_sentences = self._get_overlap_sentences(current_chunk, self.overlap_tokens)
                current_chunk = overlap_sentences + [sentence]
                current_tokens = self.count_tokens(' '.join(current_chunk))
            else:
                # Add sentence to current chunk
                current_chunk.append(sentence)
                current_tokens += sentence_tokens
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunks.append((chunk_text, self.count_tokens(chunk_text)))
        
        return chunks
    
    def _chunk_by_tokens(self, text: str) -> List[Tuple[str, int]]:
        """
        Chunk text by token count without preserving sentence boundaries.
        
        Args:
            text: Text to chunk
            
        Returns:
            List[Tuple[str, int]]: List of (chunk_text, token_count) tuples
        """
        if not self.tokenizer:
            # Fallback to character-based chunking
            return self._chunk_by_characters(text)
        
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = min(start + self.max_tokens, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            
            chunks.append((chunk_text, len(chunk_tokens)))
            
            # Move start position with overlap
            start = end - self.overlap_tokens
            if start < 0:
                start = 0
        
        return chunks
    
    def _chunk_by_characters(self, text: str) -> List[Tuple[str, int]]:
        """
        Fallback character-based chunking.
        
        Args:
            text: Text to chunk
            
        Returns:
            List[Tuple[str, int]]: List of (chunk_text, token_count) tuples
        """
        # Approximate character count per token (OpenAI uses ~4 chars per token)
        chars_per_token = 4
        max_chars = self.max_tokens * chars_per_token
        overlap_chars = self.overlap_tokens * chars_per_token
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + max_chars, len(text))
            chunk_text = text[start:end]
            
            # Try to end at word boundary if possible
            if end < len(text) and not text[end].isspace():
                last_space = chunk_text.rfind(' ')
                if last_space > start + max_chars // 2:  # Only if we don't cut too much
                    end = start + last_space
                    chunk_text = text[start:end]
            
            token_count = self.count_tokens(chunk_text)
            chunks.append((chunk_text.strip(), token_count))
            
            start = end - overlap_chars
            if start < 0:
                start = 0
        
        return chunks
    
    def _get_overlap_sentences(self, sentences: List[str], target_tokens: int) -> List[str]:
        """
        Get sentences for overlap based on token count.
        
        Args:
            sentences: List of sentences
            target_tokens: Target number of tokens for overlap
            
        Returns:
            List[str]: Sentences for overlap
        """
        if not sentences:
            return []
        
        overlap_sentences = []
        tokens_so_far = 0
        
        # Take sentences from the end, working backwards
        for sentence in reversed(sentences):
            sentence_tokens = self.count_tokens(sentence)
            if tokens_so_far + sentence_tokens <= target_tokens:
                overlap_sentences.insert(0, sentence)
                tokens_so_far += sentence_tokens
            else:
                break
        
        return overlap_sentences


class EnhancedContentProcessor:
    """
    Enhanced content processor with token-aware chunking and embedding support.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._content_storage: Dict[str, ContentItem] = {}
        self._chunk_storage: Dict[str, List[ContentChunk]] = {}
        
        # Initialize token-aware chunker
        self.chunker = TokenAwareChunker(
            max_tokens=self.settings.max_chunk_size,
            overlap_tokens=self.settings.chunk_overlap,
            preserve_sentences=self.settings.preserve_sentence_integrity
        )
    
    def ingest_content(self, title: str = None, text: str = "", source: str = None, metadata: Dict[str, Any] = None) -> ContentItem:
        """
        Ingest and process text content with enhanced chunking.
        
        Args:
            title: Optional title for the content
            text: The text content to process
            source: Optional source identifier
            metadata: Optional metadata dictionary
            
        Returns:
            ContentItem: The created content item
            
        Raises:
            ValueError: If text is empty or invalid
        """
        if not text or not text.strip():
            raise ValueError("Text content cannot be empty")
        
        # Clean and normalize text
        text = self._clean_text(text)
        
        # Create content item
        content_id = str(uuid.uuid4())
        content_item = ContentItem(
            id=content_id,
            title=title or f"Content {content_id[:8]}",
            text=text,
            source=source,
            metadata=metadata or {},
            created_at=datetime.now()
        )
        
        # Store content
        self._content_storage[content_id] = content_item
        
        # Process content into token-aware chunks
        chunks = self._chunk_content_enhanced(content_item)
        self._chunk_storage[content_id] = chunks
        
        return content_item
    
    def _clean_text(self, text: str) -> str:
        """
        Clean and normalize text content.
        
        Args:
            text: Raw text to clean
            
        Returns:
            str: Cleaned text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Strip leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _chunk_content_enhanced(self, content: ContentItem) -> List[ContentChunk]:
        """
        Split content into token-aware chunks.
        
        Args:
            content: The content item to chunk
            
        Returns:
            List[ContentChunk]: List of content chunks
        """
        text = content.text
        
        # First, try to split by structural elements (paragraphs)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        chunk_index = 0
        current_position = 0
        
        for paragraph_idx, paragraph in enumerate(paragraphs):
            # Chunk each paragraph using token-aware chunking
            paragraph_chunks = self.chunker.chunk_text(paragraph)
            
            for sub_chunk_idx, (chunk_text, token_count) in enumerate(paragraph_chunks):
                chunk = ContentChunk(
                    id=str(uuid.uuid4()),
                    content_id=content.id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_position=current_position,
                    end_position=current_position + len(chunk_text),
                    token_count=token_count,
                    metadata={
                        "paragraph_index": paragraph_idx,
                        "sub_chunk_index": sub_chunk_idx,
                        "is_structured": len(paragraph_chunks) > 1,
                        "total_sub_chunks": len(paragraph_chunks)
                    }
                )
                chunks.append(chunk)
                chunk_index += 1
                current_position += len(chunk_text)
        
        return chunks
    
    def get_content(self, content_id: str) -> ContentItem:
        """
        Retrieve content by ID.
        
        Args:
            content_id: The content ID
            
        Returns:
            ContentItem: The content item
            
        Raises:
            KeyError: If content not found
        """
        if content_id not in self._content_storage:
            raise KeyError(f"Content with ID {content_id} not found")
        return self._content_storage[content_id]
    
    def get_chunks(self, content_id: str) -> List[ContentChunk]:
        """
        Retrieve chunks for a content item.
        
        Args:
            content_id: The content ID
            
        Returns:
            List[ContentChunk]: List of chunks for the content
            
        Raises:
            KeyError: If content not found
        """
        if content_id not in self._chunk_storage:
            raise KeyError(f"Chunks for content ID {content_id} not found")
        return self._chunk_storage[content_id]
    
    def get_chunk_by_id(self, chunk_id: str) -> ContentChunk:
        """
        Retrieve a specific chunk by its ID.
        
        Args:
            chunk_id: The chunk ID
            
        Returns:
            ContentChunk: The chunk
            
        Raises:
            KeyError: If chunk not found
        """
        for chunks in self._chunk_storage.values():
            for chunk in chunks:
                if chunk.id == chunk_id:
                    return chunk
        raise KeyError(f"Chunk with ID {chunk_id} not found")
    
    def list_content(self) -> List[ContentItem]:
        """
        List all stored content items.
        
        Returns:
            List[ContentItem]: List of all content items
        """
        return list(self._content_storage.values())
    
    def get_content_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored content including token information.
        
        Returns:
            Dict[str, Any]: Statistics about content and chunks
        """
        total_content = len(self._content_storage)
        total_chunks = sum(len(chunks) for chunks in self._chunk_storage.values())
        
        if total_content > 0:
            avg_chunks_per_content = total_chunks / total_content
            total_characters = sum(len(content.text) for content in self._content_storage.values())
            avg_content_length = total_characters / total_content
            
            # Calculate token statistics
            total_tokens = 0
            max_chunk_tokens = 0
            min_chunk_tokens = float('inf')
            
            for chunks in self._chunk_storage.values():
                for chunk in chunks:
                    if chunk.token_count:
                        total_tokens += chunk.token_count
                        max_chunk_tokens = max(max_chunk_tokens, chunk.token_count)
                        min_chunk_tokens = min(min_chunk_tokens, chunk.token_count)
            
            avg_tokens_per_chunk = total_tokens / total_chunks if total_chunks > 0 else 0
            
            if min_chunk_tokens == float('inf'):
                min_chunk_tokens = 0
        else:
            avg_chunks_per_content = 0
            avg_content_length = 0
            total_tokens = 0
            avg_tokens_per_chunk = 0
            max_chunk_tokens = 0
            min_chunk_tokens = 0
        
        return {
            "total_content_items": total_content,
            "total_chunks": total_chunks,
            "average_chunks_per_content": round(avg_chunks_per_content, 2),
            "average_content_length": round(avg_content_length, 2),
            "total_tokens": total_tokens,
            "average_tokens_per_chunk": round(avg_tokens_per_chunk, 2),
            "max_chunk_tokens": max_chunk_tokens,
            "min_chunk_tokens": min_chunk_tokens
        }


# Global enhanced content processor instance
enhanced_content_processor = EnhancedContentProcessor()


def get_enhanced_content_processor() -> EnhancedContentProcessor:
    """Get the global enhanced content processor instance."""
    return enhanced_content_processor
