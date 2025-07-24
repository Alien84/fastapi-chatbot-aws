import pytest
import requests
import time
import boto3
import json
from moto import mock_cloudwatch, mock_logs
from unittest.mock import patch, MagicMock

class TestObservability:
    
    @classmethod
    def setup_class(cls):
        cls.api_base_url = "http://localhost:8002"
        cls.cloudwatch = boto3.client('cloudwatch', region_name='us-west-2')
        cls.logs_client = boto3.client('logs', region_name='us-west-2')
    
    def test_health_check_endpoint(self):
        """Test health check endpoint provides useful information"""
        response = requests.get(f"{self.api_base_url}/health", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        
        # Health check should provide essential status information
        required_fields = ['status', 'database', 'timestamp']
        for field in required_fields:
            assert field in data, f"Health check missing {field}"
        
        assert data['status'] in ['healthy', 'unhealthy']
        assert data['database'] in ['connected', 'disconnected']
        
        print("✅ Health check endpoint provides comprehensive status")
    
    def test_application_logging(self):
        """Test application logging functionality"""
        # Send requests that should generate logs
        test_scenarios = [
            {"content": "Normal message"},  # Should log successful request
            {"content": ""},  # Should log validation error
            {"invalid": "data"}  # Should log bad request
        ]
        
        for scenario in test_scenarios:
            try:
                requests.post(
                    f"{self.api_base_url}/chat",
                    json=scenario,
                    timeout=10
                )
            except:
                pass  # We expect some to fail
        
        # In a real environment, you would check actual log aggregation
        # This is a simplified test
        print("✅ Application logging test completed")
    
    @mock_cloudwatch
    def test_custom_metrics_creation(self):
        """Test custom metrics creation (if implemented)"""
        # Mock CloudWatch metrics
        with patch('boto3.client') as mock_boto:
            mock_cw = MagicMock()
            mock_boto.return_value = mock_cw
            
            # Simulate metrics that should be created
            expected_metrics = [
                {
                    'MetricName': 'MessageCount',
                    'Namespace': 'Chatbot/Application',
                    'Value': 1.0,
                    'Unit': 'Count'
                },
                {
                    'MetricName': 'ResponseTime',
                    'Namespace': 'Chatbot/Application',
                    'Value': 0.150,
                    'Unit': 'Seconds'
                }
            ]
            
            # Send a request that should generate metrics
            requests.post(
                f"{self.api_base_url}/chat",
                json={"content": "Metrics test message"},
                timeout=10
            )
            
            # In a real implementation, verify put_metric_data was called
            # This is a placeholder for actual metrics testing
            print("✅ Custom metrics creation test framework ready")
    
    def test_error_tracking(self):
        """Test error tracking and reporting"""
        # Generate different types of errors
        error_scenarios = [
            ("/nonexistent", 404),
            ("/chat", 422),  # Invalid payload
        ]
        
        for endpoint, expected_status in error_scenarios:
            if endpoint == "/chat":
                response = requests.post(
                    f"{self.api_base_url}{endpoint}",
                    json={"invalid": "payload"},
                    timeout=10
                )
            else:
                response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10)
            
            assert response.status_code == expected_status
            
            # In production, you would verify error tracking service integration
            # (e.g., Sentry, CloudWatch Insights, etc.)
        
        print("✅ Error tracking scenarios tested")
    
    def test_performance_monitoring(self):
        """Test performance monitoring capabilities"""
        # Send requests and measure response times
        response_times = []
        
        for i in range(10):
            start_time = time.time()
            
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"content": f"Performance test {i}"},
                timeout=10
            )
            
            end_time = time.time()
            response_time = end_time - start_time
            
            assert response.status_code == 200
            response_times.append(response_time)
        
        # Basic performance assertions
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        assert avg_response_time < 1.0, f"Average response time too high: {avg_response_time:.3f}s"
        assert max_response_time < 2.0, f"Max response time too high: {max_response_time:.3f}s"
        
        print(f"✅ Performance monitoring: avg={avg_response_time:.3f}s, max={max_response_time:.3f}s")
    
    def test_database_monitoring(self):
        """Test database monitoring and connection health"""
        # Test database health through health endpoint
        response = requests.get(f"{self.api_base_url}/health", timeout=10)
        
        assert response.status_code == 200
        data = response.json()
        assert data['database'] == 'connected'
        
        # Generate database load and monitor
        for i in range(20):
            requests.post(
                f"{self.api_base_url}/chat",
                json={"content": f"DB monitoring test {i}"},
                timeout=10
            )
        
        # Verify database is still healthy after load
        response = requests.get(f"{self.api_base_url}/health", timeout=10)
        assert response.status_code == 200
        assert response.json()['database'] == 'connected'
        
        print("✅ Database monitoring test completed")
    
    def test_alerting_thresholds(self):
        """Test alerting threshold scenarios"""
        # Test scenarios that might trigger alerts
        scenarios = [
            {
                'name': 'High Error Rate',
                'action': lambda: [requests.post(f"{self.api_base_url}/chat", json={}) for _ in range(5)]
            },
            {
                'name': 'High Response Time',
                'action': lambda: [requests.get(f"{self.api_base_url}/history?limit=100") for _ in range(3)]
            }
        ]
        
        for scenario in scenarios:
            print(f"Testing alerting scenario: {scenario['name']}")
            
            try:
                scenario['action']()
            except:
                pass  # Some scenarios are expected to fail
            
            # In production, you would verify alert conditions and notifications
            time.sleep(1)  # Brief pause between scenarios
        
        print("✅ Alerting threshold scenarios tested")