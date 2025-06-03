#!/usr/bin/env python3

import boto3
import sys
import os
from sqlalchemy import create_engine

def get_ssm_parameters(parameter_prefix, region='us-west-2'):
    """Retrieve parameters from AWS Systems Manager Parameter Store"""
    try:
        ssm_client = boto3.client('ssm', region_name=region)
        
        response = ssm_client.get_parameters_by_path(
            Path=parameter_prefix,
            Recursive=True,
            WithDecryption=True
        )
        
        parameters = {}
        for param in response['Parameters']:
            key = param['Name'].replace(parameter_prefix, '').lstrip('/')
            parameters[key] = param['Value']
        
        return parameters
    except Exception as e:
        print(f"Error retrieving SSM parameters: {e}")
        return None

def test_database_connection(db_config):
    """Test database connection"""
    try:
        database_url = f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
        engine = create_engine(database_url)
        
        with engine.connect() as connection:
            result = connection.execute("SELECT 1")
            print("✓ Database connection successful")
            return True
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        return False

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_ssm_connection.py <stack_name>")
        sys.exit(1)
    
    stack_name = sys.argv[1]
    ssm_prefix = f"/{stack_name}/db"
    
    print(f"Testing SSM parameters for stack: {stack_name}")
    print(f"SSM prefix: {ssm_prefix}")
    
    # Get parameters from SSM
    db_config = get_ssm_parameters(ssm_prefix)
    
    if not db_config:
        print("✗ Failed to retrieve SSM parameters")
        sys.exit(1)
    
    print("✓ SSM parameters retrieved successfully")
    print(f"  - Host: {db_config.get('host', 'Not found')}")
    print(f"  - Port: {db_config.get('port', 'Not found')}")
    print(f"  - Database: {db_config.get('dbname', 'Not found')}")
    print(f"  - Username: {db_config.get('username', 'Not found')}")
    print(f"  - Password: {'***' if db_config.get('password') else 'Not found'}")
    
    # Test database connection
    if test_database_connection(db_config):
        print("✓ All tests passed!")
        sys.exit(0)
    else:
        print("✗ Database connection test failed")
        sys.exit(1)

if __name__ == "__main__":
    main()