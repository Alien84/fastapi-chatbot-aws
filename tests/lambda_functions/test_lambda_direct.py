import boto3
import json

def find_lambda_function(base_name: str, region: str = 'eu-west-2'):
    """Find Lambda function with base name"""
    lambda_client = boto3.client('lambda', region_name=region)
    
    try:
        # List all functions
        response = lambda_client.list_functions()
        
        # Find function that starts with our base name
        for function in response['Functions']:
            if function['FunctionName'].startswith(base_name):
                return function['FunctionName']
        
        return None
    except Exception as e:
        print(f"Error listing functions: {e}")
        return None

def test_message_processor_direct():
    """Test Lambda function with direct invocation"""
    region = 'eu-west-2'  # Your actual region
    base_function_name = 'message-processor-lambda'
    
    # Find the actual function name
    actual_function_name = find_lambda_function(base_function_name, region)
    
    if not actual_function_name:
        print(f"❌ No Lambda function found starting with: {base_function_name}")
        print("Available functions:")
        
        # List available functions for debugging
        lambda_client = boto3.client('lambda', region_name=region)
        try:
            response = lambda_client.list_functions()
            for func in response['Functions']:
                print(f"  - {func['FunctionName']}")
        except Exception as e:
            print(f"Error listing functions: {e}")
        return
    
    print(f"Found Lambda function: {actual_function_name}")
    
    lambda_client = boto3.client('lambda', region_name=region)
    
    # Test payload
    test_payload = {
        'message_id': 999,
        'content': 'I am really happy about this new feature! It works great!'
    }
    
    print("Testing Lambda function with payload:")
    print(json.dumps(test_payload, indent=2))
    
    try:
        response = lambda_client.invoke(
            FunctionName=actual_function_name,
            InvocationType='RequestResponse',
            Payload=json.dumps(test_payload)
        )
        
        result = json.loads(response['Payload'].read())
        print("\nLambda Response:")
        print(json.dumps(result, indent=2))
        
        if response['StatusCode'] == 200:
            print("\n✅ Lambda function executed successfully!")
            
            # Check if response indicates success
            if 'body' in result:
                body = json.loads(result['body'])
                if 'message' in body:
                    print(f"Lambda message: {body['message']}")
                if 'sentiment' in body:
                    print(f"Sentiment analysis: {body['sentiment']}")
        else:
            print(f"\n❌ Lambda function failed with status: {response['StatusCode']}")
            
    except Exception as e:
        print(f"\n❌ Error invoking Lambda: {e}")

if __name__ == "__main__":
    test_message_processor_direct()