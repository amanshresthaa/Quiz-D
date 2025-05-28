"""
Enhanced Logging System for Quiz Generation API

Provides comprehensive logging with timestamps, structured output,
and integration with the file management system.
"""

import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
import json
from contextlib import contextmanager

from app.file_manager import get_file_manager


class StructuredFormatter(logging.Formatter):
    """Custom formatter that creates structured log entries."""
    
    def format(self, record):
        """Format log record with structured data."""
        # Base log data
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
            
        return json.dumps(log_data, ensure_ascii=False)


class QuizLogger:
    """
    Enhanced logging system for the Quiz Generation API.
    
    Features:
    - Structured JSON logging
    - Multiple output formats (console, file, structured)
    - Processing step tracking
    - Performance metrics logging
    - Error analysis and reporting
    """
    
    def __init__(self, name: str = "quiz_api"):
        """Initialize enhanced logger."""
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)
        
        # Get file manager
        self.file_manager = get_file_manager()
        
        # Setup handlers
        self._setup_handlers()
        
        # Processing context
        self._processing_context = {}
        
    def _setup_handlers(self):
        """Setup logging handlers for different outputs."""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler with simple format
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)
        
        # File handler with detailed format
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = self.file_manager.logs_dir / f"{timestamp}_api_detailed_v1.log"
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # Structured JSON handler
        json_file = self.file_manager.logs_dir / f"{timestamp}_api_structured_v1.jsonl"
        json_handler = logging.FileHandler(json_file)
        json_handler.setLevel(logging.INFO)
        json_handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(json_handler)
        
    def info(self, message: str, extra_data: Dict[str, Any] = None):
        """Log info message with optional structured data."""
        if extra_data:
            self.logger.info(message, extra={'extra_data': extra_data})
        else:
            self.logger.info(message)
            
    def warning(self, message: str, extra_data: Dict[str, Any] = None):
        """Log warning message with optional structured data."""
        if extra_data:
            self.logger.warning(message, extra={'extra_data': extra_data})
        else:
            self.logger.warning(message)
            
    def error(self, message: str, exception: Exception = None, extra_data: Dict[str, Any] = None):
        """Log error message with optional exception and structured data."""
        extra = {'extra_data': extra_data} if extra_data else {}
        if exception:
            self.logger.error(message, exc_info=exception, extra=extra)
        else:
            self.logger.error(message, extra=extra)
            
    def debug(self, message: str, extra_data: Dict[str, Any] = None):
        """Log debug message with optional structured data."""
        if extra_data:
            self.logger.debug(message, extra={'extra_data': extra_data})
        else:
            self.logger.debug(message)
            
    @contextmanager
    def processing_context(self, operation: str, **context):
        """Context manager for tracking processing operations."""
        start_time = datetime.now()
        operation_id = f"{operation}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        # Set processing context
        self._processing_context = {
            "operation_id": operation_id,
            "operation": operation,
            "start_time": start_time.isoformat(),
            **context
        }
        
        self.info(f"Started processing operation: {operation}", {
            "operation_id": operation_id,
            "context": context
        })
        
        try:
            yield operation_id
        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.error(f"Processing operation failed: {operation}", e, {
                "operation_id": operation_id,
                "duration_seconds": duration,
                "context": context
            })
            raise
        else:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            self.info(f"Completed processing operation: {operation}", {
                "operation_id": operation_id,
                "duration_seconds": duration,
                "context": context
            })
        finally:
            # Clear processing context
            self._processing_context = {}
            
    def log_processing_step(self, step_name: str, details: Dict[str, Any] = None):
        """Log a processing step within current context."""
        step_data = {
            "step": step_name,
            "processing_context": self._processing_context,
            "details": details or {}
        }
        
        self.info(f"Processing step: {step_name}", step_data)
        
        # Also log to file manager
        self.file_manager.log_processing_step(step_name, details)
        
    def log_performance_metrics(self, operation: str, metrics: Dict[str, Any]):
        """Log performance metrics for an operation."""
        timestamp = datetime.now()
        
        performance_data = {
            "operation": operation,
            "timestamp": timestamp.isoformat(),
            "metrics": metrics
        }
        
        self.info(f"Performance metrics for {operation}", performance_data)
        
        # Write to dedicated performance log
        filename = self.file_manager.generate_filename("performance_metrics", "json")
        
        # Read existing metrics or create new list
        perf_file = self.file_manager.logs_dir / filename
        if perf_file.exists():
            with open(perf_file, 'r') as f:
                all_metrics = json.load(f)
        else:
            all_metrics = []
            
        all_metrics.append(performance_data)
        
        with open(perf_file, 'w') as f:
            json.dump(all_metrics, f, indent=2)
            
    def log_api_request(self, endpoint: str, method: str, 
                       request_data: Dict[str, Any] = None,
                       response_data: Dict[str, Any] = None,
                       duration: float = None,
                       status_code: int = None):
        """Log API request details."""
        api_data = {
            "endpoint": endpoint,
            "method": method,
            "timestamp": datetime.now().isoformat(),
            "request_data": request_data,
            "response_data": response_data,
            "duration_seconds": duration,
            "status_code": status_code
        }
        
        self.info(f"API Request: {method} {endpoint}", api_data)
        
    def log_content_processing(self, content_id: str, operation: str,
                             input_size: int = None, output_size: int = None,
                             processing_time: float = None):
        """Log content processing operations."""
        content_data = {
            "content_id": content_id,
            "operation": operation,
            "input_size": input_size,
            "output_size": output_size,
            "processing_time_seconds": processing_time,
            "timestamp": datetime.now().isoformat()
        }
        
        self.info(f"Content processing: {operation} for {content_id}", content_data)
        
    def log_quiz_generation(self, quiz_id: str, question_count: int,
                          content_sources: list = None,
                          generation_time: float = None,
                          quality_metrics: Dict[str, Any] = None):
        """Log quiz generation operations."""
        quiz_data = {
            "quiz_id": quiz_id,
            "question_count": question_count,
            "content_sources": content_sources or [],
            "generation_time_seconds": generation_time,
            "quality_metrics": quality_metrics or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.info(f"Quiz generation: {question_count} questions for {quiz_id}", quiz_data)
        
    def create_session_summary(self) -> Path:
        """Create summary of current logging session."""
        timestamp = datetime.now()
        
        # Count log entries by level
        summary = {
            "session_start": timestamp.isoformat(),
            "logger_name": self.name,
            "log_files_created": [
                str(handler.baseFilename) for handler in self.logger.handlers 
                if isinstance(handler, logging.FileHandler)
            ]
        }
        
        filename = self.file_manager.generate_filename("logging_session_summary", "json")
        return self.file_manager.write_json_output(summary, filename, "logs")


# Global logger instance
_quiz_logger = None

def get_quiz_logger(name: str = "quiz_api") -> QuizLogger:
    """Get or create global quiz logger instance."""
    global _quiz_logger
    if _quiz_logger is None:
        _quiz_logger = QuizLogger(name)
    return _quiz_logger


def setup_enhanced_logging():
    """Setup enhanced logging for the entire application."""
    logger = get_quiz_logger()
    logger.info("Enhanced logging system initialized")
    return logger
