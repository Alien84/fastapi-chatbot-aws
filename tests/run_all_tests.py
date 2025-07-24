#!/usr/bin/env python3

import subprocess
import sys
import time
import os
from pathlib import Path

class TestRunner:
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.test_results = {}
    
    def run_test_suite(self, test_path, name, timeout=300):
        """Run a test suite and capture results"""
        print(f"\n{'='*60}")
        print(f"Running {name}")
        print(f"{'='*60}")
        
        start_time = time.time()
        
        try:
            result = subprocess.run([
                sys.executable, '-m', 'pytest', 
                str(test_path), 
                '-v', 
                '--tb=short',
                f'--timeout={timeout}'
            ], 
            cwd=self.project_root,
            capture_output=True,
            text=True,
            timeout=timeout
            )
            
            duration = time.time() - start_time
            
            self.test_results[name] = {
                'success': result.returncode == 0,
                'duration': duration,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
            
            if result.returncode == 0:
                print(f"✅ {name} PASSED ({duration:.1f}s)")
            else:
                print(f"❌ {name} FAILED ({duration:.1f}s)")
                print("STDOUT:", result.stdout[-500:])  # Last 500 chars
                print("STDERR:", result.stderr[-500:])
            
        except subprocess.TimeoutExpired:
            self.test_results[name] = {
                'success': False,
                'duration': timeout,
                'error': 'Test suite timed out'
            }
            print(f"⏰ {name} TIMED OUT after {timeout}s")
        
        except Exception as e:
            self.test_results[name] = {
                'success': False,
                'duration': time.time() - start_time,
                'error': str(e)
            }
            print(f"💥 {name} ERROR: {e}")
    
    def run_all_tests(self):
        """Run all test suites"""
        print("🚀 Starting comprehensive test suite")
        print(f"Project root: {self.project_root}")
        
        # Test suites in order of execution
        test_suites = [
            ('tests/database/test_schema.py', 'Database Schema Tests'),
            ('tests/database/test_data_operations.py', 'Database Operations Tests'),
            ('tests/api/test_api_integration.py', 'API Integration Tests'),
            ('tests/api/test_api_performance.py', 'API Performance Tests'),
            ('tests/infrastructure/test_pulumi_stack.py', 'Infrastructure Tests'),
            ('tests/infrastructure/test_docker_containers.py', 'Docker Container Tests'),
            ('tests/lambda/test_message_processor_unit.py', 'Lambda Unit Tests'),
            ('tests/security/test_security.py', 'Security Tests'),
            ('tests/monitoring/test_observability.py', 'Monitoring Tests'),
            ('tests/backup/test_backup_recovery.py', 'Backup & Recovery Tests'),
            ('tests/e2e/test_complete_workflow.py', 'End-to-End Tests'),
        ]
        
        total_start_time = time.time()
        
        for test_path, test_name in test_suites:
            full_test_path = self.project_root / test_path
            
            if full_test_path.exists():
                self.run_test_suite(full_test_path, test_name)
            else:
                print(f"⚠️  Test file not found: {test_path}")
                self.test_results[test_name] = {
                    'success': False,
                    'duration': 0,
                    'error': 'Test file not found'
                }
        
        total_duration = time.time() - total_start_time
        self.print_summary(total_duration)
    
    def print_summary(self, total_duration):
        """Print test summary"""
        print(f"\n{'='*60}")
        print("TEST SUMMARY")
        print(f"{'='*60}")
        
        passed = sum(1 for result in self.test_results.values() if result['success'])
        total = len(self.test_results)
        
        print(f"Total test suites: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success rate: {passed/total:.1%}")
        print(f"Total duration: {total_duration:.1f}s")
        
        print(f"\nDetailed Results:")
        print("-" * 60)
        
        for name, result in self.test_results.items():
            status = "✅ PASS" if result['success'] else "❌ FAIL"
            duration = result['duration']
            print(f"{status} {name:<40} ({duration:.1f}s)")
            
            if not result['success'] and 'error' in result:
                print(f"     Error: {result['error']}")
        
        # Return exit code
        return 0 if passed == total else 1

def main():
    """Main entry point"""
    runner = TestRunner()
    exit_code = runner.run_all_tests()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()