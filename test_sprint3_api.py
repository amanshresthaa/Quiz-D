#!/usr/bin/env python3
"""
Sprint 3 API Integration Test Suite
Tests the enhanced API endpoints with hybrid search capabilities.
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, List

# Test configuration
API_BASE_URL = "http://localhost:8000"
TEST_QUERIES = [
    "Python programming language",
    "machine learning algorithms", 
    "web development frameworks",
    "data visualization tools",
    "artificial intelligence"
]

class Sprint3APITester:
    """Comprehensive API tester for Sprint 3 hybrid search endpoints."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def test_endpoint(self, endpoint: str, method: str = "GET", params: Dict = None) -> Dict[str, Any]:
        """Test a single API endpoint."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                async with self.session.get(url, params=params) as response:
                    return {
                        "status": response.status,
                        "data": await response.json() if response.status == 200 else await response.text(),
                        "success": response.status == 200
                    }
            elif method.upper() == "POST":
                async with self.session.post(url, params=params) as response:
                    return {
                        "status": response.status,
                        "data": await response.json() if response.status == 200 else await response.text(),
                        "success": response.status == 200
                    }
        except Exception as e:
            return {
                "status": 0,
                "data": str(e),
                "success": False
            }
    
    async def test_health_check(self) -> Dict[str, Any]:
        """Test the health endpoint."""
        print("🔍 Testing Health Check...")
        result = await self.test_endpoint("/health")
        
        if result["success"]:
            print("   ✅ Health check passed")
            print(f"   📊 Status: {result['data'].get('status', 'Unknown')}")
        else:
            print(f"   ❌ Health check failed: {result['status']}")
        
        return result
    
    async def test_search_modes(self) -> Dict[str, Any]:
        """Test all search modes."""
        print("\n🔍 Testing Search Modes...")
        results = {}
        
        for mode in ["SEMANTIC_ONLY", "LEXICAL_ONLY", "HYBRID", "AUTO"]:
            print(f"   Testing {mode} mode...")
            result = await self.test_endpoint(
                "/content/search",
                method="POST",
                params={
                    "query": "Python programming language",
                    "max_results": 3,
                    "search_mode": mode
                }
            )
            
            if result["success"]:
                count = len(result["data"])
                print(f"   ✅ {mode}: {count} results")
                if count > 0:
                    top_score = result["data"][0].get("similarity_score", 0)
                    print(f"      Top score: {top_score:.4f}")
            else:
                print(f"   ❌ {mode}: Failed ({result['status']})")
            
            results[mode] = result
        
        return results
    
    async def test_search_comparison(self) -> Dict[str, Any]:
        """Test the search comparison endpoint."""
        print("\n🔍 Testing Search Comparison...")
        
        result = await self.test_endpoint(
            "/content/search/compare",
            method="POST",
            params={
                "query": "machine learning algorithms",
                "max_results": 3
            }
        )
        
        if result["success"]:
            data = result["data"]
            search_modes = data.get("search_modes", {})
            print("   ✅ Search comparison successful")
            
            for mode, mode_results in search_modes.items():
                count = mode_results.get("count", 0)
                print(f"      {mode}: {count} results")
        else:
            print(f"   ❌ Search comparison failed: {result['status']}")
        
        return result
    
    async def test_retrieval_stats(self) -> Dict[str, Any]:
        """Test the retrieval stats endpoint."""
        print("\n🔍 Testing Retrieval Stats...")
        
        result = await self.test_endpoint("/retrieval/stats")
        
        if result["success"]:
            data = result["data"]
            print("   ✅ Retrieval stats successful")
            
            # Extract key metrics
            vector_storage = data.get("vector_storage", {})
            total_vectors = vector_storage.get("total_vectors", 0)
            hybrid_available = data.get("hybrid_search_available", False)
            
            print(f"      Total vectors: {total_vectors}")
            print(f"      Hybrid search: {'Available' if hybrid_available else 'Not available'}")
            
            # Show retrieval engine stats
            retrieval_stats = data.get("retrieval_engine", {})
            total_searches = retrieval_stats.get("total_searches", 0)
            print(f"      Total searches performed: {total_searches}")
        else:
            print(f"   ❌ Retrieval stats failed: {result['status']}")
        
        return result
    
    async def test_performance(self) -> Dict[str, Any]:
        """Test search performance across multiple queries."""
        print("\n🔍 Testing Search Performance...")
        
        performance_results = []
        
        for query in TEST_QUERIES[:3]:  # Test first 3 queries
            print(f"   Testing query: '{query[:30]}...'")
            
            start_time = time.time()
            result = await self.test_endpoint(
                "/content/search",
                method="POST",
                params={
                    "query": query,
                    "max_results": 5,
                    "search_mode": "HYBRID"
                }
            )
            end_time = time.time()
            
            duration = end_time - start_time
            
            if result["success"]:
                count = len(result["data"])
                print(f"      ✅ {count} results in {duration:.3f}s")
                performance_results.append({
                    "query": query,
                    "duration": duration,
                    "results_count": count,
                    "success": True
                })
            else:
                print(f"      ❌ Failed in {duration:.3f}s")
                performance_results.append({
                    "query": query,
                    "duration": duration,
                    "results_count": 0,
                    "success": False
                })
        
        # Calculate averages
        successful_tests = [r for r in performance_results if r["success"]]
        if successful_tests:
            avg_duration = sum(r["duration"] for r in successful_tests) / len(successful_tests)
            avg_results = sum(r["results_count"] for r in successful_tests) / len(successful_tests)
            print(f"\n   📊 Performance Summary:")
            print(f"      Average response time: {avg_duration:.3f}s")
            print(f"      Average results per query: {avg_results:.1f}")
        
        return {
            "individual_results": performance_results,
            "summary": {
                "total_tests": len(performance_results),
                "successful_tests": len(successful_tests),
                "average_duration": avg_duration if successful_tests else 0,
                "average_results": avg_results if successful_tests else 0
            }
        }
    
    async def run_full_test_suite(self) -> Dict[str, Any]:
        """Run the complete test suite."""
        print("🚀 Sprint 3 API Integration Test Suite")
        print("=" * 50)
        
        results = {}
        
        # Test health check
        results["health"] = await self.test_health_check()
        
        # Test search modes
        results["search_modes"] = await self.test_search_modes()
        
        # Test search comparison
        results["search_comparison"] = await self.test_search_comparison()
        
        # Test retrieval stats
        results["retrieval_stats"] = await self.test_retrieval_stats()
        
        # Test performance
        results["performance"] = await self.test_performance()
        
        # Summary
        print("\n" + "=" * 50)
        print("📊 Test Suite Summary")
        print("=" * 50)
        
        total_tests = 0
        passed_tests = 0
        
        # Count individual test results
        for test_category, test_results in results.items():
            if test_category == "search_modes":
                for mode, mode_result in test_results.items():
                    total_tests += 1
                    if mode_result.get("success", False):
                        passed_tests += 1
            elif test_category == "performance":
                perf_summary = test_results.get("summary", {})
                total_tests += perf_summary.get("total_tests", 0)
                passed_tests += perf_summary.get("successful_tests", 0)
            else:
                total_tests += 1
                if test_results.get("success", False):
                    passed_tests += 1
        
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Total tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success rate: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 Sprint 3 integration is working well!")
        elif success_rate >= 60:
            print("⚠️  Sprint 3 integration has some issues")
        else:
            print("❌ Sprint 3 integration needs attention")
        
        return results


async def main():
    """Main test runner."""
    async with Sprint3APITester(API_BASE_URL) as tester:
        results = await tester.run_full_test_suite()
        
        # Save detailed results
        with open("sprint3_api_test_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        print(f"\n📝 Detailed results saved to: sprint3_api_test_results.json")


if __name__ == "__main__":
    asyncio.run(main())
