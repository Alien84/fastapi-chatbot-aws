import json
import boto3
import psycopg2
from datetime import datetime
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def get_ssm_parameters(parameter_prefix):
    """Get database credentials from SSM"""
    ssm = boto3.client('ssm')
    
    try:
        response = ssm.get_parameters_by_path(
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
        logger.error(f"Error getting SSM parameters: {e}")
        raise

def analyze_sentiment(message_content):
    """Analyze sentiment using AWS Comprehend"""
    comprehend = boto3.client('comprehend')
    
    try:
        response = comprehend.detect_sentiment(
            Text=message_content,
            LanguageCode='en'
        )
        return {
            'sentiment': response['Sentiment'],
            'confidence': max(response['SentimentScore'].values())
        }
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        return {'sentiment': 'NEUTRAL', 'confidence': 0.5}

def update_message_analysis(message_id, sentiment_data, db_config):
    """Update message with sentiment analysis results"""
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['dbname'],
            user=db_config['username'],
            password=db_config['password']
        )
        
        cursor = conn.cursor()
        
        # Add columns if they don't exist
        cursor.execute("""
            ALTER TABLE chatbot_messages 
            ADD COLUMN IF NOT EXISTS sentiment VARCHAR(20),
            ADD COLUMN IF NOT EXISTS sentiment_confidence FLOAT,
            ADD COLUMN IF NOT EXISTS analyzed_at TIMESTAMP;
        """)
        
        # Update the message
        cursor.execute("""
            UPDATE chatbot_messages 
            SET sentiment = %s, sentiment_confidence = %s, analyzed_at = %s
            WHERE id = %s
        """, (
            sentiment_data['sentiment'],
            sentiment_data['confidence'],
            datetime.utcnow(),
            message_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Updated message {message_id} with sentiment: {sentiment_data['sentiment']}")
        
    except Exception as e:
        logger.error(f"Error updating database: {e}")
        raise

def lambda_handler(event, context):
    """Main Lambda handler"""
    try:
        logger.info(f"Processing event: {json.dumps(event)}")
        
        # Handle different event sources
        if 'Records' in event:
            # SQS message
            for record in event['Records']:
                message_data = json.loads(record['body'])
        else:
            # Direct invocation
            message_data = event
        
        message_id = message_data['message_id']
        message_content = message_data['content']
        
        logger.info(f"Processing message {message_id}: '{message_content[:50]}...'")
        
        # Get database configuration
        ssm_prefix = os.environ['DB_SSM_PREFIX']
        db_config = get_ssm_parameters(ssm_prefix)
        
        # Analyze sentiment
        sentiment_data = analyze_sentiment(message_content)
        logger.info(f"Sentiment analysis result: {sentiment_data}")
        
        # Update database
        update_message_analysis(message_id, sentiment_data, db_config)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Successfully processed message {message_id}',
                'sentiment': sentiment_data
            })
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }