#!/usr/bin/env python3
"""
Complete Workflow System Test

Tests the entire workflow system end-to-end including:
1. API server functionality
2. Structured input/output processing  
3. JSON serialization validation
4. File management and logging
5. Performance metrics
"""

import asyncio
import requests
import json
import time
from pathlib import Path
import sys

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent / "app"))

from app.workflow_orchestrator import get_workflow_orchestrator
from app.file_manager import get_file_manager
from app.enhanced_logging import get_quiz_logger

class WorkflowSystemTest:
    """Comprehensive test suite for the workflow system."""
    
    def __init__(self, api_base_url="http://localhost:8001"):
        self.api_base_url = api_base_url
        self.workflow = get_workflow_orchestrator()
        self.file_manager = get_file_manager()
        self.logger = get_quiz_logger("test")
        self.test_results = {}
        
    def test_api_connectivity(self):
        """Test basic API connectivity."""
        print("🔗 Testing API connectivity...")
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            if response.status_code == 200:
                print("   ✅ API server is accessible")
                return True
            else:
                print(f"   ❌ API returned status code: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ API connectivity failed: {e}")
            return False
    
    def test_workflow_status(self):
        """Test workflow status endpoint."""
        print("📊 Testing workflow status endpoint...")
        try:
            response = requests.get(f"{self.api_base_url}/workflow/status", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Status endpoint working")
                print(f"   📁 Input files: {data.get('input_files_count', 0)}")
                print(f"   📂 Output directories: {len(data.get('directories', {}))}")
                return True
            else:
                print(f"   ❌ Status endpoint failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Status test failed: {e}")
            return False
    
    def test_input_processing(self):
        """Test input file processing."""
        print("📥 Testing input file processing...")
        try:
            response = requests.post(f"{self.api_base_url}/workflow/process-inputs", timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    processed_count = len(data.get("results", {}).get("processed_files", []))
                    print(f"   ✅ Successfully processed {processed_count} files")
                    print(f"   🆔 Session ID: {data.get('session_id')}")
                    self.current_session = data.get('session_id')
                    return True
                else:
                    print(f"   ❌ Processing failed: {data.get('error')}")
                    return False
            else:
                print(f"   ❌ Processing endpoint failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"   ❌ Input processing test failed: {e}")
            return False
    
    async def test_direct_workflow(self):
        """Test workflow orchestrator directly (bypassing API)."""
        print("🔄 Testing workflow orchestrator directly...")
        try:
            # Start session
            session_id = await self.workflow.start_processing_session()
            print(f"   ✅ Started session: {session_id}")
            
            # Process inputs
            results = await self.workflow.process_all_input_files()
            if results.get("processed_files"):
                print(f"   ✅ Processed {len(results['processed_files'])} files")
            else:
                print(f"   ❌ No files processed")
                return False
            
            # Generate quiz
            quiz_result = await self.workflow.generate_quiz_from_content(
                content_query="cardiovascular disease",
                num_questions=3,
                difficulty="medium"
            )
            
            if quiz_result.get("success"):
                print(f"   ✅ Generated quiz: {quiz_result['quiz_file']}")
                print(f"   📝 Questions: {quiz_result['question_count']}")
            else:
                print(f"   ❌ Quiz generation failed: {quiz_result.get('error')}")
                return False
            
            # Generate questions
            questions_result = await self.workflow.generate_questions_from_content(
                content_query="heart failure",
                num_questions=5
            )
            
            if questions_result.get("success"):
                print(f"   ✅ Generated questions: {questions_result['questions_file']}")
                print(f"   📝 Questions: {questions_result['question_count']}")
            else:
                print(f"   ❌ Question generation failed: {questions_result.get('error')}")
                return False
            
            # Complete session
            summary = await self.workflow.complete_session()
            print(f"   ✅ Session completed: {summary.get('duration_seconds', 0):.1f}s")
            
            return True
            
        except Exception as e:
            print(f"   ❌ Direct workflow test failed: {e}")
            return False
    
    def test_json_serialization(self):
        """Test JSON output file quality."""
        print("🔍 Testing JSON serialization quality...")
        
        quiz_files = list(self.file_manager.output_dir.glob("quizzes/*.json"))
        question_files = list(self.file_manager.output_dir.glob("questions/*.json"))
        
        issues_found = 0
        
        # Test quiz files
        for quiz_file in quiz_files[-3:]:  # Test last 3 files
            try:
                with open(quiz_file, 'r') as f:
                    data = json.load(f)
                
                # Check structure
                if 'quiz' in data and 'questions' in data['quiz']:
                    questions = data['quiz']['questions']
                    print(f"   ✅ {quiz_file.name}: {len(questions)} questions")
                    
                    # Check for serialization artifacts
                    json_str = json.dumps(data)
                    if '_value_' in json_str or '__objclass__' in json_str:
                        print(f"   ⚠️  {quiz_file.name}: Contains serialization artifacts")
                        issues_found += 1
                    
                else:
                    print(f"   ❌ {quiz_file.name}: Invalid structure")
                    issues_found += 1
                    
            except Exception as e:
                print(f"   ❌ {quiz_file.name}: JSON error - {e}")
                issues_found += 1
        
        # Test question files
        for q_file in question_files[-3:]:  # Test last 3 files
            try:
                with open(q_file, 'r') as f:
                    data = json.load(f)
                
                if 'questions' in data:
                    questions = data['questions']
                    print(f"   ✅ {q_file.name}: {len(questions)} questions")
                else:
                    print(f"   ❌ {q_file.name}: Invalid structure")
                    issues_found += 1
                    
            except Exception as e:
                print(f"   ❌ {q_file.name}: JSON error - {e}")
                issues_found += 1
        
        if issues_found == 0:
            print(f"   ✅ All JSON files are properly serialized")
            return True
        else:
            print(f"   ⚠️  Found {issues_found} serialization issues")
            return False
    
    def test_file_naming_convention(self):
        """Test file naming convention compliance."""
        print("📝 Testing file naming convention...")
        
        all_files = []
        for subdir in ['content', 'quizzes', 'questions', 'logs']:
            subdir_path = self.file_manager.output_dir / subdir
            if subdir_path.exists():
                all_files.extend(subdir_path.glob("*.json"))
                all_files.extend(subdir_path.glob("*.txt"))
        
        valid_names = 0
        total_files = len(all_files)
        
        for file_path in all_files:
            # Check YYYYMMDD_<description>_<version>.ext pattern
            name = file_path.name
            if len(name) >= 10 and name[:8].isdigit() and '_' in name:
                valid_names += 1
                print(f"   ✅ {name}")
            else:
                print(f"   ❌ {name}: Invalid naming pattern")
        
        compliance_rate = (valid_names / total_files * 100) if total_files > 0 else 0
        print(f"   📊 Naming convention compliance: {compliance_rate:.1f}% ({valid_names}/{total_files})")
        
        return compliance_rate >= 90
    
    def test_logging_functionality(self):
        """Test logging system functionality."""
        print("📋 Testing logging functionality...")
        
        log_files = list(self.file_manager.logs_dir.glob("*.log"))
        json_logs = list(self.file_manager.logs_dir.glob("*.jsonl"))
        
        print(f"   📄 Log files: {len(log_files)}")
        print(f"   📄 JSON logs: {len(json_logs)}")
        
        # Test recent log file
        if log_files:
            recent_log = max(log_files, key=lambda f: f.stat().st_mtime)
            with open(recent_log, 'r') as f:
                lines = f.readlines()
            print(f"   ✅ Recent log has {len(lines)} entries")
            return True
        else:
            print(f"   ❌ No log files found")
            return False
    
    async def run_all_tests(self):
        """Run complete test suite."""
        print("🚀 Running Complete Workflow System Test Suite")
        print("=" * 60)
        
        test_results = {}
        
        # API Tests
        test_results['api_connectivity'] = self.test_api_connectivity()
        test_results['workflow_status'] = self.test_workflow_status()
        test_results['input_processing'] = self.test_input_processing()
        
        # Direct Workflow Tests
        test_results['direct_workflow'] = await self.test_direct_workflow()
        
        # Quality Tests
        test_results['json_serialization'] = self.test_json_serialization()
        test_results['naming_convention'] = self.test_file_naming_convention()
        test_results['logging_functionality'] = self.test_logging_functionality()
        
        # Summary
        print("\n" + "=" * 60)
        print("🏁 Test Results Summary")
        print("=" * 60)
        
        passed = sum(1 for result in test_results.values() if result)
        total = len(test_results)
        
        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"   {test_name.replace('_', ' ').title()}: {status}")
        
        success_rate = (passed / total * 100)
        print(f"\n📊 Overall Success Rate: {success_rate:.1f}% ({passed}/{total})")
        
        if success_rate >= 90:
            print("🎉 Workflow system is working excellently!")
        elif success_rate >= 70:
            print("👍 Workflow system is working well with minor issues")
        else:
            print("⚠️  Workflow system needs attention")
        
        return test_results


async def main():
    """Run the complete workflow test suite."""
    tester = WorkflowSystemTest()
    results = await tester.run_all_tests()
    return results


if __name__ == "__main__":
    asyncio.run(main())
