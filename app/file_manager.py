"""
File Management System for Quiz Generation API

Provides structured workflow management with input/ and output/ directories,
consistent naming conventions, and comprehensive logging.
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
import uuid
import shutil

logger = logging.getLogger(__name__)


class FileManager:
    """
    Centralized file management system for the Quiz Generation API.
    
    Features:
    - Structured input/output directory workflow
    - Consistent naming convention: YYYYMMDD_<description>_<version>.ext
    - Comprehensive logging with timestamps
    - File operation tracking and versioning
    """
    
    def __init__(self, base_path: str = None):
        """Initialize file manager with base project path."""
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.input_dir = self.base_path / "input"
        self.output_dir = self.base_path / "output"
        
        # Create subdirectories in output
        self.logs_dir = self.output_dir / "logs"
        self.content_dir = self.output_dir / "content"
        self.quizzes_dir = self.output_dir / "quizzes"
        self.questions_dir = self.output_dir / "questions"
        self.processing_dir = self.output_dir / "processing"
        
        # Ensure all directories exist
        self._ensure_directories()
        
        # Initialize logging for file operations
        self._setup_file_logging()
        
    def _ensure_directories(self):
        """Create all required directories if they don't exist."""
        directories = [
            self.input_dir, self.output_dir, self.logs_dir,
            self.content_dir, self.quizzes_dir, self.questions_dir,
            self.processing_dir
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            
    def _setup_file_logging(self):
        """Setup dedicated file operation logging."""
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = self.logs_dir / f"{timestamp}_file_operations_v1.log"
        
        # Create file handler
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        logger.addHandler(file_handler)
        logger.info("File manager initialized successfully")
        
    def generate_filename(self, description: str, extension: str, 
                         version: int = 1, date: datetime = None) -> str:
        """
        Generate consistent filename using YYYYMMDD_<description>_<version>.ext format.
        
        Args:
            description: Descriptive name for the file
            extension: File extension (without dot)
            version: Version number (default: 1)
            date: Date to use (default: current date)
            
        Returns:
            Formatted filename string
        """
        if date is None:
            date = datetime.now()
            
        date_str = date.strftime("%Y%m%d")
        # Clean description: replace spaces/special chars with underscores
        clean_desc = "".join(c if c.isalnum() else "_" for c in description).strip("_")
        
        filename = f"{date_str}_{clean_desc}_v{version}.{extension}"
        logger.info(f"Generated filename: {filename}")
        return filename
        
    def find_input_files(self, pattern: str = "*") -> List[Path]:
        """
        Find files in input directory matching pattern.
        
        Args:
            pattern: Glob pattern to match files
            
        Returns:
            List of Path objects for matching files
        """
        files = list(self.input_dir.glob(pattern))
        logger.info(f"Found {len(files)} input files matching pattern '{pattern}'")
        return files
        
    def read_input_file(self, filename: str) -> str:
        """
        Read content from input directory file.
        
        Args:
            filename: Name of file in input directory
            
        Returns:
            File content as string
        """
        file_path = self.input_dir / filename
        
        if not file_path.exists():
            raise FileNotFoundError(f"Input file not found: {filename}")
            
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        logger.info(f"Read input file: {filename} ({len(content)} characters)")
        return content
        
    def write_output_file(self, content: str, filename: str, 
                         subdirectory: str = None) -> Path:
        """
        Write content to output directory file.
        
        Args:
            content: Content to write
            filename: Output filename
            subdirectory: Optional subdirectory within output (e.g., 'content', 'quizzes')
            
        Returns:
            Path to written file
        """
        if subdirectory:
            output_path = self.output_dir / subdirectory / filename
        else:
            output_path = self.output_dir / filename
            
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        logger.info(f"Wrote output file: {output_path} ({len(content)} characters)")
        return output_path
        
    def write_json_output(self, data: Dict[Any, Any], filename: str, 
                         subdirectory: str = None) -> Path:
        """
        Write JSON data to output directory.
        
        Args:
            data: Dictionary data to write as JSON
            filename: Output filename
            subdirectory: Optional subdirectory within output
            
        Returns:
            Path to written file
        """
        if subdirectory:
            output_path = self.output_dir / subdirectory / filename
        else:
            output_path = self.output_dir / filename
            
        # Ensure parent directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Wrote JSON output file: {output_path}")
        return output_path
        
    def log_processing_step(self, step_name: str, details: Dict[str, Any] = None):
        """
        Log a processing step with timestamp and details.
        
        Args:
            step_name: Name of the processing step
            details: Optional dictionary of step details
        """
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "step": step_name,
            "details": details or {}
        }
        
        logger.info(f"Processing step: {step_name} - {details}")
        
        # Also write to processing log file
        log_filename = self.generate_filename("processing_log", "json")
        log_path = self.logs_dir / log_filename
        
        # Append to existing log or create new
        if log_path.exists():
            with open(log_path, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
            
        logs.append(log_entry)
        
        with open(log_path, 'w') as f:
            json.dump(logs, f, indent=2)
            
    def create_processing_summary(self, operation: str, 
                                input_files: List[str],
                                output_files: List[str],
                                metrics: Dict[str, Any] = None) -> Path:
        """
        Create a comprehensive processing summary file.
        
        Args:
            operation: Name of the operation performed
            input_files: List of input files processed
            output_files: List of output files created
            metrics: Optional processing metrics
            
        Returns:
            Path to summary file
        """
        timestamp = datetime.now()
        summary = {
            "operation": operation,
            "timestamp": timestamp.isoformat(),
            "session_id": str(uuid.uuid4()),
            "input_files": input_files,
            "output_files": output_files,
            "metrics": metrics or {},
            "processing_time": timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        filename = self.generate_filename(f"{operation}_summary", "json", date=timestamp)
        summary_path = self.write_json_output(summary, filename, "logs")
        
        logger.info(f"Created processing summary: {summary_path}")
        return summary_path
        
    def get_latest_file(self, pattern: str, directory: str = "output") -> Optional[Path]:
        """
        Get the most recently created file matching pattern.
        
        Args:
            pattern: Glob pattern to match files
            directory: Directory to search ('input' or 'output')
            
        Returns:
            Path to latest file or None if no files found
        """
        search_dir = self.input_dir if directory == "input" else self.output_dir
        files = list(search_dir.rglob(pattern))
        
        if not files:
            return None
            
        # Sort by creation time (newest first)
        latest_file = max(files, key=lambda f: f.stat().st_ctime)
        logger.info(f"Latest file matching '{pattern}': {latest_file}")
        return latest_file
        
    def archive_processed_inputs(self, archive_name: str = None) -> Path:
        """
        Archive processed input files with timestamp.
        
        Args:
            archive_name: Optional custom archive name
            
        Returns:
            Path to created archive
        """
        if archive_name is None:
            archive_name = self.generate_filename("processed_inputs_archive", "tar.gz")
        else:
            archive_name = self.generate_filename(archive_name, "tar.gz")
            
        archive_path = self.output_dir / archive_name
        
        # Create tar archive of input directory
        shutil.make_archive(
            str(archive_path).replace('.tar.gz', ''), 
            'gztar', 
            str(self.input_dir)
        )
        
        logger.info(f"Archived input files to: {archive_path}")
        return archive_path


# Global file manager instance
_file_manager = None

def get_file_manager(base_path: str = None) -> FileManager:
    """Get or create global file manager instance."""
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager(base_path)
    return _file_manager
