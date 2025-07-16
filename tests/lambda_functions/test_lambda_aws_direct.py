import boto3
import json
import time
from typing import List, Dict

class AWSLambdaTester:
    
    def __init__(self, function_name: str, region: str = 'us-west-2'):
        self.lambda_client = boto3.client('lambda', region_name=region)
        self.function_name = function_name
    
    def test_single_invocation(self, payload: Dict) -> Dict:
        """Test single Lambda invocation"""
        print(f"Testing Lambda function: {self.function_name}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
            
            result = json.loads(response['Payload'].read())
            
            print(f"Status Code: {response['StatusCode']}")
            print(f"Response: {json.dumps(result, indent=2)}")
            
            return {
                'success': response['StatusCode'] == 200,
                'response': result,
                'execution_time': response.get('ResponseMetadata', {}).get('HTTPHeaders', {}).get('x-amzn-RequestId')
            }
            
        except Exception as e:
            print(f"Error: {e}")
            return {'success': False, 'error': str(e)}
    
    def test_async_invocation(self, payload: Dict) -> Dict:
        """Test asynchronous Lambda invocation"""
        try:
            response = self.lambda_client.invoke(
                FunctionName=self.function_name,
                InvocationType='Event',  # Asynchronous
                Payload=json.dumps(payload)
            )
            
            return {
                'success': response['StatusCode'] == 202,
                'status_code': response['StatusCode']
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_multiple_messages(self, test_cases: List[Dict]) -> List[Dict]:
        """Test multiple messages"""
        results = []
        
        for i, test_case in enumerate(test_cases):
            print(f"\n--- Test Case {i+1} ---")
            result = self.test_single_invocation(test_case)
            results.append(result)
            time.sleep(1)  # Small delay between tests
        
        return results
    
    def test_error_scenarios(self) -> List[Dict]:
        """Test error handling scenarios"""
        error_test_cases = [
            {
                'message_id': 'invalid',  # Invalid type
                'content': 'Test message'
            },
            {
                'message_id': 123,
                'content': ''  # Empty content
            },
            {
                'message_id': 123,
                'content': 'A' * 10000  # Very long content
            },
            {
                'invalid_field': 'test'  # Missing required fields
            }
        ]
        
        print("\n=== Testing Error Scenarios ===")
        return self.test_multiple_messages(error_test_cases)
    
    def performance_test(self, num_invocations: int = 10) -> Dict:
        """Test Lambda performance"""
        print(f"\n=== Performance Test ({num_invocations} invocations) ===")
        
        payload = {
            'message_id': 999,
            'content': 'Performance test message for sentiment analysis'
        }
        
        start_time = time.time()
        successful_invocations = 0
        
        for i in range(num_invocations):
            result = self.test_async_invocation(payload)
            if result['success']:
                successful_invocations += 1
            
            if i % 5 == 0:
                print(f"Completed {i+1}/{num_invocations} invocations")
        
        total_time = time.time() - start_time
        
        return {
            'total_invocations': num_invocations,
            'successful_invocations': successful_invocations,
            'success_rate': successful_invocations / num_invocations,
            'total_time': total_time,
            'average_time_per_invocation': total_time / num_invocations
        }

def main():
    """Run comprehensive Lambda tests"""
    tester = AWSLambdaTester('message-processor-lambda')
    
    # Test cases with different sentiments
    test_cases = [
        {
            'message_id': 1001,
            'content': 'I absolutely love this new feature! It works perfectly!'
        },
        {
            'message_id': 1002,
            'content': 'This is terrible and I hate it. Very disappointing.'
        },
        {
            'message_id': 1003,
            'content': 'The weather today is okay, nothing special.'
        },
        {
            'message_id': 1004,
            'content': 'Mixed feelings about this update, some good some bad.'
        }
    ]
    
    # Run normal test cases
    print("=== Testing Normal Scenarios ===")
    normal_results = tester.test_multiple_messages(test_cases)
    
    # Run error scenarios
    error_results = tester.test_error_scenarios()
    
    # Run performance test
    perf_results = tester.performance_test(10)
    
    # Summary
    print("\n=== Test Summary ===")
    successful_normal = sum(1 for r in normal_results if r['success'])
    print(f"Normal test cases: {successful_normal}/{len(normal_results)} passed")
    
    successful_errors = sum(1 for r in error_results if not r['success'])
    print(f"Error handling: {successful_errors}/{len(error_results)} handled correctly")
    
    print(f"Performance test: {perf_results['success_rate']:.1%} success rate")
    print(f"Average invocation time: {perf_results['average_time_per_invocation']:.2f}s")

if __name__ == "__main__":
    main()