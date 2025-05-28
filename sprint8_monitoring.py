#!/usr/bin/env python3
"""
Sprint 8: Production Monitoring & Logging Infrastructure
Comprehensive monitoring and logging setup for production deployment.
"""

import json
import logging
import time
import psutil
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import aiofiles
import os
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class MetricPoint:
    """Individual metric data point"""
    timestamp: datetime
    metric_name: str
    value: float
    labels: Dict[str, str]
    unit: str = ""

@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric: str
    condition: str  # "gt", "lt", "eq"
    threshold: float
    duration: int  # seconds
    severity: str  # "critical", "warning", "info"
    description: str

class MetricsCollector:
    """System and application metrics collector"""
    
    def __init__(self, collection_interval: int = 30):
        self.collection_interval = collection_interval
        self.metrics_buffer = []
        self.collecting = False
        
    async def start_collection(self):
        """Start metrics collection"""
        self.collecting = True
        logger.info("Starting metrics collection...")
        
        while self.collecting:
            try:
                await self._collect_system_metrics()
                await self._collect_application_metrics()
                await asyncio.sleep(self.collection_interval)
            except Exception as e:
                logger.error(f"Error collecting metrics: {e}")
                await asyncio.sleep(5)
    
    def stop_collection(self):
        """Stop metrics collection"""
        self.collecting = False
        logger.info("Stopping metrics collection...")
    
    async def _collect_system_metrics(self):
        """Collect system-level metrics"""
        timestamp = datetime.now()
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="system_cpu_usage_percent",
            value=cpu_percent,
            labels={"host": "localhost"},
            unit="percent"
        ))
        
        # Memory metrics
        memory = psutil.virtual_memory()
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="system_memory_usage_percent",
            value=memory.percent,
            labels={"host": "localhost"},
            unit="percent"
        ))
        
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="system_memory_available_bytes",
            value=memory.available,
            labels={"host": "localhost"},
            unit="bytes"
        ))
        
        # Disk metrics
        disk = psutil.disk_usage('/')
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="system_disk_usage_percent",
            value=(disk.used / disk.total) * 100,
            labels={"host": "localhost", "mount": "/"},
            unit="percent"
        ))
        
        # Network metrics
        network = psutil.net_io_counters()
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="system_network_bytes_sent",
            value=network.bytes_sent,
            labels={"host": "localhost"},
            unit="bytes"
        ))
        
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="system_network_bytes_recv",
            value=network.bytes_recv,
            labels={"host": "localhost"},
            unit="bytes"
        ))
    
    async def _collect_application_metrics(self):
        """Collect application-specific metrics"""
        timestamp = datetime.now()
        
        # Simulate application metrics (these would come from the actual app)
        import random
        
        # HTTP request metrics
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="http_requests_total",
            value=random.randint(50, 200),
            labels={"method": "GET", "endpoint": "/health", "status": "200"},
            unit="requests"
        ))
        
        # Response time metrics
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="http_request_duration_seconds",
            value=random.uniform(0.1, 2.0),
            labels={"method": "POST", "endpoint": "/quiz/generate"},
            unit="seconds"
        ))
        
        # Quiz generation metrics
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="quiz_generation_requests",
            value=random.randint(10, 50),
            labels={"difficulty": "medium", "status": "success"},
            unit="requests"
        ))
        
        # Database connection pool metrics
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="database_connections_active",
            value=random.randint(5, 20),
            labels={"database": "quiz_db"},
            unit="connections"
        ))
        
        # Error rate metrics
        self.metrics_buffer.append(MetricPoint(
            timestamp=timestamp,
            metric_name="application_errors_total",
            value=random.randint(0, 5),
            labels={"error_type": "validation_error"},
            unit="errors"
        ))
    
    async def export_metrics(self, filepath: str):
        """Export collected metrics to file"""
        metrics_data = []
        for metric in self.metrics_buffer:
            metrics_data.append({
                "timestamp": metric.timestamp.isoformat(),
                "metric_name": metric.metric_name,
                "value": metric.value,
                "labels": metric.labels,
                "unit": metric.unit
            })
        
        async with aiofiles.open(filepath, 'w') as f:
            await f.write(json.dumps(metrics_data, indent=2))
        
        logger.info(f"Exported {len(metrics_data)} metrics to {filepath}")
    
    def get_recent_metrics(self, metric_name: str, minutes: int = 10) -> List[MetricPoint]:
        """Get recent metrics for a specific metric"""
        cutoff_time = datetime.now() - timedelta(minutes=minutes)
        return [
            m for m in self.metrics_buffer 
            if m.metric_name == metric_name and m.timestamp > cutoff_time
        ]

class AlertManager:
    """Alert management system"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules = []
        self.active_alerts = {}
        self.alert_history = []
    
    def add_alert_rule(self, rule: AlertRule):
        """Add an alert rule"""
        self.alert_rules.append(rule)
        logger.info(f"Added alert rule: {rule.name}")
    
    async def evaluate_alerts(self):
        """Evaluate all alert rules"""
        current_time = datetime.now()
        
        for rule in self.alert_rules:
            try:
                # Get recent metrics for this rule
                recent_metrics = self.metrics_collector.get_recent_metrics(
                    rule.metric, minutes=rule.duration // 60 or 1
                )
                
                if not recent_metrics:
                    continue
                
                # Calculate current value (average of recent metrics)
                current_value = sum(m.value for m in recent_metrics) / len(recent_metrics)
                
                # Evaluate condition
                alert_triggered = self._evaluate_condition(
                    current_value, rule.condition, rule.threshold
                )
                
                alert_key = f"{rule.name}_{rule.metric}"
                
                if alert_triggered and alert_key not in self.active_alerts:
                    # New alert
                    alert = {
                        "rule_name": rule.name,
                        "metric": rule.metric,
                        "current_value": current_value,
                        "threshold": rule.threshold,
                        "severity": rule.severity,
                        "description": rule.description,
                        "triggered_at": current_time,
                        "status": "active"
                    }
                    
                    self.active_alerts[alert_key] = alert
                    self.alert_history.append(alert.copy())
                    
                    logger.warning(f"ALERT TRIGGERED: {rule.name} - {rule.description}")
                    await self._send_alert_notification(alert)
                
                elif not alert_triggered and alert_key in self.active_alerts:
                    # Alert resolved
                    alert = self.active_alerts[alert_key]
                    alert["status"] = "resolved"
                    alert["resolved_at"] = current_time
                    
                    self.alert_history.append(alert.copy())
                    del self.active_alerts[alert_key]
                    
                    logger.info(f"ALERT RESOLVED: {rule.name}")
                    await self._send_alert_notification(alert)
            
            except Exception as e:
                logger.error(f"Error evaluating alert rule {rule.name}: {e}")
    
    def _evaluate_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Evaluate alert condition"""
        if condition == "gt":
            return value > threshold
        elif condition == "lt":
            return value < threshold
        elif condition == "eq":
            return abs(value - threshold) < 0.01  # Allow small floating point differences
        else:
            logger.warning(f"Unknown condition: {condition}")
            return False
    
    async def _send_alert_notification(self, alert: Dict[str, Any]):
        """Send alert notification (placeholder for actual notification system)"""
        # In a real system, this would send emails, Slack messages, etc.
        notification_message = f"""
ALERT NOTIFICATION
Status: {alert['status'].upper()}
Rule: {alert['rule_name']}
Metric: {alert['metric']}
Current Value: {alert['current_value']:.2f}
Threshold: {alert['threshold']}
Severity: {alert['severity'].upper()}
Description: {alert['description']}
Time: {alert.get('triggered_at', alert.get('resolved_at', datetime.now()))}
        """
        
        # Write to alert log file
        alert_log_path = "/Users/amankumarshrestha/Downloads/Quiz-D/logs/alerts.log"
        os.makedirs(os.path.dirname(alert_log_path), exist_ok=True)
        
        async with aiofiles.open(alert_log_path, 'a') as f:
            await f.write(f"{datetime.now().isoformat()}: {notification_message}\n")
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """Get alert summary"""
        return {
            "active_alerts": len(self.active_alerts),
            "total_rules": len(self.alert_rules),
            "alert_history_count": len(self.alert_history),
            "active_alert_details": list(self.active_alerts.values()),
            "recent_alerts": self.alert_history[-10:]  # Last 10 alerts
        }

class LoggingManager:
    """Advanced logging manager"""
    
    def __init__(self, log_dir: str = "/Users/amankumarshrestha/Downloads/Quiz-D/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.setup_logging()
    
    def setup_logging(self):
        """Setup comprehensive logging configuration"""
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # Application logs
        app_handler = logging.FileHandler(self.log_dir / "application.log")
        app_handler.setLevel(logging.INFO)
        app_handler.setFormatter(detailed_formatter)
        
        # Error logs
        error_handler = logging.FileHandler(self.log_dir / "errors.log")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        
        # Security logs
        security_handler = logging.FileHandler(self.log_dir / "security.log")
        security_handler.setLevel(logging.WARNING)
        security_handler.setFormatter(detailed_formatter)
        
        # Performance logs
        performance_handler = logging.FileHandler(self.log_dir / "performance.log")
        performance_handler.setLevel(logging.INFO)
        performance_handler.setFormatter(simple_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Add handlers
        root_logger.addHandler(app_handler)
        root_logger.addHandler(error_handler)
        
        # Configure specific loggers
        security_logger = logging.getLogger("security")
        security_logger.addHandler(security_handler)
        
        performance_logger = logging.getLogger("performance")
        performance_logger.addHandler(performance_handler)
        
        logger.info("Logging configuration initialized")
    
    async def analyze_logs(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze recent logs for insights"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        analysis = {
            "time_range": f"Last {hours} hours",
            "log_files_analyzed": [],
            "error_summary": {},
            "warning_summary": {},
            "performance_insights": {},
            "security_events": []
        }
        
        # Analyze each log file
        for log_file in self.log_dir.glob("*.log"):
            if log_file.is_file():
                analysis["log_files_analyzed"].append(str(log_file.name))
                await self._analyze_log_file(log_file, cutoff_time, analysis)
        
        return analysis
    
    async def _analyze_log_file(self, log_file: Path, cutoff_time: datetime, analysis: Dict):
        """Analyze individual log file"""
        try:
            async with aiofiles.open(log_file, 'r') as f:
                lines = await f.readlines()
            
            error_count = 0
            warning_count = 0
            
            for line in lines:
                try:
                    # Extract timestamp (assuming ISO format at start of line)
                    timestamp_str = line.split(' - ')[0]
                    log_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    
                    if log_time < cutoff_time:
                        continue
                    
                    # Count errors and warnings
                    if "ERROR" in line:
                        error_count += 1
                        # Extract error type
                        if ":" in line:
                            error_type = line.split(":")[-1].strip()[:50]
                            analysis["error_summary"][error_type] = analysis["error_summary"].get(error_type, 0) + 1
                    
                    if "WARNING" in line:
                        warning_count += 1
                    
                    # Security events
                    if "security" in log_file.name.lower() or any(keyword in line.lower() for keyword in ["auth", "login", "security", "breach"]):
                        analysis["security_events"].append({
                            "timestamp": timestamp_str,
                            "event": line.strip()[:100]
                        })
                
                except Exception as e:
                    # Skip malformed log lines
                    continue
            
            analysis[f"{log_file.stem}_errors"] = error_count
            analysis[f"{log_file.stem}_warnings"] = warning_count
        
        except Exception as e:
            logger.error(f"Error analyzing log file {log_file}: {e}")

class HealthChecker:
    """Application health monitoring"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.health_history = []
    
    async def perform_health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check"""
        health_status = {
            "timestamp": datetime.now(),
            "overall_status": "healthy",
            "checks": {},
            "response_times": {},
            "errors": []
        }
        
        # Check API endpoints
        await self._check_api_health(health_status)
        
        # Check system resources
        await self._check_system_health(health_status)
        
        # Check database connectivity (simulated)
        await self._check_database_health(health_status)
        
        # Determine overall status
        failed_checks = [name for name, status in health_status["checks"].items() if not status]
        if failed_checks:
            health_status["overall_status"] = "unhealthy" if len(failed_checks) > 2 else "degraded"
        
        # Store in history
        self.health_history.append(health_status)
        
        # Keep only last 100 checks
        if len(self.health_history) > 100:
            self.health_history = self.health_history[-100:]
        
        return health_status
    
    async def _check_api_health(self, health_status: Dict):
        """Check API endpoint health"""
        import aiohttp
        
        endpoints = ["/health", "/docs", "/openapi.json"]
        
        for endpoint in endpoints:
            try:
                start_time = time.time()
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{self.base_url}{endpoint}",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        response_time = time.time() - start_time
                        
                        health_status["checks"][f"api{endpoint}"] = response.status == 200
                        health_status["response_times"][f"api{endpoint}"] = response_time
                        
                        if response.status != 200:
                            health_status["errors"].append(f"API {endpoint} returned {response.status}")
            
            except Exception as e:
                health_status["checks"][f"api{endpoint}"] = False
                health_status["errors"].append(f"API {endpoint} error: {str(e)}")
    
    async def _check_system_health(self, health_status: Dict):
        """Check system resource health"""
        try:
            # CPU check
            cpu_percent = psutil.cpu_percent(interval=1)
            health_status["checks"]["system_cpu"] = cpu_percent < 80
            if cpu_percent >= 80:
                health_status["errors"].append(f"High CPU usage: {cpu_percent}%")
            
            # Memory check
            memory = psutil.virtual_memory()
            health_status["checks"]["system_memory"] = memory.percent < 85
            if memory.percent >= 85:
                health_status["errors"].append(f"High memory usage: {memory.percent}%")
            
            # Disk check
            disk = psutil.disk_usage('/')
            disk_percent = (disk.used / disk.total) * 100
            health_status["checks"]["system_disk"] = disk_percent < 90
            if disk_percent >= 90:
                health_status["errors"].append(f"High disk usage: {disk_percent}%")
        
        except Exception as e:
            health_status["errors"].append(f"System health check error: {str(e)}")
    
    async def _check_database_health(self, health_status: Dict):
        """Check database health (simulated)"""
        try:
            # Simulate database connection check
            import random
            await asyncio.sleep(0.1)  # Simulate connection time
            
            # Simulate occasional database issues
            db_healthy = random.random() > 0.05  # 95% uptime
            
            health_status["checks"]["database_connection"] = db_healthy
            if not db_healthy:
                health_status["errors"].append("Database connection failed")
        
        except Exception as e:
            health_status["checks"]["database_connection"] = False
            health_status["errors"].append(f"Database health check error: {str(e)}")
    
    def get_health_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get health summary for specified time period"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_checks = [
            check for check in self.health_history 
            if check["timestamp"] > cutoff_time
        ]
        
        if not recent_checks:
            return {"error": "No health data available"}
        
        total_checks = len(recent_checks)
        healthy_checks = len([c for c in recent_checks if c["overall_status"] == "healthy"])
        
        return {
            "time_period": f"Last {hours} hours",
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "uptime_percentage": (healthy_checks / total_checks * 100) if total_checks > 0 else 0,
            "current_status": recent_checks[-1]["overall_status"] if recent_checks else "unknown",
            "recent_errors": [
                error for check in recent_checks[-5:] 
                for error in check.get("errors", [])
            ]
        }

class MonitoringOrchestrator:
    """Main monitoring orchestrator"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics_collector = MetricsCollector(collection_interval=30)
        self.alert_manager = AlertManager(self.metrics_collector)
        self.logging_manager = LoggingManager()
        self.health_checker = HealthChecker(base_url)
        self.monitoring_active = False
        
        # Setup default alert rules
        self._setup_default_alerts()
    
    def _setup_default_alerts(self):
        """Setup default alert rules"""
        default_rules = [
            AlertRule(
                name="High CPU Usage",
                metric="system_cpu_usage_percent",
                condition="gt",
                threshold=80.0,
                duration=300,  # 5 minutes
                severity="warning",
                description="CPU usage is above 80%"
            ),
            AlertRule(
                name="Critical CPU Usage",
                metric="system_cpu_usage_percent",
                condition="gt",
                threshold=95.0,
                duration=60,  # 1 minute
                severity="critical",
                description="CPU usage is above 95%"
            ),
            AlertRule(
                name="High Memory Usage",
                metric="system_memory_usage_percent",
                condition="gt",
                threshold=85.0,
                duration=300,  # 5 minutes
                severity="warning",
                description="Memory usage is above 85%"
            ),
            AlertRule(
                name="High Error Rate",
                metric="application_errors_total",
                condition="gt",
                threshold=10.0,
                duration=300,  # 5 minutes
                severity="critical",
                description="Application error rate is too high"
            )
        ]
        
        for rule in default_rules:
            self.alert_manager.add_alert_rule(rule)
    
    async def start_monitoring(self):
        """Start comprehensive monitoring"""
        if self.monitoring_active:
            logger.warning("Monitoring is already active")
            return
        
        self.monitoring_active = True
        logger.info("Starting comprehensive monitoring system...")
        
        # Start all monitoring components
        tasks = [
            asyncio.create_task(self.metrics_collector.start_collection()),
            asyncio.create_task(self._run_alert_evaluation()),
            asyncio.create_task(self._run_health_checks()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Monitoring system error: {e}")
        finally:
            self.monitoring_active = False
    
    async def _run_alert_evaluation(self):
        """Run periodic alert evaluation"""
        while self.monitoring_active:
            try:
                await self.alert_manager.evaluate_alerts()
                await asyncio.sleep(60)  # Check alerts every minute
            except Exception as e:
                logger.error(f"Alert evaluation error: {e}")
                await asyncio.sleep(30)
    
    async def _run_health_checks(self):
        """Run periodic health checks"""
        while self.monitoring_active:
            try:
                health_status = await self.health_checker.perform_health_check()
                
                # Log health status
                if health_status["overall_status"] != "healthy":
                    logger.warning(f"Health check failed: {health_status['overall_status']}")
                    for error in health_status["errors"]:
                        logger.error(f"Health check error: {error}")
                
                await asyncio.sleep(300)  # Health check every 5 minutes
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(60)
    
    def stop_monitoring(self):
        """Stop monitoring system"""
        self.monitoring_active = False
        self.metrics_collector.stop_collection()
        logger.info("Monitoring system stopped")
    
    async def generate_monitoring_report(self) -> Dict[str, Any]:
        """Generate comprehensive monitoring report"""
        logger.info("Generating monitoring report...")
        
        # Get current status from all components
        alert_summary = self.alert_manager.get_alert_summary()
        health_summary = self.health_checker.get_health_summary()
        log_analysis = await self.logging_manager.analyze_logs()
        
        # Export current metrics
        metrics_file = "/Users/amankumarshrestha/Downloads/Quiz-D/current_metrics.json"
        await self.metrics_collector.export_metrics(metrics_file)
        
        report = {
            "report_generated_at": datetime.now().isoformat(),
            "monitoring_period": "Last 24 hours",
            "system_status": {
                "overall_health": health_summary.get("current_status", "unknown"),
                "uptime_percentage": health_summary.get("uptime_percentage", 0),
                "active_alerts": alert_summary["active_alerts"],
                "monitoring_active": self.monitoring_active
            },
            "metrics_summary": {
                "total_metrics_collected": len(self.metrics_collector.metrics_buffer),
                "collection_interval": self.metrics_collector.collection_interval,
                "metrics_exported_to": metrics_file
            },
            "alert_summary": alert_summary,
            "health_summary": health_summary,
            "log_analysis": log_analysis,
            "recommendations": self._generate_monitoring_recommendations(
                alert_summary, health_summary, log_analysis
            )
        }
        
        # Save report
        report_path = "/Users/amankumarshrestha/Downloads/Quiz-D/monitoring_report.json"
        async with aiofiles.open(report_path, 'w') as f:
            await f.write(json.dumps(report, indent=2, default=str))
        
        logger.info(f"Monitoring report saved to: {report_path}")
        return report
    
    def _generate_monitoring_recommendations(self, alerts: Dict, health: Dict, logs: Dict) -> List[str]:
        """Generate monitoring recommendations"""
        recommendations = []
        
        # Alert-based recommendations
        if alerts["active_alerts"] > 0:
            recommendations.append(f"Address {alerts['active_alerts']} active alerts immediately")
        
        # Health-based recommendations
        uptime = health.get("uptime_percentage", 100)
        if uptime < 99:
            recommendations.append(f"Investigate system reliability issues (uptime: {uptime:.2f}%)")
        
        # Log-based recommendations
        error_count = sum(v for k, v in logs.items() if k.endswith("_errors"))
        if error_count > 50:
            recommendations.append(f"High error count detected ({error_count}), review error logs")
        
        if not recommendations:
            recommendations.append("System is operating normally, continue monitoring")
        
        return recommendations

# Main execution
async def main():
    """Main monitoring execution"""
    logger.info("=" * 60)
    logger.info("STARTING PRODUCTION MONITORING SETUP")
    logger.info("=" * 60)
    
    orchestrator = MonitoringOrchestrator()
    
    try:
        # Run monitoring for a test period
        logger.info("Starting monitoring system for testing...")
        
        # Start monitoring in background
        monitoring_task = asyncio.create_task(orchestrator.start_monitoring())
        
        # Let it run for a short period for testing
        await asyncio.sleep(120)  # 2 minutes for testing
        
        # Stop monitoring
        orchestrator.stop_monitoring()
        
        # Wait for tasks to complete
        monitoring_task.cancel()
        try:
            await monitoring_task
        except asyncio.CancelledError:
            pass
        
        # Generate final report
        report = await orchestrator.generate_monitoring_report()
        
        logger.info("=" * 60)
        logger.info("MONITORING SETUP COMPLETED")
        logger.info(f"System Status: {report['system_status']['overall_health']}")
        logger.info(f"Metrics Collected: {report['metrics_summary']['total_metrics_collected']}")
        logger.info(f"Active Alerts: {report['system_status']['active_alerts']}")
        logger.info("=" * 60)
        
        return report
        
    except Exception as e:
        logger.error(f"Monitoring setup failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
