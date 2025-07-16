import pytest
import psycopg2
import docker
import time
import os
from unittest.mock import patch
import sys
sys.path.append('../../lambda_functions/message_processor')
from lambda_function import lambda_handler

class TestMessageProcessorIntegration:
    
    @classmethod
    def setup_class(cls):
        """Set up test database container"""
        cls.client = docker.from_env()
        
        # Start PostgreSQL container
        cls.db_container = cls.client.containers.run(
            "postgres:14",
            environment={
                "POSTGRES_DB": "testdb",
                "POSTGRES_USER": "testuser",
                "POSTGRES_PASSWORD": "testpass"
            },
            ports={'5432/tcp': 5433},  # Use different port to avoid conflicts
            detach=True,
            remove=True
        )
        
        # Wait for database to be ready
        time.sleep(10)
        
        # Create test table
        cls.setup_test_table()
    
    @classmethod
    def teardown_class(cls):
        """Clean up test database container"""
        cls.db_container.stop()
    
    @classmethod
    def setup_test_table(cls):
        """Create test table structure"""
        conn = psycopg2.connect(
            host='localhost',
            port=5433,
            database='testdb',
            user='testuser',
            password='testpass'
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE chatbot_messages (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        # Insert test message
        cursor.execute("""
            INSERT INTO chatbot_messages (id, content, response) 
            VALUES (1, 'Original message', 'Original response');
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
    
    @patch('lambda_function.get_ssm_parameters')
    @patch('lambda_function.analyze_sentiment')
    def test_full_integration(self, mock_analyze, mock_ssm):
        """Test full integration with real database"""
        # Mock SSM to return test database config
        mock_ssm.return_value = {
            'host': 'localhost',
            'port': '5433',
            'dbname': 'testdb',
            'username': 'testuser',
            'password': 'testpass'
        }
        
        # Mock sentiment analysis
        mock_analyze.return_value = {
            'sentiment': 'POSITIVE',
            'confidence': 0.85
        }
        
        # Test event
        event = {
            'message_id': 1,
            'content': 'I love this chatbot!'
        }
        
        # Execute lambda
        with patch.dict(os.environ, {'DB_SSM_PREFIX': '/test/db'}):
            result = lambda_handler(event, None)
        
        # Verify response
        assert result['statusCode'] == 200
        
        # Verify database was updated
        conn = psycopg2.connect(
            host='localhost',
            port=5433,
            database='testdb',
            user='testuser',
            password='testpass'
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT sentiment, sentiment_confidence FROM chatbot_messages WHERE id = 1")
        result = cursor.fetchone()
        
        assert result[0] == 'POSITIVE'
        assert result[1] == 0.85
        
        cursor.close()
        conn.close()

# Run with Docker available
if __name__ == "__main__":
    pytest.main([__file__, "-v"])