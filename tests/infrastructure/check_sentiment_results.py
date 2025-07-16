import boto3
import psycopg2
import json

def get_ssm_parameters(parameter_prefix, region='us-west-2'):
    """Get database credentials from SSM"""
    ssm = boto3.client('ssm', region_name=region)
    
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

def check_sentiment_analysis(stack_name):
    """Check recent messages with sentiment analysis"""
    
    # Get database config
    ssm_prefix = f"/{stack_name}/db"
    db_config = get_ssm_parameters(ssm_prefix)
    
    # Connect to database
    conn = psycopg2.connect(
        host=db_config['host'],
        port=db_config['port'],
        database=db_config['dbname'],
        user=db_config['username'],
        password=db_config['password']
    )
    
    cursor = conn.cursor()
    
    # Get recent messages with sentiment
    cursor.execute("""
        SELECT id, content, sentiment, sentiment_confidence, analyzed_at, created_at
        FROM chatbot_messages 
        WHERE sentiment IS NOT NULL
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    
    print("Recent messages with sentiment analysis:")
    print("-" * 80)
    
    for row in results:
        msg_id, content, sentiment, confidence, analyzed_at, created_at = row
        print(f"ID: {msg_id}")
        print(f"Content: {content[:60]}...")
        print(f"Sentiment: {sentiment} (confidence: {confidence:.2f})")
        print(f"Created: {created_at}")
        print(f"Analyzed: {analyzed_at}")
        print("-" * 80)
    
    cursor.close()
    conn.close()
    
    if results:
        print(f"\n✅ Found {len(results)} messages with sentiment analysis!")
    else:
        print("\n❌ No messages with sentiment analysis found.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python check_sentiment_results.py <stack_name>")
        sys.exit(1)
    
    stack_name = sys.argv[1]
    check_sentiment_analysis(stack_name)