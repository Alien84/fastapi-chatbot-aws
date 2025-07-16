import boto3
import json
import time
import threading
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import random

class LambdaLoadTester:
    
    def __init__(self, function_name: str, region: str = 'us-west-2'):
        self.function_name = function_name
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.results = []
        self.lock = threading.Lock()
    
    def generate_test_payload(self, test_id: int) -> Dict:
        """Generate varied test payloads"""
        test_messages = [
            "I absolutely love this new feature!",
            "This is terrible and doesn't work at all.",
            "The documentation could be better.",
            "Amazing work on this project, very impressive!",
            "I'm having mixed feelings about this update.",
            "The interface is clean and user-friendly.",
            "This is frustrating and confusing.",
            "Excellent customer service experience!",
            "The loading time is too slow.",
            "Perfect! Exactly what I was looking for."
        ]
        
        return {
            'message_id': 5000 + test_id,
            'content': random.choice(test_messages)
        }
    
    def invoke_lambda_sync(self, payload: Dict, test_id: int) -> Dict:
        """Synchronous Lambda invocation with timing"""
        start_time = time.time()
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            result = {
                'test_id': test_id,
                'success': response['StatusCode'] == 200,
                'status_code': response['StatusCode'],
                'duration': duration,
                'timestamp': start_time
            }
            
            # Parse response body if successful
            if response['StatusCode'] == 200:
                try:
                    response_body = json.loads(response['Payload'].read())
                    result['response_body'] = response_body
                except:
                    result['response_parse_error'] = True
            
            return result
            
        except Exception as e:
            return {
                'test_id': test_id,
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time,
                'timestamp': start_time
            }
    
    def invoke_lambda_async(self, payload: Dict, test_id: int) -> Dict:
        """Asynchronous Lambda invocation"""
        start_time = time.time()
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType='Event',
                Payload=json.dumps(payload)
            )
            
            duration = time.time() - start_time
            
            return {
                'test_id': test_id,
                'success': response['StatusCode'] == 202,
                'status_code': response['StatusCode'],
                'duration': duration,
                'timestamp': start_time
            }
            
        except Exception as e:
            return {
                'test_id': test_id,
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time,
                'timestamp': start_time
            }
    
    def concurrent_load_test(self, 
                           num_threads: int = 10, 
                           requests_per_thread: int = 5,
                           invocation_type: str = 'sync') -> Dict:
        """Run concurrent load test"""
        
        print(f"Starting concurrent load test:")
        print(f"  Threads: {num_threads}")
        print(f"  Requests per thread: {requests_per_thread}")
        print(f"  Total requests: {num_threads * requests_per_thread}")
        print(f"  Invocation type: {invocation_type}")
        
        start_time = time.time()
        results = []
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = []
            
            for thread_id in range(num_threads):
                for req_id in range(requests_per_thread):
                    test_id = thread_id * requests_per_thread + req_id
                    payload = self.generate_test_payload(test_id)
                    
                    if invocation_type == 'sync':
                        future = executor.submit(self.invoke_lambda_sync, payload, test_id)
                    else:
                        future = executor.submit(self.invoke_lambda_async, payload, test_id)
                    
                    futures.append(future)
            
            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    
                    if len(results) % 10 == 0:
                        print(f"Completed {len(results)}/{len(futures)} requests")
                        
                except Exception as e:
                    print(f"Future failed: {e}")
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        # Analyze results
        successful_requests = [r for r in results if r['success']]
        failed_requests = [r for r in results if not r['success']]
        
        durations = [r['duration'] for r in successful_requests]
        
        analysis = {
            'test_config': {
                'num_threads': num_threads,
                'requests_per_thread': requests_per_thread,
                'total_requests': len(results),
                'invocation_type': invocation_type
            },
            'timing': {
                'total_test_duration': total_duration,
                'requests_per_second': len(results) / total_duration if total_duration > 0 else 0
            },
            'success_metrics': {
                'successful_requests': len(successful_requests),
                'failed_requests': len(failed_requests),
                'success_rate': len(successful_requests) / len(results) if results else 0
            },
            'performance_metrics': {
                'avg_duration': statistics.mean(durations) if durations else 0,
                'median_duration': statistics.median(durations) if durations else 0,
                'min_duration': min(durations) if durations else 0,
                'max_duration': max(durations) if durations else 0,
                'std_deviation': statistics.stdev(durations) if len(durations) > 1 else 0
            },
            'errors': [{'test_id': r['test_id'], 'error': r.get('error', 'Unknown')} 
                      for r in failed_requests[:10]]  # First 10 errors
        }
        
        return analysis
    
    def ramp_up_test(self, 
                     max_threads: int = 20, 
                     ramp_duration: int = 60,
                     requests_per_thread: int = 3) -> Dict:
        """Gradual ramp-up load test"""
        
        print(f"Starting ramp-up test:")
        print(f"  Max threads: {max_threads}")
        print(f"  Ramp duration: {ramp_duration}s")
        print(f"  Requests per thread: {requests_per_thread}")
        
        results = []
        start_time = time.time()
        
        # Calculate ramp-up intervals
        ramp_interval = ramp_duration / max_threads
        
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []
            
            for thread_num in range(max_threads):
                # Wait for ramp-up interval
                if thread_num > 0:
                    time.sleep(ramp_interval)
                
                print(f"Starting thread {thread_num + 1}/{max_threads}")
                
                # Submit requests for this thread
                for req_id in range(requests_per_thread):
                    test_id = thread_num * requests_per_thread + req_id
                    payload = self.generate_test_payload(test_id)
                    
                    future = executor.submit(self.invoke_lambda_async, payload, test_id)
                    futures.append(future)
            
            # Collect all results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"Future failed: {e}")
        
        total_duration = time.time() - start_time
        
        # Analyze results similar to concurrent test
        successful_requests = [r for r in results if r['success']]
        
        return {
            'test_type': 'ramp_up',
            'total_requests': len(results),
            'successful_requests': len(successful_requests),
            'success_rate': len(successful_requests) / len(results) if results else 0,
            'total_duration': total_duration,
            'ramp_config': {
                'max_threads': max_threads,
                'ramp_duration': ramp_duration,
                'requests_per_thread': requests_per_thread
            }
        }
    
    def sustained_load_test(self, 
                           threads: int = 5, 
                           duration_minutes: int = 5,
                           requests_per_minute: int = 12) -> Dict:
        """Sustained load over time"""
        
        print(f"Starting sustained load test:")
        print(f"  Threads: {threads}")
        print(f"  Duration: {duration_minutes} minutes")
        print(f"  Requests per minute: {requests_per_minute}")
        
        results = []
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)
        
        request_interval = 60 / requests_per_minute  # Seconds between requests
        test_id = 0
        
        while time.time() < end_time:
            with ThreadPoolExecutor(max_workers=threads) as executor:
                futures = []
                
                # Submit batch of requests
                for _ in range(min(threads, requests_per_minute)):
                    payload = self.generate_test_payload(test_id)
                    future = executor.submit(self.invoke_lambda_async, payload, test_id)
                    futures.append(future)
                    test_id += 1
                
                # Collect results
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as e:
                        print(f"Request failed: {e}")
            
            # Wait for next interval
            time.sleep(request_interval)
            
            elapsed_minutes = (time.time() - start_time) / 60
            print(f"Elapsed: {elapsed_minutes:.1f}/{duration_minutes} minutes, "
                  f"Requests sent: {len(results)}")
        
        successful_requests = [r for r in results if r['success']]
        
        return {
            'test_type': 'sustained_load',
            'total_requests': len(results),
            'successful_requests': len(successful_requests),
            'success_rate': len(successful_requests) / len(results) if results else 0,
            'actual_duration': time.time() - start_time,
            'requests_per_second': len(results) / (time.time() - start_time)
        }

def main():
    """Run comprehensive load tests"""
    function_name = 'message-processor-lambda'
    tester = LambdaLoadTester(function_name)
    
    print("=== Lambda Function Load Testing ===\n")
    
    # Test 1: Concurrent synchronous requests
    print("Test 1: Concurrent Synchronous Requests")
    sync_results = tester.concurrent_load_test(
        num_threads=5,
        requests_per_thread=4,
        invocation_type='sync'
    )
    
    print(f"Results: {sync_results['success_metrics']['success_rate']:.1%} success rate")
    print(f"Average duration: {sync_results['performance_metrics']['avg_duration']:.3f}s")
    print(f"Requests per second: {sync_results['timing']['requests_per_second']:.2f}\n")
    
    # Test 2: Concurrent asynchronous requests
    print("Test 2: Concurrent Asynchronous Requests")
    async_results = tester.concurrent_load_test(
        num_threads=10,
        requests_per_thread=5,
        invocation_type='async'
    )
    
    print(f"Results: {async_results['success_metrics']['success_rate']:.1%} success rate")
    print(f"Requests per second: {async_results['timing']['requests_per_second']:.2f}\n")
    
    # Test 3: Ramp-up test
    print("Test 3: Ramp-up Load Test")
    ramp_results = tester.ramp_up_test(
        max_threads=15,
        ramp_duration=30,
        requests_per_thread=2
    )
    
    print(f"Results: {ramp_results['success_rate']:.1%} success rate")
    print(f"Total requests: {ramp_results['total_requests']}\n")
    
    # Test 4: Sustained load (shorter for demo)
    print("Test 4: Sustained Load Test")
    sustained_results = tester.sustained_load_test(
        threads=3,
        duration_minutes=2,
        requests_per_minute=10
    )
    
    print(f"Results: {sustained_results['success_rate']:.1%} success rate")
    print(f"Requests per second: {sustained_results['requests_per_second']:.2f}")
    
    # Summary
    print("\n=== Load Test Summary ===")
    all_tests = [
        ('Concurrent Sync', sync_results['success_metrics']['success_rate']),
        ('Concurrent Async', async_results['success_metrics']['success_rate']),
        ('Ramp-up', ramp_results['success_rate']),
        ('Sustained', sustained_results['success_rate'])
    ]
    
    for test_name, success_rate in all_tests:
        status = "✅ PASS" if success_rate > 0.9 else "⚠️  WARN" if success_rate > 0.7 else "❌ FAIL"
        print(f"{test_name}: {success_rate:.1%} {status}")

if __name__ == "__main__":
    main()