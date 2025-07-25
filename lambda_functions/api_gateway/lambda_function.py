import json
import boto3
import psycopg2
from datetime import datetime
import os
import logging
from datetime import datetime, timedelta, timezone

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

def get_chatbot_statistics(db_config, days=7):
    """Get comprehensive chatbot usage statistics"""
    try:
        conn = psycopg2.connect(
            host=db_config['host'],
            port=db_config['port'],
            database=db_config['dbname'],
            user=db_config['username'],
            password=db_config['password']
        )
        
        cursor = conn.cursor()
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # 1. Total messages in period
        cursor.execute(
            "SELECT COUNT(*) FROM chatbot_messages WHERE created_at >= %s",
            (since_date,)
        )
        total_messages = cursor.fetchone()[0]
        
        # 2. Daily message counts for trend analysis
        cursor.execute("""
            SELECT DATE(created_at) as message_date, COUNT(*) as message_count
            FROM chatbot_messages 
            WHERE created_at >= %s 
            GROUP BY DATE(created_at) 
            ORDER BY DATE(created_at)
        """, (since_date,))
        daily_counts = cursor.fetchall()
        
        # 3. Average message length
        cursor.execute("""
            SELECT AVG(LENGTH(content)) 
            FROM chatbot_messages 
            WHERE created_at >= %s
        """, (since_date,))
        avg_length_result = cursor.fetchone()[0]
        avg_length = float(avg_length_result) if avg_length_result else 0.0
        
        # 4. Message length distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN LENGTH(content) < 50 THEN 'short'
                    WHEN LENGTH(content) < 200 THEN 'medium'
                    ELSE 'long'
                END as length_category,
                COUNT(*) as count
            FROM chatbot_messages 
            WHERE created_at >= %s
            GROUP BY length_category
        """, (since_date,))
        length_distribution = dict(cursor.fetchall())
        
        # 5. Sentiment distribution (if available)
        cursor.execute("""
            SELECT sentiment, COUNT(*) as count
            FROM chatbot_messages 
            WHERE created_at >= %s AND sentiment IS NOT NULL
            GROUP BY sentiment
        """, (since_date,))
        sentiment_distribution = dict(cursor.fetchall())
        
        # 6. Hourly activity pattern
        cursor.execute("""
            SELECT EXTRACT(HOUR FROM created_at) as hour, COUNT(*) as count
            FROM chatbot_messages 
            WHERE created_at >= %s
            GROUP BY EXTRACT(HOUR FROM created_at)
            ORDER BY hour
        """, (since_date,))
        hourly_activity = [{'hour': int(hour), 'count': count} for hour, count in cursor.fetchall()]
        
        # 7. Most common words (simple analysis)
        cursor.execute("""
            SELECT content
            FROM chatbot_messages 
            WHERE created_at >= %s
            LIMIT 1000
        """, (since_date,))
        
        # Simple word frequency analysis
        word_counts = {}
        for (content,) in cursor.fetchall():
            words = content.lower().split()
            for word in words:
                if len(word) > 3:  # Only count words longer than 3 characters
                    word_counts[word] = word_counts.get(word, 0) + 1
        
        # Get top 10 most common words
        top_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        cursor.close()
        conn.close()
        
        # Prepare response data
        return {
            'period_days': days,
            'period_start': (datetime.utcnow() - timedelta(days=days)).isoformat(),
            'period_end': datetime.utcnow().isoformat(),
            'total_messages': total_messages,
            'daily_counts': [
                {
                    'date': str(date), 
                    'count': count
                } for date, count in daily_counts
            ],
            'average_message_length': round(avg_length, 2),
            'message_length_distribution': length_distribution,
            'sentiment_distribution': sentiment_distribution,
            'hourly_activity': hourly_activity,
            'top_words': [{'word': word, 'count': count} for word, count in top_words],
            'messages_per_day_average': round(total_messages / max(days, 1), 2)
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise


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
        
        # Extract query parameters
        query_params = event.get('queryStringParameters') or {}
        days = int(query_params.get('days', '7'))
        
        # Validate parameters
        if days < 1 or days > 365:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': 'GET, OPTIONS',
                    'Access-Control-Allow-Headers': 'Content-Type'
                },
                'body': json.dumps({
                    'error': 'Invalid parameter',
                    'message': 'Days must be between 1 and 365',
                    'provided_days': days
                })
            }

        # Generating statistics
        # TODO: Uncomment the following line to update the message in the database
        """
        In current implementation, the Lambda function is not placed in a VPC.
        This means it can access AWS services like Comprehend and SSM without needing VPC endpoints or NAT gateways.
        However, if you need to access resources inside a VPC (like an RDS database), you would need to place the Lambda in a VPC.
        This is done by configuring the Lambda function to use a VPC and specifying the subnets and security groups.
        In AWS, placing a Lambda function in a private subnet is necessary when your function needs to access resources 
        that are only available inside your Virtual Private Cloud (VPC) and not publicly accessible.
        Then your Lambda must be placed in a VPC and configured to use a private subnet where those resources live.
        """
        logger.info(f"Generating statistics for {days} days")
        # stats = get_chatbot_statistics(db_config, days)
        # Hardcoded stats
        stats = {
            'period_days': days,
            'period_start': (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(),
            'period_end': datetime.now(timezone.utc).isoformat(),
            'total_messages': 10,
            'daily_counts': [
                {'date': (datetime.now(timezone.utc) - timedelta(days=i)).strftime('%Y-%m-%d'), 'count': 2} for i in range(days)
            ],
            'average_message_length': 5.5,
            'message_length_distribution': {
                'short': 3,
                'medium': 5,
                'long': 2
            },
            'sentiment_distribution': {
                'POSITIVE': 4,
                'NEGATIVE': 2,
                'NEUTRAL': 3,
                'MIXED': 1
            },
            'hourly_activity': [{'hour': i, 'count': 1} for i in range(24)],  # Simulated hourly activity
            'top_words': [{'word': word, 'count': count} for word, count in [('test', 5), ('message', 3), ('chatbot', 2)]],
            'messages_per_day_average': round(10 / max(days, 1), 2)
        }

        logger.info(f"✅ Lambda execution successful")

        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': json.dumps(stats, default=str)  # default=str handles datetime serialization
        }
        
    except ValueError as e:
        logger.error(f"Parameter validation error: {e}")
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Invalid parameter format'})
        }
        
    except Exception as e:
        logger.error(f"Lambda execution failed: {e}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Internal server error'})
        }