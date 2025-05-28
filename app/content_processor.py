"""
Content ingestion module for processing and chunking text content.
This is a stub implementation that will be extended in Sprint 2.
"""

import uuid
from typing import List, Dict, Any
from datetime import datetime
import re

from app.models import ContentItem, ContentChunk
from app.config import get_settings


class ContentProcessor:
    """
    Handles content ingestion and processing.
    Current implementation provides basic text chunking functionality.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._content_storage: Dict[str, ContentItem] = {}
        self._chunk_storage: Dict[str, List[ContentChunk]] = {}
    
    def ingest_content(self, title: str = None, text: str = "", source: str = None, metadata: Dict[str, Any] = None) -> ContentItem:
        """
        Ingest and process text content.
        
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
        
        # Create content item
        content_id = str(uuid.uuid4())
        content_item = ContentItem(
            id=content_id,
            title=title or f"Content {content_id[:8]}",
            text=text.strip(),
            source=source,
            metadata=metadata or {},
            created_at=datetime.now()
        )
        
        # Store content
        self._content_storage[content_id] = content_item
        
        # Process content into chunks
        chunks = self._chunk_content(content_item)
        self._chunk_storage[content_id] = chunks
        
        return content_item
    
    def _chunk_content(self, content: ContentItem) -> List[ContentChunk]:
        """
        Split content into chunks for processing.
        Current implementation uses simple paragraph and sentence-based splitting.
        
        Args:
            content: The content item to chunk
            
        Returns:
            List[ContentChunk]: List of content chunks
        """
        text = content.text
        max_chunk_size = self.settings.max_chunk_size
        overlap = self.settings.chunk_overlap
        
        # First, try to split by paragraphs
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        chunks = []
        chunk_index = 0
        current_position = 0
        
        for paragraph in paragraphs:
            if len(paragraph) <= max_chunk_size:
                # Paragraph fits in one chunk
                chunk = ContentChunk(
                    id=str(uuid.uuid4()),
                    content_id=content.id,
                    text=paragraph,
                    chunk_index=chunk_index,
                    start_position=current_position,
                    end_position=current_position + len(paragraph),
                    metadata={"paragraph_index": len(chunks)}
                )
                chunks.append(chunk)
                chunk_index += 1
                current_position += len(paragraph) + 2  # +2 for \n\n
            else:
                # Split large paragraph into smaller chunks
                sub_chunks = self._split_large_text(paragraph, max_chunk_size, overlap)
                for i, sub_chunk in enumerate(sub_chunks):
                    chunk = ContentChunk(
                        id=str(uuid.uuid4()),
                        content_id=content.id,
                        text=sub_chunk,
                        chunk_index=chunk_index,
                        start_position=current_position,
                        end_position=current_position + len(sub_chunk),
                        metadata={
                            "paragraph_index": len(chunks),
                            "sub_chunk_index": i,
                            "is_sub_chunk": True
                        }
                    )
                    chunks.append(chunk)
                    chunk_index += 1
                    current_position += len(sub_chunk)
        
        return chunks
    
    def _split_large_text(self, text: str, max_size: int, overlap: int) -> List[str]:
        """
        Split large text into smaller chunks with overlap.
        
        Args:
            text: Text to split
            max_size: Maximum size per chunk
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List[str]: List of text chunks
        """
        if len(text) <= max_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + max_size
            
            if end >= len(text):
                # Last chunk
                chunks.append(text[start:])
                break
            
            # Try to find a sentence boundary near the end
            chunk_text = text[start:end]
            
            # Look for sentence endings (., !, ?) in the last part of the chunk
            sentence_end = -1
            for i in range(len(chunk_text) - 1, max(0, len(chunk_text) - 100), -1):
                if chunk_text[i] in '.!?' and i < len(chunk_text) - 1 and chunk_text[i + 1].isspace():
                    sentence_end = i + 1
                    break
            
            if sentence_end > 0:
                # Split at sentence boundary
                chunks.append(text[start:start + sentence_end])
                start = start + sentence_end - overlap
            else:
                # Split at word boundary
                words = chunk_text.split()
                if len(words) > 1:
                    # Remove the last incomplete word
                    chunk_text = ' '.join(words[:-1])
                    chunks.append(chunk_text)
                    start = start + len(chunk_text) - overlap
                else:
                    # Force split if no word boundaries
                    chunks.append(chunk_text)
                    start = end - overlap
            
            # Ensure we don't go backwards
            if start < 0:
                start = 0
        
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
    
    def list_content(self) -> List[ContentItem]:
        """
        List all stored content items.
        
        Returns:
            List[ContentItem]: List of all content items
        """
        return list(self._content_storage.values())
    
    def get_content_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about stored content.
        
        Returns:
            Dict[str, Any]: Statistics about content and chunks
        """
        total_content = len(self._content_storage)
        total_chunks = sum(len(chunks) for chunks in self._chunk_storage.values())
        
        if total_content > 0:
            avg_chunks_per_content = total_chunks / total_content
            total_characters = sum(len(content.text) for content in self._content_storage.values())
            avg_content_length = total_characters / total_content
        else:
            avg_chunks_per_content = 0
            avg_content_length = 0
        
        return {
            "total_content_items": total_content,
            "total_chunks": total_chunks,
            "average_chunks_per_content": round(avg_chunks_per_content, 2),
            "average_content_length": round(avg_content_length, 2)
        }


# Global content processor instance
content_processor = ContentProcessor()


def get_content_processor() -> ContentProcessor:
    """Get the global content processor instance."""
    return content_processor
