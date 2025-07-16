import subprocess
import json
import os

def get_pulumi_outputs(stack_name='dev'):
    """Get Pulumi stack outputs"""
    try:
        # Change to infrastructure directory
        original_dir = os.getcwd()
        os.chdir('/Users/aliakbari/Documents/fastapi-chatbot-aws/infrastructure')
        
        # Get Pulumi outputs
        result = subprocess.run(
            ['pulumi', 'stack', 'output', '--json'],
            capture_output=True,
            text=True,
            check=True
        )
        
        outputs = json.loads(result.stdout)
        
        # Change back to original directory
        os.chdir(original_dir)
        
        return outputs
    
    except subprocess.CalledProcessError as e:
        print(f"Error getting Pulumi outputs: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {}

def main():
    """Print available Pulumi outputs"""
    outputs = get_pulumi_outputs()
    
    print("Available Pulumi outputs:")
    for key, value in outputs.items():
        print(f"  {key}: {value}")
    
    # Extract Lambda function name if available
    lambda_name = outputs.get('lambda_function_name')
    if lambda_name:
        print(f"\nLambda function name: {lambda_name}")
        print(f"Export command: export LAMBDA_FUNCTION_NAME={lambda_name}")
    else:
        print("\n❌ Lambda function name not found in outputs")
        print("Make sure you've exported it in your Pulumi code")

if __name__ == "__main__":
    main()