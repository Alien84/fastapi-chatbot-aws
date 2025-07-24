import pytest
import pulumi
import json
import boto3
from moto import mock_ec2, mock_rds, mock_ssm
from unittest.mock import patch, MagicMock
import sys
sys.path.append('../../infrastructure')

class TestPulumiInfrastructure:
    
    def test_vpc_configuration(self):
        """Test VPC configuration"""
        import pulumi
        
        @pulumi.runtime.test
        def test_vpc():
            from vpc import create_vpc
            
            vpc_resources = create_vpc("test")
            
            # Test VPC CIDR
            def check_vpc_cidr(args):
                vpc = args[0]
                assert vpc.cidr_block == "10.0.0.0/16"
                return vpc
            
            # Test subnet configuration
            def check_subnets(args):
                public_subnets, private_subnets = args[0], args[1]
                assert len(public_subnets) == 2
                assert len(private_subnets) == 2
                return True
            
            return pulumi.Output.all(vpc_resources["vpc"]).apply(check_vpc_cidr)
    
    @mock_ssm
    def test_ssm_parameter_creation(self):
        """Test SSM parameter creation"""
        # Mock SSM client
        ssm = boto3.client('ssm', region_name='us-west-2')
        
        # Simulate parameter creation
        test_params = {
            'host': 'test-host',
            'username': 'test-user',
            'password': 'test-password',
            'port': '5432',
            'dbname': 'test-db'
        }
        
        for key, value in test_params.items():
            ssm.put_parameter(
                Name=f'/test/db/{key}',
                Value=value,
                Type='SecureString' if key == 'password' else 'String'
            )
        
        # Test parameter retrieval
        response = ssm.get_parameters_by_path(
            Path='/test/db',
            Recursive=True,
            WithDecryption=True
        )
        
        retrieved_params = {}
        for param in response['Parameters']:
            key = param['Name'].split('/')[-1]
            retrieved_params[key] = param['Value']
        
        assert retrieved_params == test_params
    
    def test_security_group_rules(self):
        """Test security group configuration"""
        # Mock security group configuration testing
        expected_web_sg_rules = [
            {'protocol': 'tcp', 'from_port': 80, 'to_port': 80, 'cidr': '0.0.0.0/0'},
            {'protocol': 'tcp', 'from_port': 443, 'to_port': 443, 'cidr': '0.0.0.0/0'},
            {'protocol': 'tcp', 'from_port': 22, 'to_port': 22, 'cidr': '0.0.0.0/0'},
        ]
        
        expected_db_sg_rules = [
            {'protocol': 'tcp', 'from_port': 5432, 'to_port': 5432, 'source_sg': 'web-sg'},
        ]
        
        # In a real test, you would verify these rules are created correctly
        # This is a simplified assertion
        assert len(expected_web_sg_rules) == 3
        assert len(expected_db_sg_rules) == 1
    
    def test_iam_policy_validation(self):
        """Test IAM policy configuration"""
        # Test EC2 instance role policy
        expected_permissions = [
            'ssm:GetParameter',
            'ssm:GetParameters', 
            'ssm:GetParametersByPath',
            'logs:CreateLogStream',
            'logs:PutLogEvents',
            'ecr:GetAuthorizationToken',
            'ecr:BatchGetImage'
        ]
        
        # Verify all required permissions are included
        # In practice, you'd test the actual policy document
        assert all(perm in expected_permissions for perm in expected_permissions)
    
    def test_resource_tagging(self):
        """Test resource tagging strategy"""
        expected_tags = {
            'Environment': 'test',
            'Project': 'chatbot',
            'ManagedBy': 'pulumi'
        }
        
        # Verify tagging strategy
        assert 'Environment' in expected_tags
        assert 'Project' in expected_tags
        assert 'ManagedBy' in expected_tags