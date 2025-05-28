#!/usr/bin/env python3
"""
Workflow Demonstration Script

Demonstrates the structured workflow system for the Quiz Generation API:
- Input/output directory management
- Consistent file naming conventions
- Comprehensive logging
- End-to-end content processing

Usage:
    python workflow_demo.py
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

# Add the app directory to Python path
import sys
sys.path.append(str(Path(__file__).parent / "app"))

from app.file_manager import get_file_manager
from app.enhanced_logging import get_quiz_logger
from app.workflow_orchestrator import get_workflow_orchestrator


async def demonstrate_workflow():
    """Demonstrate the complete workflow system."""
    
    print("🚀 Quiz Generation API - Structured Workflow Demonstration")
    print("=" * 70)
    
    # Initialize components
    file_manager = get_file_manager()
    logger = get_quiz_logger("demo")
    workflow = get_workflow_orchestrator()
    
    # Step 1: Show directory structure
    print("\n📁 Directory Structure:")
    print(f"   Input:  {file_manager.input_dir}")
    print(f"   Output: {file_manager.output_dir}")
    print(f"   Logs:   {file_manager.logs_dir}")
    
    # Step 2: Check input files
    input_files = file_manager.find_input_files("*.txt")
    print(f"\n📥 Found {len(input_files)} input files:")
    for file in input_files:
        print(f"   - {file.name}")
    
    if not input_files:
        print("   ⚠️  No input files found. Please add .txt files to the input/ directory.")
        return
    
    # Step 3: Start processing session
    print("\n🔄 Starting Processing Session...")
    session_id = await workflow.start_processing_session()
    print(f"   Session ID: {session_id}")
    
    # Step 4: Process input files
    print("\n📊 Processing Input Files...")
    try:
        results = await workflow.process_all_input_files()
        
        if results.get("processed_files"):
            print(f"   ✅ Successfully processed {len(results['processed_files'])} files")
            for file in results["processed_files"]:
                print(f"      - {Path(file).name}")
        
        if results.get("errors"):
            print(f"   ❌ {len(results['errors'])} files had errors")
            for error in results["errors"]:
                print(f"      - {error['file']}: {error['error']}")
                
    except Exception as e:
        print(f"   ❌ Processing failed: {e}")
        return
    
    # Step 5: Demonstrate quiz generation
    print("\n🎯 Generating Sample Quiz...")
    test_queries = [
        "cardiovascular disease",
        "pharmacology",
        "medical procedures"
    ]
    
    for query in test_queries[:1]:  # Test one query
        try:
            quiz_result = await workflow.generate_quiz_from_content(
                content_query=query,
                num_questions=3,
                difficulty="medium"
            )
            
            if quiz_result.get("success"):
                print(f"   ✅ Generated {quiz_result['question_count']} questions for '{query}'")
                print(f"      Output: {Path(quiz_result['quiz_file']).name}")
            else:
                print(f"   ❌ Quiz generation failed for '{query}': {quiz_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Quiz generation error for '{query}': {e}")
    
    # Step 6: Demonstrate question generation
    print("\n❓ Generating Sample Questions...")
    
    for query in test_queries[:1]:  # Test one query
        try:
            questions_result = await workflow.generate_questions_from_content(
                content_query=query,
                num_questions=5
            )
            
            if questions_result.get("success"):
                print(f"   ✅ Generated {questions_result['question_count']} questions for '{query}'")
                print(f"      Output: {Path(questions_result['questions_file']).name}")
            else:
                print(f"   ❌ Question generation failed for '{query}': {questions_result.get('error')}")
                
        except Exception as e:
            print(f"   ❌ Question generation error for '{query}': {e}")
    
    # Step 7: Complete session
    print("\n🏁 Completing Session...")
    try:
        session_summary = await workflow.complete_session()
        print(f"   ✅ Session completed successfully")
        print(f"   Duration: {session_summary.get('duration_seconds', 0):.1f} seconds")
        
        # Show output files created
        output_files = session_summary.get("output_files", {})
        total_files = sum(len(files) for files in output_files.values())
        print(f"   📄 Created {total_files} output files:")
        
        for category, files in output_files.items():
            if files:
                print(f"      {category}: {len(files)} files")
        
    except Exception as e:
        print(f"   ❌ Session completion error: {e}")
    
    # Step 8: Show file naming convention examples
    print("\n📝 File Naming Convention Examples:")
    timestamp = datetime.now()
    examples = [
        file_manager.generate_filename("medical_content", "txt", 1, timestamp),
        file_manager.generate_filename("quiz_cardiovascular", "json", 1, timestamp),
        file_manager.generate_filename("processing_log", "json", 2, timestamp),
        file_manager.generate_filename("session_summary", "json", 1, timestamp)
    ]
    
    for example in examples:
        print(f"   - {example}")
    
    # Step 9: Show logging capabilities
    print("\n📊 Logging Demonstration:")
    logger.info("Demo completed successfully", {
        "session_id": session_id,
        "input_files_processed": len(input_files),
        "demo_timestamp": datetime.now().isoformat()
    })
    
    logger.log_performance_metrics("workflow_demo", {
        "total_files": len(input_files),
        "demo_duration": "completed",
        "features_demonstrated": [
            "directory_structure",
            "file_processing",
            "quiz_generation",
            "question_generation",
            "session_management",
            "logging"
        ]
    })
    
    print("   ✅ Logged demo metrics and performance data")
    print(f"   📁 Log files available in: {file_manager.logs_dir}")
    
    print("\n" + "=" * 70)
    print("🎉 Workflow demonstration completed successfully!")
    print("\nKey Features Demonstrated:")
    print("✅ Structured input/output directory workflow")
    print("✅ Consistent YYYYMMDD_<description>_<version>.ext naming")
    print("✅ Comprehensive logging with timestamps")
    print("✅ End-to-end content processing pipeline")
    print("✅ Quiz and question generation with metadata")
    print("✅ Session management and performance tracking")


def main():
    """Main demonstration function."""
    try:
        asyncio.run(demonstrate_workflow())
    except KeyboardInterrupt:
        print("\n\n⚠️  Demo interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
