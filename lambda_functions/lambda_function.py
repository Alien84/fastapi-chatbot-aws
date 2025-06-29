import json
import boto3
import psycopg2
from datetime import datetime
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def test_aws_services():
    """Test AWS service access step by step"""
    results = {}
    
    # Test 1: Basic boto3 functionality
    try:
        session = boto3.session.Session()
        results['boto3_session'] = "✅ Success"
        logger.info("✅ boto3 session created successfully")
    except Exception as e:
        results['boto3_session'] = f"❌ Failed: {e}"
        logger.error(f"❌ boto3 session failed: {e}")
        return results
    
    # Test 2: AWS credentials and region
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        results['aws_identity'] = f"✅ Account: {identity.get('Account')}"
        logger.info(f"✅ AWS Identity: {identity}")
    except Exception as e:
        results['aws_identity'] = f"❌ Failed: {e}"
        logger.error(f"❌ AWS identity check failed: {e}")
    
    # Test 3: Comprehend service availability
    try:
        comprehend = boto3.client('comprehend')
        results['comprehend_client'] = "✅ Client created"
        logger.info("✅ Comprehend client created successfully")
        
        # Test if we can list available languages (simple API call)
        try:
            # This is a simple API call to test service access
            response = comprehend.describe_dominant_language_detection_job(JobId='test-job-that-does-not-exist')
        except comprehend.exceptions.JobNotFoundException:
            results['comprehend_access'] = "✅ Service accessible (expected JobNotFound)"
            logger.info("✅ Comprehend service is accessible")
        except Exception as e:
            results['comprehend_access'] = f"⚠️  Service access issue: {e}"
            logger.warning(f"⚠️  Comprehend access issue: {e}")
            
    except Exception as e:
        results['comprehend_client'] = f"❌ Failed: {e}"
        logger.error(f"❌ Comprehend client creation failed: {e}")
    
    return results

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

def analyze_sentiment_with_debug(message_content):
    """Analyze sentiment with detailed debugging"""
    logger.info(f"🔍 Starting sentiment analysis for: '{message_content[:50]}...'")
    
    try:
        # Step 1: Create Comprehend client
        logger.info("📝 Step 1: Creating Comprehend client...")
        comprehend = boto3.client('comprehend', region_name='eu-west-2')  # Explicit region
        logger.info("✅ Comprehend client created successfully")
        
        # Step 2: Validate input
        logger.info(f"📝 Step 2: Validating input (length: {len(message_content)} chars)")
        if not message_content or len(message_content.strip()) == 0:
            raise ValueError("Message content is empty")
        if len(message_content) > 5000:
            logger.warning("⚠️  Message is quite long, truncating to 5000 chars")
            message_content = message_content[:5000]
        
        # Step 3: Call Comprehend API
        logger.info("📝 Step 3: Calling Comprehend detect_sentiment API...")
        response = comprehend.detect_sentiment(
            Text=message_content,
            LanguageCode='en'
        )
        logger.info(f"✅ Comprehend API call successful: {response}")
        
        # Step 4: Process response
        sentiment_result = {
            'sentiment': response['Sentiment'],
            'confidence': max(response['SentimentScore'].values()),
            'all_scores': response['SentimentScore']
        }
        
        logger.info(f"✅ Sentiment analysis complete: {sentiment_result}")
        return sentiment_result
        
    except Exception as e:
        logger.error(f"❌ Sentiment analysis failed at some step: {str(e)}")
        logger.error(f"❌ Exception type: {type(e).__name__}")
        
        # Return detailed error info
        return {
            'sentiment': 'ERROR',
            'confidence': 0.0,
            'error': str(e),
            'error_type': type(e).__name__
        }

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
    """Enhanced debugging Lambda handler"""
    try:
        logger.info("🚀 Lambda function started")
        logger.info(f"📥 Received event: {json.dumps(event)}")
        logger.info(f"🌍 AWS Region: {os.environ.get('AWS_REGION', 'Not set')}")
        logger.info(f"🔧 Environment variables: {dict(os.environ)}")
        
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
        
        # Test sentiment analysis with debugging
        logger.info("🔍 Starting sentiment analysis...")
        sentiment_data = analyze_sentiment_with_debug(message_content)
        # sentiment_data = analyze_sentiment(message_content)
        
        # Prepare response
        response_data = {
            'message': f'Processing complete for message {message_id}',
            'sentiment_analysis': sentiment_data,
            'service_tests': service_tests,
            'test_mode': True,
            'lambda_info': {
                'region': os.environ.get('AWS_REGION'),
                'function_name': context.function_name if context else 'unknown',
                'request_id': context.aws_request_id if context else 'unknown'
            }
        }
        
        logger.info(f"✅ Lambda execution successful")

        # Update database
        update_message_analysis(message_id, sentiment_data, db_config)

        return {
            'statusCode': 200,
            'body': json.dumps(response_data, default=str)
        }
        
    except Exception as e:
        logger.error(f"💥 Lambda execution failed: {str(e)}")
        logger.error(f"💥 Exception type: {type(e).__name__}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'error_type': type(e).__name__,
                'test_mode': True
            })
        }