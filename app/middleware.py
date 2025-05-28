"""
Timeout and response handling middleware for Quiz Generation API.

This module provides timeout handling, request size limits, and 
async response management for production use.
"""

import asyncio
import time
from typing import Callable, Any
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class TimeoutMiddleware:
    """Middleware to handle request timeouts."""
    
    def __init__(self, app, timeout_seconds: int = 30):
        self.app = app
        self.timeout_seconds = timeout_seconds
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Create timeout task
        timeout_task = asyncio.create_task(
            asyncio.sleep(self.timeout_seconds)
        )
        
        # Create app task
        app_task = asyncio.create_task(
            self.app(scope, receive, send)
        )
        
        try:
            # Wait for either timeout or app completion
            done, pending = await asyncio.wait(
                [timeout_task, app_task],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            # Check if timeout occurred
            if timeout_task in done:
                logger.warning(f"Request timeout after {self.timeout_seconds} seconds")
                # Send timeout response
                response = Response(
                    content='{"detail": "Request timeout"}',
                    status_code=408,
                    media_type="application/json"
                )
                await response(scope, receive, send)
            else:
                # App completed successfully
                pass
                
        except Exception as e:
            logger.error(f"Error in timeout middleware: {str(e)}")
            # Send error response
            response = Response(
                content='{"detail": "Internal server error"}',
                status_code=500,
                media_type="application/json"
            )
            await response(scope, receive, send)


class RequestSizeMiddleware:
    """Middleware to limit request body size."""
    
    def __init__(self, app, max_size: int = 10 * 1024 * 1024):  # 10MB default
        self.app = app
        self.max_size = max_size
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Check content length header
        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        
        if content_length:
            try:
                size = int(content_length.decode())
                if size > self.max_size:
                    response = JSONResponse(
                        content={"detail": f"Request too large. Max size: {self.max_size} bytes"},
                        status_code=413
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass
        
        # Track actual received size
        received_size = 0
        
        async def receive_wrapper():
            nonlocal received_size
            message = await receive()
            
            if message["type"] == "http.request":
                body = message.get("body", b"")
                received_size += len(body)
                
                if received_size > self.max_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request too large. Max size: {self.max_size} bytes"
                    )
            
            return message
        
        await self.app(scope, receive_wrapper, send)


class ResponseTimeMiddleware:
    """Middleware to track response times."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                process_time = time.time() - start_time
                # Add response time header
                headers = dict(message.get("headers", []))
                headers[b"x-process-time"] = str(process_time).encode()
                message["headers"] = list(headers.items())
                
                # Log slow requests
                if process_time > 5.0:  # Log requests taking more than 5 seconds
                    path = scope.get("path", "unknown")
                    method = scope.get("method", "unknown")
                    logger.warning(f"Slow request: {method} {path} took {process_time:.2f}s")
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)


def add_timeout_middleware(app, timeout_seconds: int = 30):
    """Add timeout middleware to FastAPI app."""
    app.add_middleware(TimeoutMiddleware, timeout_seconds=timeout_seconds)


def add_request_size_middleware(app, max_size: int = 10 * 1024 * 1024):
    """Add request size limit middleware to FastAPI app."""
    app.add_middleware(RequestSizeMiddleware, max_size=max_size)


def add_response_time_middleware(app):
    """Add response time tracking middleware to FastAPI app."""
    app.add_middleware(ResponseTimeMiddleware)


# Context manager for operation timeouts
class OperationTimeout:
    """Context manager for timing out long-running operations."""
    
    def __init__(self, timeout_seconds: int, operation_name: str = "operation"):
        self.timeout_seconds = timeout_seconds
        self.operation_name = operation_name
        self.task = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info(f"Operation '{self.operation_name}' was cancelled due to timeout")
    
    async def run(self, coro):
        """Run a coroutine with timeout."""
        try:
            self.task = asyncio.create_task(coro)
            return await asyncio.wait_for(self.task, timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            logger.warning(f"Operation '{self.operation_name}' timed out after {self.timeout_seconds} seconds")
            raise HTTPException(
                status_code=408,
                detail=f"Operation timed out after {self.timeout_seconds} seconds"
            )


# Async utilities for quiz generation
async def with_quiz_timeout(coro, timeout_seconds: int = 300):
    """Run quiz generation with timeout."""
    async with OperationTimeout(timeout_seconds, "quiz_generation") as timeout_mgr:
        return await timeout_mgr.run(coro)


async def with_question_timeout(coro, timeout_seconds: int = 120):
    """Run question generation with timeout."""
    async with OperationTimeout(timeout_seconds, "question_generation") as timeout_mgr:
        return await timeout_mgr.run(coro)


# Streaming response utilities
async def stream_quiz_generation(generator_func, **kwargs):
    """Stream quiz generation results as they become available."""
    async def generate():
        try:
            async for chunk in generator_func(**kwargs):
                yield f"data: {chunk}\n\n"
        except Exception as e:
            yield f"data: {{'error': '{str(e)}'}}\n\n"
        finally:
            yield "data: [DONE]\n\n"
    
    return generate()


class CancellableTask:
    """Wrapper for cancellable async tasks."""
    
    def __init__(self, coro, task_id: str = None):
        self.coro = coro
        self.task_id = task_id or str(id(coro))
        self.task = None
        self.cancelled = False
    
    async def start(self):
        """Start the task."""
        if self.task is None:
            self.task = asyncio.create_task(self.coro)
        return self.task
    
    async def cancel(self):
        """Cancel the task."""
        if self.task and not self.task.done():
            self.cancelled = True
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info(f"Task {self.task_id} was successfully cancelled")
    
    async def result(self):
        """Get the task result."""
        if self.task is None:
            await self.start()
        return await self.task
    
    def is_done(self):
        """Check if task is done."""
        return self.task and self.task.done()
    
    def is_cancelled(self):
        """Check if task was cancelled."""
        return self.cancelled or (self.task and self.task.cancelled())


# Task management for long-running operations
class TaskManager:
    """Manage long-running tasks with cancellation support."""
    
    def __init__(self):
        self.tasks = {}
    
    def create_task(self, coro, task_id: str = None) -> str:
        """Create and register a new task."""
        task = CancellableTask(coro, task_id)
        task_id = task.task_id
        self.tasks[task_id] = task
        return task_id
    
    async def start_task(self, task_id: str):
        """Start a registered task."""
        if task_id in self.tasks:
            return await self.tasks[task_id].start()
        raise ValueError(f"Task {task_id} not found")
    
    async def cancel_task(self, task_id: str):
        """Cancel a running task."""
        if task_id in self.tasks:
            await self.tasks[task_id].cancel()
            del self.tasks[task_id]
        else:
            raise ValueError(f"Task {task_id} not found")
    
    async def get_task_result(self, task_id: str):
        """Get task result."""
        if task_id in self.tasks:
            result = await self.tasks[task_id].result()
            if self.tasks[task_id].is_done():
                del self.tasks[task_id]
            return result
        raise ValueError(f"Task {task_id} not found")
    
    def get_task_status(self, task_id: str) -> dict:
        """Get task status."""
        if task_id not in self.tasks:
            return {"status": "not_found"}
        
        task = self.tasks[task_id]
        if task.is_cancelled():
            return {"status": "cancelled"}
        elif task.is_done():
            return {"status": "completed"}
        else:
            return {"status": "running"}
    
    def list_tasks(self) -> dict:
        """List all active tasks."""
        return {
            task_id: self.get_task_status(task_id)
            for task_id in self.tasks.keys()
        }
    
    async def cleanup_completed_tasks(self):
        """Remove completed tasks from memory."""
        completed_tasks = [
            task_id for task_id, task in self.tasks.items()
            if task.is_done() or task.is_cancelled()
        ]
        for task_id in completed_tasks:
            del self.tasks[task_id]


# Global task manager instance
task_manager = TaskManager()
