#!/usr/bin/env python3
"""
Debug the BM25 index to see what's actually stored.
"""

import pickle
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import get_settings

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def debug_bm25_index():
    """Debug the BM25 index contents."""
    logger.info("Debugging BM25 index contents...")
    
    try:
        settings = get_settings()
        filepath = os.path.join(os.path.dirname(settings.vector_index_path), "bm25_index.pkl")
        
        logger.info(f"Loading index from: {filepath}")
        
        if not os.path.exists(filepath):
            logger.error(f"Index file not found: {filepath}")
            return
        
        with open(filepath, 'rb') as f:
            index_data = pickle.load(f)
        
        logger.info(f"Index data keys: {list(index_data.keys())}")
        
        chunks = index_data.get('chunks', [])
        processed_texts = index_data.get('processed_texts', [])
        chunk_id_to_index = index_data.get('chunk_id_to_index', {})
        
        logger.info(f"Number of chunks: {len(chunks)}")
        logger.info(f"Number of processed texts: {len(processed_texts)}")
        logger.info(f"Chunk ID to index mapping: {len(chunk_id_to_index)}")
        
        # Show first few chunks
        for i, chunk in enumerate(chunks[:3]):
            logger.info(f"Chunk {i}:")
            logger.info(f"  ID: {chunk.id}")
            logger.info(f"  Content ID: {chunk.content_id}")
            logger.info(f"  Text (first 200 chars): {chunk.text[:200]}...")
            
            if i < len(processed_texts):
                processed = processed_texts[i]
                logger.info(f"  Processed tokens ({len(processed)}): {processed[:10]}...")
        
        # Check if there are any non-empty processed texts
        non_empty_processed = [pt for pt in processed_texts if pt]
        logger.info(f"Non-empty processed texts: {len(non_empty_processed)}")
        
        if non_empty_processed:
            logger.info(f"Sample processed text: {non_empty_processed[0][:10]}")
        
        # Check for common tokens
        all_tokens = set()
        for pt in processed_texts:
            all_tokens.update(pt)
        
        logger.info(f"Total unique tokens: {len(all_tokens)}")
        if all_tokens:
            logger.info(f"Sample tokens: {list(all_tokens)[:20]}")
        
    except Exception as e:
        logger.error(f"Error debugging index: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function."""
    logger.info("BM25 Index Debug Tool")
    logger.info("=" * 40)
    
    debug_bm25_index()


if __name__ == "__main__":
    main()
