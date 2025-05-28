"""
Monitoring and logging module for Quiz Generation API.

This module provides structured logging, metrics collection, health checks,
and monitoring hooks for production deployments.
"""

import logging
import json
import time
import psutil
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from fastapi import FastAPI, Request, Response
import asyncio

# Configure structured logging
class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add extra fields
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'duration'):
            log_data['duration'] = record.duration
        if hasattr(record, 'endpoint'):
            log_data['endpoint'] = record.endpoint
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)


def setup_logging(log_level: str = "INFO", log_format: str = "json"):
    """Setup structured logging for the application."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    
    if log_format.lower() == "json":
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Set specific logger levels
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


@dataclass
class RequestMetrics:
    """Metrics for individual requests."""
    endpoint: str
    method: str
    status_code: int
    duration: float
    timestamp: datetime
    content_length: int = 0
    user_agent: str = ""
    client_ip: str = ""


@dataclass
class SystemMetrics:
    """System performance metrics."""
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    memory_available_mb: float
    disk_usage_percent: float
    active_connections: int
    timestamp: datetime


class MetricsCollector:
    """Collect and store application metrics."""
    
    def __init__(self, max_request_history: int = 10000):
        self.request_metrics: deque = deque(maxlen=max_request_history)
        self.system_metrics: deque = deque(maxlen=1440)  # 24 hours at 1 minute intervals
        self.counters = defaultdict(int)
        self.gauges = defaultdict(float)
        self.histograms = defaultdict(list)
        self.start_time = datetime.utcnow()
        
        # Performance tracking
        self.endpoint_stats = defaultdict(lambda: {
            'count': 0,
            'total_duration': 0,
            'min_duration': float('inf'),
            'max_duration': 0,
            'error_count': 0,
            'last_24h_count': 0
        })
    
    def record_request(self, metrics: RequestMetrics):
        """Record request metrics."""
        self.request_metrics.append(metrics)
        
        # Update counters
        self.counters[f"requests_total"] += 1
        self.counters[f"requests_{metrics.method.lower()}"] += 1
        self.counters[f"responses_{metrics.status_code}"] += 1
        
        # Update endpoint statistics
        endpoint_key = f"{metrics.method}:{metrics.endpoint}"
        stats = self.endpoint_stats[endpoint_key]
        stats['count'] += 1
        stats['total_duration'] += metrics.duration
        stats['min_duration'] = min(stats['min_duration'], metrics.duration)
        stats['max_duration'] = max(stats['max_duration'], metrics.duration)
        
        if metrics.status_code >= 400:
            stats['error_count'] += 1
            self.counters['requests_errors'] += 1
        
        # Track histogram for response times
        self.histograms['response_time'].append(metrics.duration)
        
        # Keep only last 1000 response times for histogram
        if len(self.histograms['response_time']) > 1000:
            self.histograms['response_time'] = self.histograms['response_time'][-1000:]
    
    def record_system_metrics(self):
        """Record current system metrics."""
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            metrics = SystemMetrics(
                cpu_percent=psutil.cpu_percent(interval=None),
                memory_percent=memory.percent,
                memory_used_mb=memory.used / 1024 / 1024,
                memory_available_mb=memory.available / 1024 / 1024,
                disk_usage_percent=disk.percent,
                active_connections=len(psutil.net_connections()),
                timestamp=datetime.utcnow()
            )
            
            self.system_metrics.append(metrics)
            
            # Update gauges
            self.gauges['cpu_percent'] = metrics.cpu_percent
            self.gauges['memory_percent'] = metrics.memory_percent
            self.gauges['disk_usage_percent'] = metrics.disk_usage_percent
            self.gauges['active_connections'] = metrics.active_connections
            
        except Exception as e:
            logging.error(f"Error collecting system metrics: {str(e)}")
    
    def get_endpoint_stats(self) -> Dict[str, Any]:
        """Get aggregated endpoint statistics."""
        stats = {}
        for endpoint, data in self.endpoint_stats.items():
            if data['count'] > 0:
                avg_duration = data['total_duration'] / data['count']
                error_rate = data['error_count'] / data['count'] * 100
                
                stats[endpoint] = {
                    'total_requests': data['count'],
                    'avg_response_time': round(avg_duration, 3),
                    'min_response_time': round(data['min_duration'], 3),
                    'max_response_time': round(data['max_duration'], 3),
                    'error_rate': round(error_rate, 2),
                    'total_errors': data['error_count']
                }
        
        return stats
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics."""
        uptime = datetime.utcnow() - self.start_time
        
        # Calculate recent request rate (last 5 minutes)
        five_minutes_ago = datetime.utcnow() - timedelta(minutes=5)
        recent_requests = [
            m for m in self.request_metrics 
            if m.timestamp > five_minutes_ago
        ]
        
        # Response time percentiles
        response_times = self.histograms.get('response_time', [])
        if response_times:
            sorted_times = sorted(response_times)
            p50 = sorted_times[int(0.5 * len(sorted_times))]
            p95 = sorted_times[int(0.95 * len(sorted_times))]
            p99 = sorted_times[int(0.99 * len(sorted_times))]
        else:
            p50 = p95 = p99 = 0
        
        return {
            'uptime_seconds': uptime.total_seconds(),
            'uptime_human': str(uptime),
            'total_requests': self.counters.get('requests_total', 0),
            'total_errors': self.counters.get('requests_errors', 0),
            'requests_per_minute': len(recent_requests) * 12,  # Extrapolate from 5 min to 1 hour
            'avg_response_time': round(sum(response_times) / len(response_times) if response_times else 0, 3),
            'response_time_p50': round(p50, 3),
            'response_time_p95': round(p95, 3),
            'response_time_p99': round(p99, 3),
            'memory_usage_mb': self.gauges.get('memory_used_mb', 0),
            'cpu_usage_percent': self.gauges.get('cpu_percent', 0)
        }
    
    def export_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        # Add help and type annotations
        lines.append("# HELP quiz_requests_total Total number of requests")
        lines.append("# TYPE quiz_requests_total counter")
        lines.append(f"quiz_requests_total {self.counters.get('requests_total', 0)}")
        
        lines.append("# HELP quiz_requests_errors_total Total number of error responses")
        lines.append("# TYPE quiz_requests_errors_total counter")
        lines.append(f"quiz_requests_errors_total {self.counters.get('requests_errors', 0)}")
        
        lines.append("# HELP quiz_memory_usage_bytes Memory usage in bytes")
        lines.append("# TYPE quiz_memory_usage_bytes gauge")
        lines.append(f"quiz_memory_usage_bytes {self.gauges.get('memory_used_mb', 0) * 1024 * 1024}")
        
        lines.append("# HELP quiz_cpu_usage_percent CPU usage percentage")
        lines.append("# TYPE quiz_cpu_usage_percent gauge")
        lines.append(f"quiz_cpu_usage_percent {self.gauges.get('cpu_percent', 0)}")
        
        # Endpoint-specific metrics
        for endpoint, stats in self.endpoint_stats.items():
            if stats['count'] > 0:
                safe_endpoint = endpoint.replace(':', '_').replace('/', '_')
                
                lines.append(f"# HELP quiz_endpoint_requests_total_{safe_endpoint} Total requests for endpoint")
                lines.append(f"# TYPE quiz_endpoint_requests_total_{safe_endpoint} counter")
                lines.append(f"quiz_endpoint_requests_total_{{{safe_endpoint}}} {stats['count']}")
                
                avg_duration = stats['total_duration'] / stats['count']
                lines.append(f"# HELP quiz_endpoint_duration_seconds_{safe_endpoint} Average response time")
                lines.append(f"# TYPE quiz_endpoint_duration_seconds_{safe_endpoint} gauge")
                lines.append(f"quiz_endpoint_duration_seconds_{{{safe_endpoint}}} {avg_duration}")
        
        return '\n'.join(lines)


# Global metrics collector
metrics_collector = MetricsCollector()


class MonitoringMiddleware:
    """Middleware for collecting request metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        start_time = time.time()
        request_id = str(time.time_ns())
        
        # Extract request information
        path = scope.get("path", "")
        method = scope.get("method", "")
        headers = dict(scope.get("headers", []))
        
        # Get client information
        client_ip = "unknown"
        if "client" in scope and scope["client"]:
            client_ip = scope["client"][0]
        
        user_agent = headers.get(b"user-agent", b"").decode()
        content_length = int(headers.get(b"content-length", b"0").decode() or "0")
        
        # Add request ID to logging context
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add request ID header
                if "headers" not in message:
                    message["headers"] = []
                message["headers"].append([b"x-request-id", request_id.encode()])
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as e:
            status_code = 500
            logging.error(f"Unhandled exception in request {request_id}: {str(e)}", 
                         extra={'request_id': request_id, 'endpoint': path})
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time
            
            metrics = RequestMetrics(
                endpoint=path,
                method=method,
                status_code=status_code,
                duration=duration,
                timestamp=datetime.utcnow(),
                content_length=content_length,
                user_agent=user_agent,
                client_ip=client_ip
            )
            
            metrics_collector.record_request(metrics)
            
            # Log request
            logging.info(
                f"{method} {path} {status_code} {duration:.3f}s",
                extra={
                    'request_id': request_id,
                    'endpoint': path,
                    'method': method,
                    'status_code': status_code,
                    'duration': duration,
                    'content_length': content_length,
                    'client_ip': client_ip
                }
            )


def add_monitoring_middleware(app: FastAPI):
    """Add monitoring middleware to FastAPI app."""
    app.add_middleware(MonitoringMiddleware)


async def start_system_monitoring():
    """Start background system monitoring."""
    async def monitor_loop():
        while True:
            try:
                metrics_collector.record_system_metrics()
                await asyncio.sleep(60)  # Record every minute
            except Exception as e:
                logging.error(f"Error in system monitoring: {str(e)}")
                await asyncio.sleep(60)
    
    # Start monitoring task
    asyncio.create_task(monitor_loop())


def get_health_status() -> Dict[str, Any]:
    """Get comprehensive health status."""
    try:
        # Basic health check
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Check if system resources are healthy
        healthy = True
        issues = []
        
        if memory.percent > 90:
            healthy = False
            issues.append("High memory usage")
        
        if disk.percent > 90:
            healthy = False
            issues.append("High disk usage")
        
        cpu_percent = psutil.cpu_percent(interval=1)
        if cpu_percent > 90:
            healthy = False
            issues.append("High CPU usage")
        
        # Check recent error rate
        recent_requests = list(metrics_collector.request_metrics)[-100:]  # Last 100 requests
        if recent_requests:
            error_count = sum(1 for r in recent_requests if r.status_code >= 500)
            error_rate = error_count / len(recent_requests)
            if error_rate > 0.1:  # More than 10% error rate
                healthy = False
                issues.append(f"High error rate: {error_rate:.1%}")
        
        return {
            "status": "healthy" if healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "issues": issues,
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "uptime_seconds": (datetime.utcnow() - metrics_collector.start_time).total_seconds()
            },
            "application": {
                "total_requests": metrics_collector.counters.get('requests_total', 0),
                "error_rate": metrics_collector.counters.get('requests_errors', 0) / max(metrics_collector.counters.get('requests_total', 1), 1),
                "avg_response_time": metrics_collector.gauges.get('avg_response_time', 0)
            }
        }
    
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# Monitoring hooks for quiz generation
class QuizGenerationMonitor:
    """Monitor quiz generation operations."""
    
    @staticmethod
    def log_quiz_generation_start(quiz_id: str, content_count: int, question_count: int):
        """Log start of quiz generation."""
        logging.info(
            f"Starting quiz generation: {quiz_id}",
            extra={
                'quiz_id': quiz_id,
                'content_count': content_count,
                'question_count': question_count,
                'operation': 'quiz_generation_start'
            }
        )
        metrics_collector.counters['quiz_generations_started'] += 1
    
    @staticmethod
    def log_quiz_generation_complete(quiz_id: str, duration: float, success: bool, error: str = None):
        """Log completion of quiz generation."""
        status = "success" if success else "error"
        
        logging.info(
            f"Quiz generation {status}: {quiz_id} in {duration:.2f}s",
            extra={
                'quiz_id': quiz_id,
                'duration': duration,
                'operation': 'quiz_generation_complete',
                'success': success,
                'error': error
            }
        )
        
        if success:
            metrics_collector.counters['quiz_generations_success'] += 1
        else:
            metrics_collector.counters['quiz_generations_error'] += 1
        
        metrics_collector.histograms['quiz_generation_duration'].append(duration)
    
    @staticmethod
    def log_question_generation(count: int, duration: float, success: bool):
        """Log question generation."""
        logging.info(
            f"Generated {count} questions in {duration:.2f}s",
            extra={
                'question_count': count,
                'duration': duration,
                'operation': 'question_generation',
                'success': success
            }
        )
        
        metrics_collector.counters['questions_generated'] += count
        metrics_collector.histograms['question_generation_duration'].append(duration)


# Export monitoring utilities
quiz_monitor = QuizGenerationMonitor()
