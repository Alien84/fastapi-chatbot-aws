import requests
import time
import boto3
import json
from typing import Dict, List

class E2EWorkflowTester:
    
    def __init__(self, api_base_url: str, region: str = 'us-west-2'):
        self.api_base_url = api_base_url.rstrip('/')
        self.region = region
        self.logs_client = boto3.client('logs', region_name=region)
    
    def send_chat_message(self, content: str) -> Dict:
        """Send a chat message via FastAPI"""
        try:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"content": content},
                timeout=10
            )
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'data': response.json(),
                    'message_id': response.json().get('message_id')
                }
            else:
                return {
                    'success': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def check_sentiment_analysis(self, message_id: int, max_retries: int = 5) -> Dict:
        """Check if sentiment analysis is complete for a message"""
        for attempt in range(max_retries):
            try:
                response = requests.get(
                    f"{self.api_base_url}/message/{message_id}/sentiment",
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('sentiment') is not None:
                        return {
                            'success': True,
                            'sentiment_data': data
                        }
                
                # Wait before retry
                time.sleep(2)
                
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {e}")
                time.sleep(2)
        
        return {'success': False, 'error': 'Sentiment analysis not completed after retries'}
    
    def get_lambda_logs(self, log_group_name: str = '/aws/lambda/message-processor-lambda') -> List[str]:
        """Get recent Lambda function logs"""
        try:
            # Get recent log streams
            streams_response = self.logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=1
            )
            
            if not streams_response['logStreams']:
                return []
            
            # Get log events from the most recent stream
            latest_stream = streams_response['logStreams'][0]['logStreamName']
            
            events_response = self.logs_client.get_log_events(
                logGroupName=log_group_name,
                logStreamName=latest_stream,
                limit=50
            )
            
            return [event['message'] for event in events_response['events']]
            
        except Exception as e:
            print(f"Error getting logs: {e}")
            return []
    
    def test_complete_workflow(self, test_message: str) -> Dict:
        """Test the complete workflow from API to Lambda"""
        print(f"\n--- Testing Complete Workflow ---")
        print(f"Test message: '{test_message}'")
        
        # Step 1: Send chat message
        print("Step 1: Sending chat message...")
        chat_result = self.send_chat_message(test_message)
        
        if not chat_result['success']:
            return {'success': False, 'step': 'chat', 'error': chat_result.get('error')}
        
        message_id = chat_result['message_id']
        print(f"✅ Message sent successfully (ID: {message_id})")
        
        # Step 2: Wait for Lambda processing
        print("Step 2: Waiting for Lambda processing...")
        time.sleep(3)  # Give Lambda time to process
        
        # Step 3: Check sentiment analysis
        print("Step 3: Checking sentiment analysis...")
        sentiment_result = self.check_sentiment_analysis(message_id)
        
        if not sentiment_result['success']:
            # Get Lambda logs for debugging
            logs = self.get_lambda_logs()
            return {
                'success': False, 
                'step': 'sentiment_analysis', 
                'error': sentiment_result.get('error'),
                'lambda_logs': logs[-10:]  # Last 10 log entries
            }
        
        sentiment_data = sentiment_result['sentiment_data']
        print(f"✅ Sentiment analysis complete:")
        print(f"   Sentiment: {sentiment_data['sentiment']}")
        print(f"   Confidence: {sentiment_data['sentiment_confidence']:.3f}")
        
        return {
            'success': True,
            'message_id': message_id,
            'sentiment': sentiment_data['sentiment'],
            'confidence': sentiment_data['sentiment_confidence']
        }
    
    def run_comprehensive_test(self) -> Dict:
        """Run comprehensive end-to-end tests"""
        print("=== Comprehensive E2E Test ===")
        
        test_cases = [
            {
                'message': 'I absolutely love this chatbot! It is amazing and so helpful!',
                'expected_sentiment': 'POSITIVE'
            },
            {
                'message': 'This is the worst experience ever. I hate everything about it.',
                'expected_sentiment': 'NEGATIVE'
            },
            {
                'message': 'The documentation is available on the website.',
                'expected_sentiment': 'NEUTRAL'
            },
            {
                'message': 'I like some features but dislike others. Very mixed feelings here.',
                'expected_sentiment': 'MIXED'
            }
        ]
        
        results = []
        
        for i, test_case in enumerate(test_cases):
            print(f"\n--- Test Case {i+1} ---")
            result = self.test_complete_workflow(test_case['message'])
            
            if result['success']:
                # Check if sentiment matches expectation
                expected = test_case['expected_sentiment']
                actual = result['sentiment']
                sentiment_correct = actual == expected
                
                result['expected_sentiment'] = expected
                result['sentiment_correct'] = sentiment_correct
                
                if sentiment_correct:
                    print(f"✅ Sentiment prediction correct: {actual}")
                else:
                    print(f"⚠️  Sentiment prediction: expected {expected}, got {actual}")
            
            results.append(result)
        
        # Summary
        successful_tests = sum(1 for r in results if r['success'])
        correct_sentiments = sum(1 for r in results if r.get('sentiment_correct', False))
        
        print(f"\n=== E2E Test Summary ===")
        print(f"Successful workflows: {successful_tests}/{len(test_cases)}")
        print(f"Correct sentiment predictions: {correct_sentiments}/{successful_tests}")
        
        return {
            'total_tests': len(test_cases),
            'successful_workflows': successful_tests,
            'correct_sentiments': correct_sentiments,
            'success_rate': successful_tests / len(test_cases),
            'accuracy_rate': correct_sentiments / successful_tests if successful_tests > 0 else 0,
            'detailed_results': results
        }

def main():
    """Run E2E tests"""
    # Replace with your actual load balancer URL
    api_url = "http://your-load-balancer-url"  # Update this!
    
    tester = E2EWorkflowTester(api_url)
    
    # Test individual workflow
    print("=== Individual Workflow Test ===")
    individual_result = tester.test_complete_workflow("I'm so excited about this new AI assistant!")
    
    if individual_result['success']:
        print("✅ Individual workflow test passed!")
    else:
        print(f"❌ Individual workflow test failed: {individual_result.get('error')}")
        if 'lambda_logs' in individual_result:
            print("Recent Lambda logs:")
            for log in individual_result['lambda_logs']:
                print(f"  {log}")
    
    # Run comprehensive tests
    comprehensive_results = tester.run_comprehensive_test()
    
    if comprehensive_results['success_rate'] > 0.8:
        print("✅ Comprehensive tests mostly successful!")
    else:
        print("⚠️  Some comprehensive tests failed - check individual results")

if __name__ == "__main__":
    main()