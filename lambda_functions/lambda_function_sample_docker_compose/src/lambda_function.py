import json
import os
import psycopg2
import boto3

def lambda_handler(event, context):
    try:
        print("=== Testing psycopg2 Container Deployment ===")
        print(f"psycopg2 version: {psycopg2.__version__}")
        print(f"boto3 available: {bool(boto3)}")
        print(f"Environment: {os.environ.get('AWS_EXECUTION_ENV', 'local')}")
        
        # Test psycopg2 functionality
        print("psycopg2 module loaded successfully!")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Container built with Docker Compose works!',
                'psycopg2_version': psycopg2.__version__,
                'deployment_method': 'docker-compose',
                'event_received': event,
                'environment': os.environ.get('AWS_EXECUTION_ENV', 'local')
            }, indent=2)
        }
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(error_msg)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': error_msg,
                'message': 'Failed to import or use psycopg2'
            })
        }