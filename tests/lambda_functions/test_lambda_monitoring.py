import boto3
import time
import json
from datetime import datetime, timedelta

class LambdaMonitoringTester:
    
    def __init__(self, function_name: str, region: str = 'us-west-2'):
        self.function_name = function_name
        self.region = region
        self.cloudwatch = boto3.client('cloudwatch', region_name=region)
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.logs_client = boto3.client('logs', region_name=region)
    
    def get_lambda_metrics(self, start_time: datetime, end_time: datetime) -> Dict:
        """Get Lambda function metrics"""
        metrics = {}
        
        metric_names = [
            'Invocations',
            'Errors', 
            'Duration',
            'Throttles',
            'ConcurrentExecutions'
        ]
        
        for metric_name in metric_names:
            try:
                response = self.cloudwatch.get_metric_statistics(
                    Namespace='AWS/Lambda',
                    MetricName=metric_name,
                    Dimensions=[
                        {
                            'Name': 'FunctionName',
                            'Value': self.function_name
                        }
                    ],
                    StartTime=start_time,
                    EndTime=end_time,
                    Period=300,  # 5 minutes
                    Statistics=['Sum', 'Average', 'Maximum']
                )
                
                metrics[metric_name] = response['Datapoints']
                
            except Exception as e:
                print(f"Error getting {metric_name} metrics: {e}")
                metrics[metric_name] = []
        
        return metrics
    
    def test_lambda_performance(self, num_invocations: int = 20) -> Dict:
        """Test Lambda performance and collect metrics"""
        print(f"Testing Lambda performance with {num_invocations} invocations...")
        
        start_time = datetime.utcnow()
        
        # Generate test invocations
        for i in range(num_invocations):
            payload = {
                'message_id': 2000 + i,
                'content': f'Performance test message number {i+1}'
            }
            
            try:
                self.lambda_client.invoke(
                    FunctionName=self.function_name,
                    InvocationType='Event',
                    Payload=json.dumps(payload)
                )
                
                if i % 5 == 0:
                    print(f"Sent {i+1}/{num_invocations} invocations")
                    
            except Exception as e:
                print(f"Error in invocation {i+1}: {e}")
        
        # Wait for processing to complete
        print("Waiting for processing to complete...")
        time.sleep(60)
        
        end_time = datetime.utcnow()
        
        # Get metrics
        metrics = self.get_lambda_metrics(start_time, end_time)
        
        return {
            'test_period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat()
            },
            'metrics': metrics
        }
    
    def analyze_error_logs(self, hours_back: int = 1) -> Dict:
        """Analyze Lambda error logs"""
        try:
            log_group_name = f'/aws/lambda/{self.function_name}'
            
            # Get log streams from the last hour
            start_time = datetime.utcnow() - timedelta(hours=hours_back)
            
            streams_response = self.logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=10
            )
            
            error_patterns = ['ERROR', 'Exception', 'Failed', 'Traceback']
            errors = []
            
            for stream in streams_response['logStreams']:
                try:
                    events_response = self.logs_client.get_log_events(
                        logGroupName=log_group_name,
                        logStreamName=stream['logStreamName'],
                        startTime=int(start_time.timestamp() * 1000)
                    )
                    
                    for event in events_response['events']:
                        message = event['message']
                        if any(pattern in message for pattern in error_patterns):
                            errors.append({
                                'timestamp': datetime.fromtimestamp(event['timestamp'] / 1000).isoformat(),
                                'message': message,
                                'stream': stream['logStreamName']
                            })
                            
                except Exception as e:
                    print(f"Error reading log stream {stream['logStreamName']}: {e}")
            
            return {
                'errors_found': len(errors),
                'errors': errors[:20]  # Limit to first 20 errors
            }
            
        except Exception as e:
            return {'error': f"Failed to analyze logs: {e}"}
    
    def test_lambda_limits(self) -> Dict:
        """Test Lambda function against various limits"""
        print("Testing Lambda limits...")
        
        tests = []
        
        # Test 1: Large payload
        print("Test 1: Large payload")
        large_content = "A" * 5000  # 5KB content
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'message_id': 3001,
                    'content': large_content
                })
            )
            tests.append({
                'test': 'large_payload',
                'success': response['StatusCode'] == 200,
                'payload_size': len(large_content)
            })
        except Exception as e:
            tests.append({
                'test': 'large_payload',
                'success': False,
                'error': str(e)
            })
        
        # Test 2: Concurrent invocations
        print("Test 2: Concurrent invocations")
        import threading
        
        def invoke_lambda(thread_id):
            try:
                response = self.lambda_client.invoke(
                    FunctionName=self.function_name,
                    InvocationType='Event',
                    Payload=json.dumps({
                       'message_id': 3100 + thread_id,
                       'content': f'Concurrent test message {thread_id}'
                   })
               )
                return response['StatusCode'] == 202
            except Exception as e:
                print(f"Thread {thread_id} error: {e}")
                return False
        
        # Launch 10 concurrent invocations
        threads = []
        results = []
        
        for i in range(10):
            thread = threading.Thread(target=lambda: results.append(invoke_lambda(i)))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        concurrent_success_rate = sum(results) / len(results) if results else 0
        tests.append({
            'test': 'concurrent_invocations',
            'total_invocations': 10,
            'successful_invocations': sum(results),
            'success_rate': concurrent_success_rate
        })
        
        # Test 3: Memory usage patterns
        print("Test 3: Memory usage test")
        try:
            # Invoke with varying content sizes to test memory
            memory_test_results = []
            for size in [100, 1000, 5000]:
                content = "X" * size
                response = self.lambda_client.invoke(
                    FunctionName=self.function_name,
                    InvocationType='RequestResponse',
                    Payload=json.dumps({
                        'message_id': 3200 + size,
                        'content': content
                    })
                )
                
                # Extract memory usage from logs if available
                memory_test_results.append({
                    'content_size': size,
                    'status_code': response['StatusCode'],
                    'success': response['StatusCode'] == 200
                })
            
            tests.append({
                'test': 'memory_usage',
                'results': memory_test_results
            })
            
        except Exception as e:
            tests.append({
                'test': 'memory_usage',
                'success': False,
                'error': str(e)
            })
        
        return {'limit_tests': tests}

    def generate_test_report(self) -> Dict:
        """Generate comprehensive test report"""
        print("=== Generating Comprehensive Lambda Test Report ===")
        
        report = {
            'function_name': self.function_name,
            'test_timestamp': datetime.utcnow().isoformat(),
            'tests': {}
        }
        
        # Performance test
        print("Running performance test...")
        perf_results = self.test_lambda_performance(15)
        report['tests']['performance'] = perf_results
        
        # Error analysis
        print("Analyzing error logs...")
        error_results = self.analyze_error_logs(2)  # Last 2 hours
        report['tests']['error_analysis'] = error_results
        
        # Limits testing
        print("Testing limits...")
        limits_results = self.test_lambda_limits()
        report['tests']['limits'] = limits_results
        
        # Function configuration
        try:
            config_response = self.lambda_client.get_function_configuration(
                FunctionName=self.function_name
            )
            report['function_config'] = {
                'runtime': config_response['Runtime'],
                'timeout': config_response['Timeout'],
                'memory_size': config_response['MemorySize'],
                'last_modified': config_response['LastModified']
            }
        except Exception as e:
            report['function_config'] = {'error': str(e)}
        
        return report

def main():
    """Run comprehensive monitoring tests"""
    function_name = 'message-processor-lambda'  # Update with your function name

    tester = LambdaMonitoringTester(function_name)

    # Generate comprehensive report
    report = tester.generate_test_report()

    # Print summary
    print("\n=== TEST REPORT SUMMARY ===")
    print(f"Function: {report['function_name']}")
    print(f"Test Time: {report['test_timestamp']}")

    # Performance summary
    if 'performance' in report['tests']:
        metrics = report['tests']['performance']['metrics']
        invocations = metrics.get('Invocations', [])
        errors = metrics.get('Errors', [])
        
        total_invocations = sum(dp['Sum'] for dp in invocations)
        total_errors = sum(dp['Sum'] for dp in errors)
        
        print(f"Total Invocations: {int(total_invocations)}")
        print(f"Total Errors: {int(total_errors)}")
        if total_invocations > 0:
            error_rate = (total_errors / total_invocations) * 100
            print(f"Error Rate: {error_rate:.2f}%")

    # Error analysis summary
    if 'error_analysis' in report['tests']:
        error_count = report['tests']['error_analysis']['errors_found']
        print(f"Recent Errors Found: {error_count}")

    # Limits testing summary
    if 'limits' in report['tests']:
        limit_tests = report['tests']['limits']['limit_tests']
        successful_limit_tests = sum(1 for test in limit_tests if test.get('success', False))
        print(f"Limit Tests Passed: {successful_limit_tests}/{len(limit_tests)}")

    # Save detailed report
    with open(f'lambda_test_report_{int(time.time())}.json', 'w') as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\nDetailed report saved to lambda_test_report_{int(time.time())}.json")

if __name__ == "__main__":
    main()