#!/usr/bin/env python3
"""
Sprint 8: Load and Stress Testing
Comprehensive performance testing for production readiness validation.
"""

import asyncio
import aiohttp
import time
import json
import statistics
import psutil
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import logging
import concurrent.futures
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    name: str
    endpoint: str
    method: str = "GET"
    concurrent_users: int = 10
    requests_per_user: int = 10
    ramp_up_time: int = 5  # seconds
    duration: int = 60  # seconds
    payload: Optional[Dict] = None
    headers: Optional[Dict] = None
    expected_status: int = 200

@dataclass
class PerformanceMetrics:
    """Performance metrics collection"""
    start_time: datetime
    end_time: datetime
    total_requests: int
    successful_requests: int
    failed_requests: int
    response_times: List[float]
    error_rates: Dict[str, int]
    throughput: float  # requests per second
    cpu_usage: List[float]
    memory_usage: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            'average_response_time': statistics.mean(self.response_times) if self.response_times else 0,
            'median_response_time': statistics.median(self.response_times) if self.response_times else 0,
            'p95_response_time': self._percentile(self.response_times, 95) if self.response_times else 0,
            'p99_response_time': self._percentile(self.response_times, 99) if self.response_times else 0,
            'min_response_time': min(self.response_times) if self.response_times else 0,
            'max_response_time': max(self.response_times) if self.response_times else 0,
            'success_rate': (self.successful_requests / self.total_requests * 100) if self.total_requests > 0 else 0
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile"""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]

class SystemMonitor:
    """System resource monitoring"""
    
    def __init__(self):
        self.cpu_usage = []
        self.memory_usage = []
        self.monitoring = False
    
    async def start_monitoring(self):
        """Start system monitoring"""
        self.monitoring = True
        self.cpu_usage = []
        self.memory_usage = []
        
        while self.monitoring:
            cpu = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory().percent
            
            self.cpu_usage.append(cpu)
            self.memory_usage.append(memory)
            
            await asyncio.sleep(1)
    
    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring = False
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get collected metrics"""
        return {
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "avg_cpu": statistics.mean(self.cpu_usage) if self.cpu_usage else 0,
            "max_cpu": max(self.cpu_usage) if self.cpu_usage else 0,
            "avg_memory": statistics.mean(self.memory_usage) if self.memory_usage else 0,
            "max_memory": max(self.memory_usage) if self.memory_usage else 0
        }

class LoadTester:
    """Advanced load testing framework"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.monitor = SystemMonitor()
        self.test_results = {}
    
    async def run_load_test(self, config: LoadTestConfig) -> PerformanceMetrics:
        """Run load test with specified configuration"""
        logger.info(f"Starting load test: {config.name}")
        logger.info(f"Config: {config.concurrent_users} users, {config.requests_per_user} requests each")
        
        # Start system monitoring
        monitor_task = asyncio.create_task(self.monitor.start_monitoring())
        
        start_time = datetime.now()
        response_times = []
        error_rates = {}
        successful_requests = 0
        failed_requests = 0
        
        try:
            # Create semaphore to control concurrency
            semaphore = asyncio.Semaphore(config.concurrent_users)
            
            # Create user tasks with ramp-up
            tasks = []
            for user_id in range(config.concurrent_users):
                # Stagger user start times
                delay = (config.ramp_up_time / config.concurrent_users) * user_id
                task = asyncio.create_task(
                    self._simulate_user(config, user_id, semaphore, delay)
                )
                tasks.append(task)
            
            # Wait for all users to complete
            user_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggregate results
            for result in user_results:
                if isinstance(result, dict):
                    response_times.extend(result.get('response_times', []))
                    successful_requests += result.get('successful_requests', 0)
                    failed_requests += result.get('failed_requests', 0)
                    
                    # Aggregate error rates
                    for error, count in result.get('error_rates', {}).items():
                        error_rates[error] = error_rates.get(error, 0) + count
                elif isinstance(result, Exception):
                    failed_requests += 1
                    error_rates[str(type(result).__name__)] = error_rates.get(str(type(result).__name__), 0) + 1
            
        finally:
            # Stop monitoring
            self.monitor.stop_monitoring()
            monitor_task.cancel()
            try:
                await monitor_task
            except asyncio.CancelledError:
                pass
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        total_requests = successful_requests + failed_requests
        
        metrics = PerformanceMetrics(
            start_time=start_time,
            end_time=end_time,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            response_times=response_times,
            error_rates=error_rates,
            throughput=total_requests / duration if duration > 0 else 0,
            cpu_usage=self.monitor.cpu_usage,
            memory_usage=self.monitor.memory_usage
        )
        
        logger.info(f"Load test completed: {config.name}")
        logger.info(f"Results: {successful_requests}/{total_requests} successful, {metrics.throughput:.2f} req/s")
        
        return metrics
    
    async def _simulate_user(self, config: LoadTestConfig, user_id: int, 
                           semaphore: asyncio.Semaphore, delay: float) -> Dict[str, Any]:
        """Simulate individual user behavior"""
        await asyncio.sleep(delay)
        
        response_times = []
        successful_requests = 0
        failed_requests = 0
        error_rates = {}
        
        async with semaphore:
            connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                for request_id in range(config.requests_per_user):
                    try:
                        start_time = time.time()
                        
                        url = f"{self.base_url}{config.endpoint}"
                        headers = config.headers or {}
                        
                        if config.method.upper() == "GET":
                            async with session.get(url, headers=headers) as response:
                                await response.text()
                                status = response.status
                        elif config.method.upper() == "POST":
                            async with session.post(url, json=config.payload, headers=headers) as response:
                                await response.text()
                                status = response.status
                        else:
                            raise ValueError(f"Unsupported method: {config.method}")
                        
                        response_time = time.time() - start_time
                        response_times.append(response_time)
                        
                        if status == config.expected_status:
                            successful_requests += 1
                        else:
                            failed_requests += 1
                            error_key = f"HTTP_{status}"
                            error_rates[error_key] = error_rates.get(error_key, 0) + 1
                    
                    except Exception as e:
                        failed_requests += 1
                        error_key = str(type(e).__name__)
                        error_rates[error_key] = error_rates.get(error_key, 0) + 1
                        
                        # Add timeout for failed requests
                        response_times.append(30.0)  # Timeout duration
        
        return {
            'user_id': user_id,
            'response_times': response_times,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'error_rates': error_rates
        }
    
    async def run_stress_test(self, endpoint: str, max_users: int = 100, 
                            step_size: int = 10, step_duration: int = 30) -> Dict[str, Any]:
        """Run stress test to find breaking point"""
        logger.info(f"Starting stress test for {endpoint}")
        logger.info(f"Ramping up to {max_users} users in steps of {step_size}")
        
        stress_results = {
            "endpoint": endpoint,
            "start_time": datetime.now(),
            "steps": [],
            "breaking_point": None,
            "peak_performance": None
        }
        
        peak_throughput = 0
        peak_users = 0
        
        for num_users in range(step_size, max_users + 1, step_size):
            logger.info(f"Testing with {num_users} concurrent users...")
            
            config = LoadTestConfig(
                name=f"Stress Test - {num_users} users",
                endpoint=endpoint,
                concurrent_users=num_users,
                requests_per_user=5,  # Fewer requests per user for stress test
                duration=step_duration
            )
            
            try:
                metrics = await self.run_load_test(config)
                
                step_result = {
                    "num_users": num_users,
                    "metrics": metrics.to_dict(),
                    "success_rate": metrics.to_dict()["success_rate"],
                    "throughput": metrics.throughput,
                    "avg_response_time": statistics.mean(metrics.response_times) if metrics.response_times else 0
                }
                
                stress_results["steps"].append(step_result)
                
                # Track peak performance
                if metrics.throughput > peak_throughput:
                    peak_throughput = metrics.throughput
                    peak_users = num_users
                    stress_results["peak_performance"] = step_result
                
                # Check for breaking point (success rate < 95% or avg response time > 5s)
                if (step_result["success_rate"] < 95 or 
                    step_result["avg_response_time"] > 5.0):
                    stress_results["breaking_point"] = step_result
                    logger.warning(f"Breaking point reached at {num_users} users")
                    break
                
                # Small delay between steps
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"Stress test failed at {num_users} users: {e}")
                stress_results["breaking_point"] = {
                    "num_users": num_users,
                    "error": str(e)
                }
                break
        
        stress_results["end_time"] = datetime.now()
        logger.info(f"Stress test completed. Peak: {peak_users} users at {peak_throughput:.2f} req/s")
        
        return stress_results
    
    async def run_endurance_test(self, endpoint: str, duration_minutes: int = 30, 
                               concurrent_users: int = 20) -> Dict[str, Any]:
        """Run endurance test for sustained load"""
        logger.info(f"Starting endurance test for {duration_minutes} minutes with {concurrent_users} users")
        
        config = LoadTestConfig(
            name=f"Endurance Test - {duration_minutes}m",
            endpoint=endpoint,
            concurrent_users=concurrent_users,
            requests_per_user=duration_minutes * 2,  # 2 requests per minute per user
            duration=duration_minutes * 60
        )
        
        start_time = datetime.now()
        
        # Run continuous load for specified duration
        metrics = await self.run_load_test(config)
        
        # Analyze for performance degradation
        response_times = metrics.response_times
        if len(response_times) >= 20:  # Need sufficient data
            first_quarter = response_times[:len(response_times)//4]
            last_quarter = response_times[-len(response_times)//4:]
            
            avg_first = statistics.mean(first_quarter)
            avg_last = statistics.mean(last_quarter)
            degradation = ((avg_last - avg_first) / avg_first * 100) if avg_first > 0 else 0
        else:
            degradation = 0
        
        endurance_results = {
            "endpoint": endpoint,
            "duration_minutes": duration_minutes,
            "concurrent_users": concurrent_users,
            "metrics": metrics.to_dict(),
            "performance_degradation_percent": degradation,
            "memory_leak_detected": self._check_memory_leak(),
            "stability_score": self._calculate_stability_score(metrics)
        }
        
        logger.info(f"Endurance test completed. Degradation: {degradation:.2f}%")
        return endurance_results
    
    def _check_memory_leak(self) -> bool:
        """Check for potential memory leaks"""
        memory_usage = self.monitor.memory_usage
        if len(memory_usage) < 10:
            return False
        
        # Simple trend analysis
        first_half = memory_usage[:len(memory_usage)//2]
        second_half = memory_usage[len(memory_usage)//2:]
        
        avg_first = statistics.mean(first_half)
        avg_second = statistics.mean(second_half)
        
        # If memory usage increased by more than 20%, flag as potential leak
        return (avg_second - avg_first) / avg_first > 0.2 if avg_first > 0 else False
    
    def _calculate_stability_score(self, metrics: PerformanceMetrics) -> float:
        """Calculate stability score based on various factors"""
        factors = []
        
        # Success rate factor (0-40 points)
        success_rate = (metrics.successful_requests / metrics.total_requests * 100) if metrics.total_requests > 0 else 0
        factors.append(min(success_rate * 0.4, 40))
        
        # Response time consistency factor (0-30 points)
        if metrics.response_times:
            avg_rt = statistics.mean(metrics.response_times)
            std_rt = statistics.stdev(metrics.response_times) if len(metrics.response_times) > 1 else 0
            consistency = max(0, 30 - (std_rt / avg_rt * 30)) if avg_rt > 0 else 0
            factors.append(consistency)
        else:
            factors.append(0)
        
        # Resource usage factor (0-30 points)
        if self.monitor.cpu_usage and self.monitor.memory_usage:
            max_cpu = max(self.monitor.cpu_usage)
            max_memory = max(self.monitor.memory_usage)
            resource_score = max(0, 30 - (max_cpu + max_memory) / 200 * 30)
            factors.append(resource_score)
        else:
            factors.append(20)  # Default moderate score
        
        return sum(factors)

class PerformanceTestSuite:
    """Comprehensive performance testing suite"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.tester = LoadTester(base_url)
        self.results = {}
    
    async def run_comprehensive_performance_tests(self) -> Dict[str, Any]:
        """Run complete performance test suite"""
        logger.info("=" * 60)
        logger.info("STARTING COMPREHENSIVE PERFORMANCE TESTS")
        logger.info("=" * 60)
        
        test_suite_start = datetime.now()
        
        # Define test scenarios
        test_scenarios = [
            {
                "name": "Health Check Load Test",
                "type": "load",
                "config": LoadTestConfig(
                    name="Health Check Load",
                    endpoint="/health",
                    concurrent_users=50,
                    requests_per_user=20
                )
            },
            {
                "name": "Quiz Generation Load Test",
                "type": "load",
                "config": LoadTestConfig(
                    name="Quiz Generation Load",
                    endpoint="/quiz/generate",
                    method="POST",
                    concurrent_users=10,
                    requests_per_user=5,
                    payload={
                        "content": "Test content for quiz generation",
                        "num_questions": 3,
                        "difficulty": "medium"
                    },
                    headers={"Content-Type": "application/json"}
                )
            },
            {
                "name": "API Stress Test",
                "type": "stress",
                "endpoint": "/health"
            },
            {
                "name": "Endurance Test",
                "type": "endurance",
                "endpoint": "/health",
                "duration": 10  # 10 minutes for testing
            }
        ]
        
        # Execute test scenarios
        for scenario in test_scenarios:
            logger.info(f"\nRunning: {scenario['name']}")
            
            try:
                if scenario["type"] == "load":
                    result = await self.tester.run_load_test(scenario["config"])
                    self.results[scenario["name"]] = {
                        "type": "load_test",
                        "metrics": result.to_dict(),
                        "status": "completed"
                    }
                
                elif scenario["type"] == "stress":
                    result = await self.tester.run_stress_test(
                        scenario["endpoint"], 
                        max_users=30,  # Reduced for testing
                        step_size=5,
                        step_duration=20
                    )
                    self.results[scenario["name"]] = {
                        "type": "stress_test",
                        "result": result,
                        "status": "completed"
                    }
                
                elif scenario["type"] == "endurance":
                    result = await self.tester.run_endurance_test(
                        scenario["endpoint"],
                        duration_minutes=scenario["duration"],
                        concurrent_users=10
                    )
                    self.results[scenario["name"]] = {
                        "type": "endurance_test",
                        "result": result,
                        "status": "completed"
                    }
                
                logger.info(f"✓ {scenario['name']} completed successfully")
                
            except Exception as e:
                logger.error(f"✗ {scenario['name']} failed: {e}")
                self.results[scenario["name"]] = {
                    "type": scenario["type"],
                    "status": "failed",
                    "error": str(e)
                }
        
        # Generate comprehensive report
        test_suite_end = datetime.now()
        
        report = {
            "test_suite": "Comprehensive Performance Tests",
            "start_time": test_suite_start,
            "end_time": test_suite_end,
            "total_duration": (test_suite_end - test_suite_start).total_seconds(),
            "results": self.results,
            "summary": self._generate_performance_summary(),
            "recommendations": self._generate_performance_recommendations()
        }
        
        # Save report
        report_path = "/Users/amankumarshrestha/Downloads/Quiz-D/performance_test_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info("=" * 60)
        logger.info("PERFORMANCE TESTING COMPLETED")
        logger.info(f"Report saved to: {report_path}")
        logger.info("=" * 60)
        
        return report
    
    def _generate_performance_summary(self) -> Dict[str, Any]:
        """Generate performance summary"""
        completed_tests = [name for name, result in self.results.items() if result["status"] == "completed"]
        failed_tests = [name for name, result in self.results.items() if result["status"] == "failed"]
        
        return {
            "total_tests": len(self.results),
            "completed_tests": len(completed_tests),
            "failed_tests": len(failed_tests),
            "success_rate": len(completed_tests) / len(self.results) * 100 if self.results else 0,
            "completed_test_names": completed_tests,
            "failed_test_names": failed_tests
        }
    
    def _generate_performance_recommendations(self) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        for name, result in self.results.items():
            if result["status"] == "failed":
                recommendations.append(f"Investigate failure in {name}")
            elif result["type"] == "load_test":
                metrics = result.get("metrics", {})
                if metrics.get("success_rate", 100) < 95:
                    recommendations.append(f"Improve reliability for {name} (success rate: {metrics.get('success_rate', 0):.1f}%)")
                if metrics.get("average_response_time", 0) > 2.0:
                    recommendations.append(f"Optimize response time for {name} (avg: {metrics.get('average_response_time', 0):.2f}s)")
        
        if not recommendations:
            recommendations.append("All performance tests passed - system is performing well under load")
        
        return recommendations

# Main execution
async def main():
    """Main execution function"""
    suite = PerformanceTestSuite()
    
    try:
        report = await suite.run_comprehensive_performance_tests()
        
        # Print summary
        summary = report["summary"]
        print(f"\nPerformance Test Summary:")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Completed: {summary['completed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Success Rate: {summary['success_rate']:.1f}%")
        
        return report
        
    except Exception as e:
        logger.error(f"Performance test suite failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
