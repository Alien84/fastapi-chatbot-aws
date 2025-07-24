import pytest
import requests
import time
import docker
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
sys.path.append('../../app')

class TestAPIIntegration:
    
    @classmethod
    def setup_class(cls):
        """Set up test environment"""
        cls.client = docker.from_env()
        
        # Start test database
        cls.db_container = cls.client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "test_api",
                "POSTGRES_USER": "test_user",
                "POSTGRES_PASSWORD": "test_password"
            },
            ports={'5432/tcp': 5436},
            detach=True,
            remove=True
        )
        
        time.sleep(10)
        
        # Mock environment variables
        cls.env_vars = {
            'DB_HOST': 'localhost',
            'DB_PORT': '5436',
            'DB_NAME': 'test_api',
            'DB_USERNAME': 'test_user',
            'DB_PASSWORD': 'test_password'
        }
    
    @classmethod
    def teardown_class(cls):
        """Clean up"""
        cls.db_container.stop()
    
    def test_api_startup_and_health(self):
        """Test API startup and health endpoint"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Test health endpoint
            response = client.get("/health")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            assert "timestamp" in data
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            response = client.get("/")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "online"
            assert "message" in data
    
    @patch('main.trigger_message_processing')
    def test_chat_endpoint_success(self, mock_trigger):
        """Test successful chat endpoint"""
        mock_trigger.return_value = True
        
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Test valid chat message
            response = client.post("/chat", json={"content": "Hello, chatbot!"})
            
            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "message_id" in data
            assert data["response"] == "You said: Hello, chatbot!"
            assert isinstance(data["message_id"], int)
            
            # Verify Lambda trigger was called
            mock_trigger.assert_called_once()
    
    def test_chat_endpoint_validation(self):
        """Test chat endpoint input validation"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Test empty content
            response = client.post("/chat", json={"content": ""})
            assert response.status_code == 422
            
            # Test missing content
            response = client.post("/chat", json={})
            assert response.status_code == 422
            
            # Test invalid JSON
            response = client.post("/chat", data="invalid json")
            assert response.status_code == 422
            
            # Test too long content
            long_content = "A" * 10000
            response = client.post("/chat", json={"content": long_content})
            assert response.status_code == 422
    
    def test_history_endpoint(self):
        """Test history endpoint with pagination"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Add some test messages first
            for i in range(15):
                client.post("/chat", json={"content": f"Test message {i}"})
            
            # Test default pagination
            response = client.get("/history")
            assert response.status_code == 200
            
            data = response.json()
            assert "history" in data
            assert "total_count" in data
            assert len(data["history"]) <= 50  # Default limit
            assert data["total_count"] == 15
            
            # Test custom pagination
            response = client.get("/history?limit=5&offset=5")
            assert response.status_code == 200
            
            data = response.json()
            assert len(data["history"]) == 5
            assert data["total_count"] == 15
    
    def test_history_endpoint_validation(self):
        """Test history endpoint validation"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Test invalid limit
            response = client.get("/history?limit=0")
            assert response.status_code == 400
            
            response = client.get("/history?limit=200")
            assert response.status_code == 400
            
            # Test invalid offset
            response = client.get("/history?offset=-1")
            assert response.status_code == 400
    
    def test_sentiment_endpoint(self):
        """Test sentiment endpoint"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Create a message first
            chat_response = client.post("/chat", json={"content": "I love this!"})
            message_id = chat_response.json()["message_id"]
            
            # Test sentiment endpoint
            response = client.get(f"/message/{message_id}/sentiment")
            assert response.status_code == 200
            
            data = response.json()
            assert data["message_id"] == message_id
            assert data["content"] == "I love this!"
            # sentiment and sentiment_confidence might be None initially
    
    def test_cleanup_endpoint(self):
        """Test cleanup endpoint"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Add some messages
            client.post("/chat", json={"content": "Test message 1"})
            client.post("/chat", json={"content": "Test message 2"})
            
            # Test cleanup
            response = client.delete("/history/cleanup?days=1")
            assert response.status_code == 200
            
            data = response.json()
            assert "deleted_count" in data
            assert "cutoff_date" in data
    
    def test_cors_headers(self):
        """Test CORS headers"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Test preflight request
            response = client.options("/chat")
            assert response.status_code == 200
            
            # Test actual request has CORS headers
            response = client.get("/")
            assert "access-control-allow-origin" in response.headers
    
    def test_error_handling(self):
        """Test error handling"""
        with patch.dict('os.environ', self.env_vars):
            from main import app
            
            client = TestClient(app)
            
            # Test 404 for non-existent endpoint
            response = client.get("/nonexistent")
            assert response.status_code == 404
            
            # Test 404 for non-existent message
            response = client.get("/message/99999/sentiment")
            assert response.status_code == 404