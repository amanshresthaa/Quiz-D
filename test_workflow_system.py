#!/usr/bin/env python3
"""
Comprehensive Test Script for Structured Workflow System

Tests the complete workflow from input/ to output/ with:
- File management and naming conventions
- Enhanced logging system
- Workflow orchestration
- End-to-end content processing
"""

import asyncio
import json
import requests
from datetime import datetime
from pathlib import Path
import sys

# Test configuration
BASE_URL = "http://localhost:8000"
TEST_QUERIES = [
    "cardiovascular disease",
    "pharmacology",
    "anatomy",
    "medical procedures"
]

class WorkflowTestSuite:
    """Comprehensive test suite for the structured workflow system."""
    
    def __init__(self, base_url: str = BASE_URL):
        """Initialize test suite."""
        self.base_url = base_url
        self.session = requests.Session()
        self.test_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": [],
            "summary": {}
        }
        
    def log_test_result(self, test_name: str, success: bool, details: dict = None):
        """Log test result."""
        result = {
            "test_name": test_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.test_results["tests"].append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details and not success:
            print(f"    Details: {details}")
    
    def test_api_health(self):
        """Test API health and basic connectivity."""
        try:
            response = self.session.get(f"{self.base_url}/health")
            success = response.status_code == 200
            
            self.log_test_result("API Health Check", success, {
                "status_code": response.status_code,
                "response": response.json() if success else response.text
            })
            return success
            
        except Exception as e:
            self.log_test_result("API Health Check", False, {"error": str(e)})
            return False
    
    def test_workflow_status(self):
        """Test workflow status endpoint."""
        try:
            response = self.session.get(f"{self.base_url}/workflow/status")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = {
                    "input_files_count": data.get("input_files_count", 0),
                    "input_files": data.get("input_files", []),
                    "directories": data.get("directories", {})
                }
            else:
                details = {"status_code": response.status_code, "error": response.text}
                
            self.log_test_result("Workflow Status", success, details)
            return success, data if success else None
            
        except Exception as e:
            self.log_test_result("Workflow Status", False, {"error": str(e)})
            return False, None
    
    def test_input_processing(self):
        """Test processing of input files."""
        try:
            response = self.session.post(f"{self.base_url}/workflow/process-inputs")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = {
                    "session_id": data.get("session_id"),
                    "files_processed": len(data.get("results", {}).get("processed_files", [])),
                    "errors": len(data.get("results", {}).get("errors", [])),
                    "message": data.get("message")
                }
            else:
                details = {"status_code": response.status_code, "error": response.text}
                
            self.log_test_result("Input Processing", success, details)
            return success, data if success else None
            
        except Exception as e:
            self.log_test_result("Input Processing", False, {"error": str(e)})
            return False, None
    
    def test_content_search(self, query: str = "cardiovascular"):
        """Test content search functionality."""
        try:
            search_payload = {
                "query": query,
                "max_results": 5
            }
            
            response = self.session.post(
                f"{self.base_url}/content/search",
                json=search_payload
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                results_count = len(data.get("results", []))
                details = {
                    "query": query,
                    "results_count": results_count,
                    "has_results": results_count > 0
                }
            else:
                details = {"status_code": response.status_code, "error": response.text}
                
            self.log_test_result(f"Content Search - {query}", success, details)
            return success, data if success else None
            
        except Exception as e:
            self.log_test_result(f"Content Search - {query}", False, {"error": str(e)})
            return False, None
    
    def test_workflow_quiz_generation(self, query: str, num_questions: int = 3):
        """Test workflow-based quiz generation."""
        try:
            response = self.session.post(
                f"{self.base_url}/workflow/generate-quiz",
                params={
                    "content_query": query,
                    "num_questions": num_questions,
                    "difficulty": "medium"
                }
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = {
                    "query": query,
                    "question_count": data.get("question_count", 0),
                    "quiz_file": data.get("quiz_file"),
                    "message": data.get("message")
                }
            else:
                details = {"status_code": response.status_code, "error": response.text}
                
            self.log_test_result(f"Workflow Quiz Generation - {query}", success, details)
            return success, data if success else None
            
        except Exception as e:
            self.log_test_result(f"Workflow Quiz Generation - {query}", False, {"error": str(e)})
            return False, None
    
    def test_workflow_question_generation(self, query: str, num_questions: int = 5):
        """Test workflow-based question generation."""
        try:
            response = self.session.post(
                f"{self.base_url}/workflow/generate-questions",
                params={
                    "content_query": query,
                    "num_questions": num_questions
                }
            )
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = {
                    "query": query,
                    "question_count": data.get("question_count", 0),
                    "questions_file": data.get("questions_file"),
                    "message": data.get("message")
                }
            else:
                details = {"status_code": response.status_code, "error": response.text}
                
            self.log_test_result(f"Workflow Question Generation - {query}", success, details)
            return success, data if success else None
            
        except Exception as e:
            self.log_test_result(f"Workflow Question Generation - {query}", False, {"error": str(e)})
            return False, None
    
    def test_session_completion(self):
        """Test workflow session completion."""
        try:
            response = self.session.post(f"{self.base_url}/workflow/complete-session")
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = {
                    "session_id": data.get("summary", {}).get("session_id"),
                    "duration_seconds": data.get("summary", {}).get("duration_seconds"),
                    "files_processed": data.get("summary", {}).get("performance_metrics", {}).get("files_processed")
                }
            else:
                details = {"status_code": response.status_code, "error": response.text}
                
            self.log_test_result("Session Completion", success, details)
            return success, data if success else None
            
        except Exception as e:
            self.log_test_result("Session Completion", False, {"error": str(e)})
            return False, None
    
    def test_file_structure_validation(self):
        """Validate that expected directories and files exist."""
        try:
            project_root = Path.cwd()
            
            # Check directory structure
            required_dirs = [
                "input",
                "output",
                "output/logs",
                "output/content",
                "output/quizzes",
                "output/questions"
            ]
            
            missing_dirs = []
            for dir_path in required_dirs:
                full_path = project_root / dir_path
                if not full_path.exists():
                    missing_dirs.append(dir_path)
            
            # Check for input files
            input_files = list((project_root / "input").glob("*.txt")) if (project_root / "input").exists() else []
            
            success = len(missing_dirs) == 0
            details = {
                "missing_directories": missing_dirs,
                "input_files_found": len(input_files),
                "input_files": [f.name for f in input_files]
            }
            
            self.log_test_result("File Structure Validation", success, details)
            return success
            
        except Exception as e:
            self.log_test_result("File Structure Validation", False, {"error": str(e)})
            return False
    
    def run_comprehensive_test(self):
        """Run the complete test suite."""
        print("🚀 Starting Comprehensive Workflow Test Suite")
        print("=" * 60)
        
        # Test 1: File structure validation
        print("\n📁 Testing File Structure...")
        self.test_file_structure_validation()
        
        # Test 2: API health
        print("\n🏥 Testing API Health...")
        if not self.test_api_health():
            print("❌ API is not responding. Please start the server first.")
            return False
        
        # Test 3: Workflow status
        print("\n📊 Testing Workflow Status...")
        status_success, status_data = self.test_workflow_status()
        
        # Test 4: Input processing
        print("\n📥 Testing Input Processing...")
        process_success, process_data = self.test_input_processing()
        
        # Test 5: Content search
        print("\n🔍 Testing Content Search...")
        for query in TEST_QUERIES[:2]:  # Test first 2 queries
            self.test_content_search(query)
        
        # Test 6: Workflow quiz generation
        print("\n🎯 Testing Workflow Quiz Generation...")
        for query in TEST_QUERIES[:2]:  # Test first 2 queries
            self.test_workflow_quiz_generation(query, 3)
        
        # Test 7: Workflow question generation
        print("\n❓ Testing Workflow Question Generation...")
        for query in TEST_QUERIES[:2]:  # Test first 2 queries
            self.test_workflow_question_generation(query, 5)
        
        # Test 8: Session completion
        print("\n🏁 Testing Session Completion...")
        self.test_session_completion()
        
        # Generate summary
        self.generate_test_summary()
        
        return True
    
    def generate_test_summary(self):
        """Generate and display test summary."""
        total_tests = len(self.test_results["tests"])
        passed_tests = sum(1 for test in self.test_results["tests"] if test["success"])
        failed_tests = total_tests - passed_tests
        
        self.test_results["summary"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": failed_tests,
            "success_rate": passed_tests / total_tests if total_tests > 0 else 0
        }
        
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {self.test_results['summary']['success_rate']:.1%}")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for test in self.test_results["tests"]:
                if not test["success"]:
                    print(f"   - {test['test_name']}")
        
        # Save detailed results
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            results_file = f"output/logs/{timestamp}_workflow_test_results_v1.json"
            
            with open(results_file, 'w') as f:
                json.dump(self.test_results, f, indent=2)
            
            print(f"\n💾 Detailed results saved to: {results_file}")
            
        except Exception as e:
            print(f"\n⚠️  Could not save detailed results: {e}")


def main():
    """Main test execution function."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL
    
    print(f"Testing API at: {base_url}")
    
    # Create and run test suite
    test_suite = WorkflowTestSuite(base_url)
    success = test_suite.run_comprehensive_test()
    
    if success:
        print("\n🎉 Workflow test suite completed!")
    else:
        print("\n💥 Workflow test suite encountered critical errors!")
        sys.exit(1)


if __name__ == "__main__":
    main()
