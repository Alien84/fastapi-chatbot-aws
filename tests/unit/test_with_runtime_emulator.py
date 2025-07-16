import requests
import json
import subprocess
import time
import threading

class TestLambdaWithRuntimeEmulator:
    
    @classmethod
    def setup_class(cls):
        """Start Lambda Runtime Interface Emulator"""
        # Build Lambda container
        subprocess.run([
            "docker", "build", "-t", "message-processor", 
            "../../lambda_functions/message_processor"
        ])
        
        # Start Lambda container
        cls.lambda_process = subprocess.Popen([
            "docker", "run", "--rm", "-p", "9000:8080",
            "message-processor"
        ])
        
        # Wait for Lambda to be ready
        time.sleep(5)
    
    @classmethod
    def teardown_class(cls):
        """Stop Lambda container"""
        cls.lambda_process.terminate()
    
    def test_lambda_invocation(self):
        """Test Lambda function via HTTP interface"""
        
        # Test payload
        payload = {
            'message_id': 123,
            'content': 'This is a test message for sentiment analysis'
        }
        
        # Invoke Lambda function
        response = requests.post(
            'http://localhost:9000/2015-03-31/functions/function/invocations',
            json=payload,
            timeout=30
        )
        
        # Verify response
        assert response.status_code == 200
        result = response.json()
        assert result['statusCode'] == 200
        
        response_body = json.loads(result['body'])
        assert 'Successfully processed message' in response_body['message']