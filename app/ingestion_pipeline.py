"""
Integrated data ingestion pipeline for Sprint 2.
Combines enhanced content processing, embedding generation, and vector storage.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.models import ContentItem, ContentChunk, VectorSearchResult
from app.enhanced_content_processor import get_enhanced_content_processor
from app.embedding_generator import get_embedding_generator
from app.simple_vector_store import get_knowledge_base
from app.config import get_settings

logger = logging.getLogger(__name__)


class DataIngestionPipeline:
    """
    Complete data ingestion pipeline that processes content through all stages:
    1. Content chunking (token-aware)
    2. Embedding generation
    3. Vector storage
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.content_processor = get_enhanced_content_processor()
        self.embedding_generator = get_embedding_generator()
        self.knowledge_base = get_knowledge_base()
        
        # Connect embedding generator to knowledge base
        self.knowledge_base.set_embedding_generator(self.embedding_generator)
        
        # Register semantic search function with global retrieval engine using knowledge base
        try:
            from app.retrieval_engine import get_retrieval_engine
            engine = get_retrieval_engine()
            # Use knowledge base text search for semantic search
            engine.set_semantic_search(self.knowledge_base.search_by_text)
            logger.info("Registered knowledge_base.search_by_text with global retrieval engine")
        except Exception as e:
            logger.warning(f"Failed to register semantic search with retrieval engine: {e}")
    
    async def ingest_content(
        self, 
        title: str = None, 
        text: str = "", 
        source: str = None, 
        metadata: Dict[str, Any] = None,
        generate_embeddings: bool = True
    ) -> Dict[str, Any]:
        """
        Complete content ingestion pipeline.
        
        Args:
            title: Optional title for the content
            text: The text content to process
            source: Optional source identifier
            metadata: Optional metadata dictionary
            generate_embeddings: Whether to generate embeddings and store in vector DB
            
        Returns:
            Dict[str, Any]: Ingestion results including content_id, chunks_created, etc.
        """
        start_time = datetime.now()
        
        try:
            # Step 1: Process content and create chunks
            logger.info("Step 1: Processing content and creating chunks")
            content_item = self.content_processor.ingest_content(
                title=title,
                text=text,
                source=source,
                metadata=metadata
            )
            
            chunks = self.content_processor.get_chunks(content_item.id)
            logger.info(f"Created {len(chunks)} chunks from content")
            
            embedded_chunks = []
            vectors_stored = 0
            
            if generate_embeddings and chunks:
                # Step 2: Generate embeddings
                logger.info("Step 2: Generating embeddings")
                embedded_chunks = await self.embedding_generator.embed_chunks(chunks)
                logger.info(f"Generated embeddings for {len(embedded_chunks)} chunks")
                
                # Step 3: Store in vector database
                logger.info("Step 3: Storing in vector database")
                vectors_stored = self.knowledge_base.add_chunks(embedded_chunks)
                # Also register chunks with global retrieval engine for lexical search
                try:
                    from app.retrieval_engine import get_retrieval_engine
                    engine = get_retrieval_engine()
                    engine.add_chunks(embedded_chunks)
                    logger.info(f"Registered {len(embedded_chunks)} chunks with retrieval engine")
                except Exception as e:
                    logger.warning(f"Failed to register chunks with retrieval engine: {e}")
                logger.info(f"Stored {vectors_stored} vectors in knowledge base")
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # Prepare results
            results = {
                "success": True,
                "content_id": content_item.id,
                "content_title": content_item.title,
                "chunks_created": len(chunks),
                "embeddings_generated": len(embedded_chunks),
                "vectors_stored": vectors_stored,
                "processing_time_seconds": round(processing_time, 2),
                "average_chunk_tokens": sum(chunk.token_count or 0 for chunk in chunks) // len(chunks) if chunks else 0,
                "total_tokens": sum(chunk.token_count or 0 for chunk in chunks),
                "source": source,
                "metadata": metadata or {}
            }
            
            logger.info(f"Successfully ingested content {content_item.id} in {processing_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Content ingestion failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time_seconds": (datetime.now() - start_time).total_seconds()
            }
    
    async def search_content(
        self,
        query: str,
        max_results: int = None,
        search_mode: str = "AUTO"
    ) -> List[VectorSearchResult]:
        """
        Search for content using specified search mode via unified retrieval engine.
        """
        from app.retrieval_engine import get_retrieval_engine, SearchMode
        try:
            # Resolve search mode by name (uses enum member names)
            mode = SearchMode[search_mode.upper()]
        except KeyError:
            raise RuntimeError(f"Invalid search_mode: {search_mode}")
        try:
            engine = get_retrieval_engine()
            results = await engine.retrieve(
                query=query,
                mode=mode,
                max_results=max_results
            )
            logger.info(f"Found {len(results)} results for query: '{query[:50]}...' using {mode} mode")
            return results
        except Exception as e:
            logger.error(f"Content search failed: {e}")
            raise RuntimeError(f"Search failed: {e}")
    
    def get_content_by_id(self, content_id: str) -> ContentItem:
        """
        Retrieve content by ID.
        
        Args:
            content_id: Content ID
            
        Returns:
            ContentItem: Content item
        """
        return self.content_processor.get_content(content_id)
    
    def get_chunks_by_content_id(self, content_id: str) -> List[ContentChunk]:
        """
        Retrieve chunks for a content item.
        
        Args:
            content_id: Content ID
            
        Returns:
            List[ContentChunk]: List of chunks
        """
        return self.content_processor.get_chunks(content_id)
    
    def list_all_content(self) -> List[ContentItem]:
        """
        List all stored content items.
        
        Returns:
            List[ContentItem]: List of all content items
        """
        return self.content_processor.list_content()
    
    def get_pipeline_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the ingestion pipeline.
        
        Returns:
            Dict[str, Any]: Pipeline statistics
        """
        try:
            content_stats = self.content_processor.get_content_statistics()
            vector_stats = self.knowledge_base.get_stats()
            embedding_info = self.embedding_generator.get_embedding_info()
            
            return {
                "content_processing": content_stats,
                "vector_storage": vector_stats,
                "embedding_generation": embedding_info,
                "pipeline_health": {
                    "content_processor_active": True,
                    "embedding_generator_active": embedding_info.get("client_initialized", False),
                    "vector_store_active": vector_stats.get("total_vectors", 0) >= 0,
                    "api_key_configured": embedding_info.get("api_key_configured", False)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get pipeline statistics: {e}")
            return {
                "error": str(e),
                "pipeline_health": {"status": "error"}
            }
    
    async def test_pipeline(self, test_text: str = None) -> Dict[str, Any]:
        """
        Test the complete ingestion pipeline with sample content.
        
        Args:
            test_text: Optional test text (uses default if not provided)
            
        Returns:
            Dict[str, Any]: Test results
        """
        if test_text is None:
            test_text = """
            This is a test document for the Quiz Generation application.
            
            The application uses advanced natural language processing to create educational quizzes
            from study materials. It employs token-aware chunking to break down large documents
            into manageable pieces that can be processed by language models.
            
            The system generates embeddings for each chunk using OpenAI's embedding models,
            allowing for semantic search and retrieval. This enables the application to find
            relevant content when generating quiz questions.
            
            The vector storage system uses FAISS for efficient similarity search, making it
            possible to quickly retrieve relevant content chunks based on semantic similarity
            rather than just keyword matching.
            """
        
        logger.info("Starting pipeline test")
        
        try:
            # Test full ingestion
            ingestion_result = await self.ingest_content(
                title="Pipeline Test Document",
                text=test_text,
                source="pipeline_test",
                metadata={"test": True, "timestamp": datetime.now().isoformat()}
            )
            
            if not ingestion_result["success"]:
                return {
                    "success": False,
                    "stage": "ingestion",
                    "error": ingestion_result.get("error"),
                    "details": ingestion_result
                }
            
            # Test search
            search_results = await self.search_content(
                query="quiz generation application",
                max_results=3
            )
            
            # Test embedding directly
            embedding_test = await self.embedding_generator.test_embedding()
            
            return {
                "success": True,
                "ingestion": ingestion_result,
                "search": {
                    "query": "quiz generation application",
                    "results_count": len(search_results),
                    "top_similarity": search_results[0].similarity_score if search_results else 0,
                    "results": [
                        {
                            "chunk_id": r.chunk_id,
                            "similarity": r.similarity_score,
                            "text_preview": r.chunk_text[:100] + "..." if len(r.chunk_text) > 100 else r.chunk_text
                        }
                        for r in search_results[:3]
                    ]
                },
                "embedding_test": embedding_test,
                "pipeline_stats": self.get_pipeline_statistics()
            }
            
        except Exception as e:
            logger.error(f"Pipeline test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "stage": "unknown"
            }
    
    async def save_pipeline_state(self, filepath: str = None) -> bool:
        """
        Save the current state of the pipeline to disk.
        
        Args:
            filepath: Optional filepath for vector index
            
        Returns:
            bool: True if successfully saved
        """
        try:
            success = self.knowledge_base.save(filepath)
            if success:
                logger.info("Pipeline state saved successfully")
            else:
                logger.warning("Failed to save pipeline state")
            return success
            
        except Exception as e:
            logger.error(f"Failed to save pipeline state: {e}")
            return False
    
    def clear_pipeline_data(self):
        """Clear all data from the pipeline (useful for testing)."""
        try:
            self.knowledge_base.clear()
            # Note: Content processor data is in-memory, so it will persist
            # until the application restarts
            logger.info("Cleared pipeline data")
        except Exception as e:
            logger.error(f"Failed to clear pipeline data: {e}")


# Global pipeline instance
data_ingestion_pipeline = DataIngestionPipeline()


def get_data_ingestion_pipeline() -> DataIngestionPipeline:
    """Get the global data ingestion pipeline instance."""
    return data_ingestion_pipeline
