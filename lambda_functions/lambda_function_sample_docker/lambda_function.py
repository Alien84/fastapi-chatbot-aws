
import json
import psycopg2
import boto3

def lambda_handler(event, context):
    # Test that packages are imported correctly
    print("psycopg2 version:", psycopg2.__version__)
    print("boto3 available:", bool(boto3))
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Packages loaded successfully!',
            'psycopg2_version': psycopg2.__version__
        })
    }