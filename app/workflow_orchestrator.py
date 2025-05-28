"""
Workflow Orchestrator for Structured Quiz Generation API

Orchestrates the complete workflow from input/ to output/ with comprehensive logging
and consistent file management.
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import json

from app.file_manager import get_file_manager, FileManager
from app.enhanced_logging import get_quiz_logger, QuizLogger
from app.ingestion_pipeline import get_data_ingestion_pipeline
from app.quiz_orchestrator import get_quiz_orchestrator
from app.models import ContentIngestionRequest, QuizGenerationRequest, DifficultyLevel


class WorkflowOrchestrator:
    """
    Orchestrates the complete workflow for quiz generation with structured
    input/output management and comprehensive logging.
    
    Workflow:
    1. Read content from input/ directory
    2. Process and ingest content with full pipeline
    3. Generate quizzes/questions based on processed content
    4. Write all outputs to output/ directory with consistent naming
    5. Log all operations with timestamps and metrics
    """
    
    def __init__(self):
        """Initialize workflow orchestrator."""
        self.file_manager = get_file_manager()
        self.logger = get_quiz_logger("workflow")
        self.ingestion_pipeline = get_data_ingestion_pipeline()
        self.quiz_orchestrator = get_quiz_orchestrator()
        
        # Workflow tracking
        self.current_session_id = None
        self.session_start_time = None
        
    async def start_processing_session(self) -> str:
        """
        Start a new processing session.
        
        Returns:
            Session ID for tracking
        """
        self.session_start_time = datetime.now()
        self.current_session_id = f"session_{self.session_start_time.strftime('%Y%m%d_%H%M%S')}"
        
        session_info = {
            "session_id": self.current_session_id,
            "start_time": self.session_start_time.isoformat(),
            "input_files_available": len(self.file_manager.find_input_files()),
        }
        
        self.logger.info(f"Started processing session: {self.current_session_id}", session_info)
        
        # Create session directory in output
        session_dir = self.file_manager.output_dir / self.current_session_id
        session_dir.mkdir(exist_ok=True)
        
        return self.current_session_id
        
    async def process_all_input_files(self) -> Dict[str, Any]:
        """
        Process all files in the input directory through the complete pipeline.
        
        Returns:
            Processing results summary
        """
        if not self.current_session_id:
            await self.start_processing_session()
            
        with self.logger.processing_context("process_all_inputs"):
            # Find all text files in input directory
            input_files = self.file_manager.find_input_files("*.txt")
            
            if not input_files:
                self.logger.warning("No .txt files found in input directory")
                return {"success": False, "error": "No input files found"}
                
            results = {
                "session_id": self.current_session_id,
                "processed_files": [],
                "ingestion_results": [],
                "errors": []
            }
            
            for input_file in input_files:
                try:
                    result = await self._process_single_file(input_file)
                    results["processed_files"].append(str(input_file))
                    results["ingestion_results"].append(result)
                    
                except Exception as e:
                    error_info = {
                        "file": str(input_file),
                        "error": str(e)
                    }
                    results["errors"].append(error_info)
                    self.logger.error(f"Failed to process file {input_file}", e)
                    
            # Write processing summary
            summary_file = self.file_manager.create_processing_summary(
                "batch_content_ingestion",
                [str(f) for f in input_files],
                [r.get("content_id", "unknown") for r in results["ingestion_results"]],
                {
                    "total_files": len(input_files),
                    "successful": len(results["ingestion_results"]),
                    "failed": len(results["errors"])
                }
            )
            
            self.logger.info(f"Completed batch processing: {len(results['processed_files'])} files")
            return results
            
    async def _process_single_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single input file through ingestion pipeline."""
        self.logger.log_processing_step("read_input_file", {"file": str(file_path)})
        
        # Read file content
        content = self.file_manager.read_input_file(file_path.name)
        
        # Extract title from filename (remove date prefix and version suffix)
        title = self._extract_title_from_filename(file_path.name)
        
        # Run ingestion pipeline
        self.logger.log_processing_step("start_ingestion", {
            "title": title,
            "content_length": len(content)
        })
        
        result = await self.ingestion_pipeline.ingest_content(
            title=title,
            text=content,
            source=f"input_file:{file_path.name}",
            metadata={"original_filename": file_path.name},
            generate_embeddings=True
        )
        
        # Write processed content to output
        if result.get("success"):
            processed_filename = self.file_manager.generate_filename(
                f"processed_{title}", "json"
            )
            
            processed_path = self.file_manager.write_json_output(
                result, processed_filename, "content"
            )
            
            self.logger.log_content_processing(
                result["content_id"], 
                "ingestion_complete",
                input_size=len(content),
                output_size=result.get("chunks_created", 0)
            )
            
        return result
        
    async def generate_quiz_from_content(self, 
                                       content_query: str,
                                       num_questions: int = 5,
                                       difficulty: str = "medium") -> Dict[str, Any]:
        """
        Generate quiz from processed content.
        
        Args:
            content_query: Query to find relevant content
            num_questions: Number of questions to generate
            difficulty: Question difficulty level
            
        Returns:
            Quiz generation results
        """
        if not self.current_session_id:
            await self.start_processing_session()
            
        with self.logger.processing_context("generate_quiz", 
                                           query=content_query, 
                                           num_questions=num_questions):
            try:
                # Generate quiz using orchestrator
                self.logger.log_processing_step("start_quiz_generation", {
                    "query": content_query,
                    "num_questions": num_questions,
                    "difficulty": difficulty
                })
                
                # Generate quiz (unpack tuple) - using correct API
                quiz, metadata = await self.quiz_orchestrator.generate_quiz(
                    title=f"Quiz: {content_query}",
                    description=f"Auto-generated quiz for {content_query}",
                    topic_or_query=content_query,
                    num_questions=num_questions,
                    difficulty=getattr(DifficultyLevel, difficulty.upper(), DifficultyLevel.MEDIUM)
                )
                
                # Prepare results with JSON serializable data
                results = {
                    "quiz": self._serialize_quiz(quiz),
                    "metadata": self._serialize_metadata(metadata),
                    "generation_info": {
                        "timestamp": datetime.now().isoformat(),
                        "session_id": self.current_session_id,
                        "query": content_query
                    }
                }
                
                # Write quiz to output
                quiz_filename = self.file_manager.generate_filename(
                    f"quiz_{content_query.replace(' ', '_')}", "json"
                )
                
                quiz_path = self.file_manager.write_json_output(
                    results, quiz_filename, "quizzes"
                )
                
                question_count = len(quiz.questions) if hasattr(quiz, 'questions') else 0
                
                self.logger.log_quiz_generation(
                    quiz_filename,
                    question_count,
                    content_sources=[content_query],
                    quality_metrics=metadata
                )
                
                return {
                    "success": True,
                    "quiz_file": str(quiz_path),
                    "question_count": question_count,
                    "metadata": metadata
                }
                
            except Exception as e:
                self.logger.error(f"Quiz generation failed for query: {content_query}", e)
                return {
                    "success": False,
                    "error": str(e),
                    "query": content_query
                }
                
    async def generate_questions_from_content(self,
                                            content_query: str,
                                            num_questions: int = 10) -> Dict[str, Any]:
        """
        Generate individual questions from processed content.
        
        Args:
            content_query: Query to find relevant content
            num_questions: Number of questions to generate
            
        Returns:
            Question generation results
        """
        if not self.current_session_id:
            await self.start_processing_session()
            
        with self.logger.processing_context("generate_questions", 
                                           query=content_query, 
                                           num_questions=num_questions):
            try:
                # Generate questions using orchestrator
                self.logger.log_processing_step("start_question_generation", {
                    "query": content_query,
                    "num_questions": num_questions
                })
                
                # Generate questions (unpack tuple) - using correct API
                questions, metadata = await self.quiz_orchestrator.generate_multiple_questions(
                    topic_or_query=content_query,
                    num_questions=num_questions,
                    difficulty=DifficultyLevel.MEDIUM
                )
                
                # Prepare results with JSON serializable data
                results = {
                    "questions": self._serialize_questions(questions),
                    "metadata": self._serialize_metadata(metadata),
                    "generation_info": {
                        "timestamp": datetime.now().isoformat(),
                        "session_id": self.current_session_id,
                        "query": content_query
                    }
                }
                
                # Write questions to output
                questions_filename = self.file_manager.generate_filename(
                    f"questions_{content_query.replace(' ', '_')}", "json"
                )
                
                questions_path = self.file_manager.write_json_output(
                    results, questions_filename, "questions"
                )
                
                self.logger.log_processing_step("questions_generated", {
                    "output_file": str(questions_path),
                    "question_count": len(questions)
                })
                
                return {
                    "success": True,
                    "questions_file": str(questions_path),
                    "question_count": len(questions),
                    "metadata": metadata
                }
                
            except Exception as e:
                self.logger.error(f"Question generation failed for query: {content_query}", e)
                return {
                    "success": False,
                    "error": str(e),
                    "query": content_query
                }
                
    async def complete_session(self) -> Dict[str, Any]:
        """
        Complete current processing session and generate summary.
        
        Returns:
            Session completion summary
        """
        if not self.current_session_id:
            return {"error": "No active session"}
            
        end_time = datetime.now()
        duration = (end_time - self.session_start_time).total_seconds()
        
        # Generate session summary
        session_summary = {
            "session_id": self.current_session_id,
            "start_time": self.session_start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "output_files": self._collect_session_outputs(),
            "performance_metrics": {
                "total_duration": duration,
                "files_processed": len(self.file_manager.find_input_files()),
            }
        }
        
        # Write session summary
        summary_filename = self.file_manager.generate_filename(
            f"session_summary_{self.current_session_id}", "json"
        )
        
        summary_path = self.file_manager.write_json_output(
            session_summary, summary_filename, "logs"
        )
        
        self.logger.info(f"Session completed: {self.current_session_id}", {
            "duration_seconds": duration,
            "summary_file": str(summary_path)
        })
        
        # Reset session
        self.current_session_id = None
        self.session_start_time = None
        
        return session_summary
        
    def _extract_title_from_filename(self, filename: str) -> str:
        """Extract meaningful title from structured filename."""
        # Remove extension
        name_without_ext = filename.rsplit('.', 1)[0]
        
        # Split by underscores
        parts = name_without_ext.split('_')
        
        # Skip date (first part) and version (last part if starts with 'v')
        title_parts = parts[1:]
        if title_parts and title_parts[-1].startswith('v'):
            title_parts = title_parts[:-1]
            
        return ' '.join(title_parts).replace('_', ' ').title()
        
    def _collect_session_outputs(self) -> Dict[str, List[str]]:
        """Collect all output files created in current session."""
        outputs = {
            "content_files": [],
            "quiz_files": [],
            "question_files": [],
            "log_files": []
        }
        
        # Check each output subdirectory
        if self.file_manager.content_dir.exists():
            outputs["content_files"] = [f.name for f in self.file_manager.content_dir.glob("*.json")]
            
        if self.file_manager.quizzes_dir.exists():
            outputs["quiz_files"] = [f.name for f in self.file_manager.quizzes_dir.glob("*.json")]
            
        if self.file_manager.questions_dir.exists():
            outputs["question_files"] = [f.name for f in self.file_manager.questions_dir.glob("*.json")]
            
        if self.file_manager.logs_dir.exists():
            outputs["log_files"] = [f.name for f in self.file_manager.logs_dir.glob("*.json")]
            
        return outputs
    
    def _serialize_quiz(self, quiz) -> dict:
        """Convert quiz object to JSON serializable format."""
        if hasattr(quiz, 'dict'):
            quiz_dict = quiz.dict()
        elif hasattr(quiz, '__dict__'):
            quiz_dict = quiz.__dict__.copy()
        else:
            quiz_dict = quiz
            
        return self._make_json_serializable(quiz_dict)
        
    def _serialize_questions(self, questions) -> list:
        """Convert questions list to JSON serializable format."""
        serialized = []
        for q in questions:
            if hasattr(q, 'dict'):
                q_dict = q.dict()
            elif hasattr(q, '__dict__'):
                q_dict = q.__dict__.copy()
            else:
                q_dict = q
            serialized.append(self._make_json_serializable(q_dict))
        return serialized
        
    def _serialize_metadata(self, metadata) -> dict:
        """Convert metadata to JSON serializable format."""
        if isinstance(metadata, dict):
            return self._make_json_serializable(metadata)
        return metadata
        
    def _make_json_serializable(self, obj):
        """Recursively convert object to JSON serializable format."""
        if isinstance(obj, dict):
            return {k: self._make_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, tuple):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, set):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'isoformat'):  # Other datetime-like objects
            return obj.isoformat()
        elif hasattr(obj, 'value'):  # Handle enums
            return obj.value
        elif hasattr(obj, '_value_'):  # Handle Pydantic enums
            return obj._value_
        elif str(type(obj)) == "<class 'mappingproxy'>":
            return self._make_json_serializable(dict(obj))
        elif hasattr(obj, '__dict__'):
            return self._make_json_serializable(obj.__dict__)
        elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
            try:
                return [self._make_json_serializable(item) for item in obj]
            except:
                return str(obj)
        else:
            # For any other types, try to convert to string as fallback
            try:
                # Check if it's a basic JSON-serializable type
                if obj is None or isinstance(obj, (bool, int, float, str)):
                    return obj
                return str(obj)
            except:
                return str(obj)


# Global workflow orchestrator
_workflow_orchestrator = None

def get_workflow_orchestrator() -> WorkflowOrchestrator:
    """Get or create global workflow orchestrator instance."""
    global _workflow_orchestrator
    if _workflow_orchestrator is None:
        _workflow_orchestrator = WorkflowOrchestrator()
    return _workflow_orchestrator
