import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import your lambda function (assuming you structure it as a module)
import sys
import os
sys.path.append('../../lambda_functions/message_processor')
from lambda_function import analyze_sentiment, update_message_analysis, lambda_handler

class TestMessageProcessor:
    
    def test_analyze_sentiment_success(self):
        """Test sentiment analysis with mocked Comprehend"""
        with patch('boto3.client') as mock_boto:
            # Mock Comprehend response
            mock_comprehend = Mock()
            mock_comprehend.detect_sentiment.return_value = {
                'Sentiment': 'POSITIVE',
                'SentimentScore': {
                    'Positive': 0.9988,
                    'Negative': 0.0001,
                    'Neutral': 0.0010,
                    'Mixed': 0.0001
                }
            }
            mock_boto.return_value = mock_comprehend
            
            # Test the function
            result = analyze_sentiment("I love this!")
            
            # Assertions
            assert result['sentiment'] == 'POSITIVE'
            assert result['confidence'] == 0.9988
            mock_comprehend.detect_sentiment.assert_called_once_with(
                Text="I love this!",
                LanguageCode='en'
            )
    
    def test_analyze_sentiment_error_handling(self):
        """Test sentiment analysis error handling"""
        with patch('boto3.client') as mock_boto:
            # Mock Comprehend error
            mock_comprehend = Mock()
            mock_comprehend.detect_sentiment.side_effect = Exception("API Error")
            mock_boto.return_value = mock_comprehend
            
            # Test the function
            result = analyze_sentiment("Test message")
            
            # Should return neutral sentiment on error
            assert result['sentiment'] == 'NEUTRAL'
            assert result['confidence'] == 0.5
    
    def test_update_message_analysis(self):
        """Test database update function"""
        with patch('psycopg2.connect') as mock_connect:
            # Mock database connection and cursor
            mock_conn = Mock()
            mock_cursor = Mock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn
            
            # Test data
            db_config = {
                'host': 'localhost',
                'port': '5432',
                'dbname': 'test',
                'username': 'user',
                'password': 'pass'
            }
            sentiment_data = {'sentiment': 'POSITIVE', 'confidence': 0.95}
            
            # Call function
            update_message_analysis(123, sentiment_data, db_config)
            
            # Verify database operations
            mock_connect.assert_called_once_with(
                host='localhost',
                port='5432',
                database='test',
                user='user',
                password='pass'
            )
            assert mock_cursor.execute.call_count == 2  # ALTER and UPDATE
            mock_conn.commit.assert_called_once()
    
    @patch('lambda_function.get_ssm_parameters')
    @patch('lambda_function.analyze_sentiment')
    @patch('lambda_function.update_message_analysis')
    def test_lambda_handler_success(self, mock_update, mock_analyze, mock_ssm):
        """Test the main lambda handler"""
        # Mock dependencies
        mock_ssm.return_value = {'host': 'localhost', 'username': 'user', 'password': 'pass'}
        mock_analyze.return_value = {'sentiment': 'POSITIVE', 'confidence': 0.9}
        mock_update.return_value = None
        
        # Test event
        event = {
            'message_id': 123,
            'content': 'I love this chatbot!'
        }
        
        # Mock environment variable
        with patch.dict(os.environ, {'DB_SSM_PREFIX': '/test/db'}):
            result = lambda_handler(event, None)
        
        # Assertions
        assert result['statusCode'] == 200
        response_body = json.loads(result['body'])
        assert 'Successfully processed message 123' in response_body['message']
        assert response_body['sentiment']['sentiment'] == 'POSITIVE'

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])