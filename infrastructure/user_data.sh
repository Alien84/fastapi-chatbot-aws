#!/bin/bash

# Configure AWS CLI to use IMDSv2
mkdir -p ~/.aws
cat << EOF > ~/.aws/config
[default]
imds_version = v2
EOF

# Extensive logging
exec > >(tee /var/log/user-data-script.log 2>&1)

# Exit immediately if a command exits with a non-zero status
set -e

# Run as root (not needed if this script is run by EC2 as user_data)
#yum update -y is enough, no need for sudo in user_data
yum update -y

# Enable and install NGINX from amazon-linux-extras
amazon-linux-extras enable nginx1
yum clean metadata
yum install -y nginx

# Install AWS CLI and other dependencies
yum install -y python3 python3-pip git awscli amazon-cloudwatch-agent # postgresql

# Add PostgreSQL repository that's compatible with Amazon Linux 2
amazon-linux-extras enable postgresql14
yum install -y postgresql postgresql-devel

# Install application dependencies
pip3 install --upgrade pip
pip3 install fastapi uvicorn gunicorn psycopg2-binary sqlalchemy boto3
# Install psycopg2 for PostgreSQL
pip3 install psycopg2-binary sqlalchemy

# Create application directory
mkdir -p /opt/chatbot
mkdir -p /opt/chatbot/logs

# Create a script to fetch database credentials
cat <<EOF > /opt/chatbot/get_secrets.py
import boto3
import os
import sys

def get_parameters(path_prefix):
    try:
        # Debug messages to stderr
        print(f"Attempting to fetch parameters from path: {path_prefix}", file=sys.stderr)
        
        # Create an SSM client
        session = boto3.session.Session(region_name='eu-west-2')  # Use your region
        ssm = session.client(service_name='ssm')
        
        # Get all parameters under the specified path
        print(f"Fetching parameters by path: {path_prefix}", file=sys.stderr)
        # response = ssm.get_parameters_by_path(
        #     Path=path_prefix,
        #     WithDecryption=True,
        #     Recursive=True
        # )
        
        # parameters = {}
        # for param in response.get('Parameters', []):
        #     param_name = param['Name'].split('/')[-1]
        #     parameters[param_name] = param['Value']

        paginator = ssm.get_paginator('get_parameters_by_path')
        parameters = {}

        for page in paginator.paginate(Path=path_prefix, WithDecryption=True, Recursive=True):
            for param in page['Parameters']:
                param_name = param['Name'].split('/')[-1]
                parameters[param_name] = param['Value']

        print(f"Fetched parameters: {parameters}", file=sys.stderr)   
        return parameters
    
    except Exception as e:
        print(f"Error fetching parameters: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return {}

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python get_secrets.py <parameter_path>", file=sys.stderr)
        sys.exit(1)
    
    path_prefix = sys.argv[1]
    print(f"Starting script with path: {path_prefix}", file=sys.stderr)
    params = get_parameters(path_prefix)
    
    if not params:
        print("No parameters found or error occurred.", file=sys.stderr)
        # Set fallback values for local testing
        print("DB_USERNAME=dbadmin")
        print("DB_PASSWORD=local_test_only")
        print("DB_HOST=localhost")
        print("DB_PORT=5432")
        print("DB_DBNAME=chatbot")
        sys.exit(1)
    
    # Output environment variables
    for key, value in params.items():
        print(f"DB_{key.upper()}={value}")
EOF

# Set execute permissions
chmod +x /opt/chatbot/get_secrets.py

# Create a script to set up environment variables
cat << 'EOF' > /opt/chatbot/setup_env.sh
#!/bin/bash

# Get database credentials from SSM Parameter Store
python3 /opt/chatbot/get_secrets.py ${DB_PARAM_PATH} > /tmp/db_env.sh 2> /opt/chatbot/logs/ssm_fetch.log
sudo mv /tmp/db_env.sh /etc/profile.d/db_env.sh

sudo chmod +x /etc/profile.d/db_env.sh

# Verify the environment file was created
if [ -f /etc/profile.d/db_env.sh ]; then
    echo "Environment file created successfully" >> /opt/chatbot/logs/ssm_fetch.log
    cat /etc/profile.d/db_env.sh >> /opt/chatbot/logs/ssm_fetch.log
else
    echo "ERROR: Environment file was not created!" >> /opt/chatbot/logs/ssm_fetch.log
fi

EOF

chmod +x /opt/chatbot/setup_env.sh
/opt/chatbot/setup_env.sh

cat << 'EOF' > /opt/chatbot/test_db.sh
#!/bin/bash

# Source environment variables if they exist
if [ -f /etc/profile.d/db_env.sh ]; then
    set -a  # Automatically export all variables
    source /etc/profile.d/db_env.sh
    set +a
fi

echo "Testing connection to: $DB_HOST:$DB_PORT/$DB_DBNAME as $DB_USERNAME" >> /opt/chatbot/logs/ssm_fetch.log

# Use PGPASSWORD to avoid password prompt
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USERNAME -d $DB_DBNAME -c "SELECT version();" 

if [ $? -eq 0 ]; then
    echo "Connection successful!" >> /opt/chatbot/logs/ssm_fetch.log
else
    echo "Connection failed!" >> /opt/chatbot/logs/ssm_fetch.log
    echo "Please check your database credentials and network settings." >> /opt/chatbot/logs/ssm_fetch.log
    exit 1
fi
EOF

chmod +x /opt/chatbot/test_db.sh
/opt/chatbot/test_db.sh

sudo cat <<EOF > /opt/chatbot/test_connection.py
import os
import psycopg2
import sys

# Get database credentials from environment variables
db_host = os.getenv("DB_HOST")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_DBNAME")
db_user = os.getenv("DB_USERNAME")
db_pass = os.getenv("DB_PASSWORD")

print(f"Testing connection to {db_user}@{db_host}:{db_port}/{db_name}", file=sys.stderr)

try:
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=db_user,
        password=db_pass
    )
    print("Connection successful!", file=sys.stderr)
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    print(f"Database version: {db_version[0]}", file=sys.stderr)
    conn.close()
except Exception as e:
    print(f"Error connecting to database: {e}", file=sys.stderr)
    sys.exit(1)
EOF

# Run the test script with the environment variables
chmod +x /opt/chatbot/test_connection.py
sudo bash -c "set -a && source /etc/profile.d/db_env.sh && set +a  && python3 /opt/chatbot/test_connection.py 2>> /opt/chatbot/logs/ssm_fetch.log"

# Add logging configuration to FastAPI app
cat << 'EOF' > /opt/chatbot/logging_config.py
import logging
import sys
from logging.handlers import RotatingFileHandler

def setup_logging():
    # Create logger
    logger = logging.getLogger("chatbot")
    logger.setLevel(logging.INFO)
    
    # Create file handler
    file_handler = RotatingFileHandler(
        "/opt/chatbot/app.log",
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set formatter
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
EOF
# Clone the application repository (in a real scenario)
# git clone https://github.com/your-username/fastapi-chatbot.git /opt/chatbot

# Copy application code
cat <<EOF > /opt/chatbot/main.py
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import time
from logging_config import setup_logging

# Setup logging
logger = setup_logging()

# Get database credentials from environment variables
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_DBNAME = os.getenv("DB_DBNAME")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")

DATABASE_URL = f"postgresql://{DB_USERNAME}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_DBNAME}"

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define database models
class MessageRecord(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    response = Column(Text)

# Create tables
Base.metadata.create_all(bind=engine)

# FastAPI models
class Message(BaseModel):
    content: str

class ChatResponse(BaseModel):
    response: str

app = FastAPI(title="Chatbot API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.4f}s")
    return response

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"status": "online", "message": "Welcome to the Chatbot API"}

@app.post("/chat", response_model=ChatResponse)
def chat(message: Message, db: Session = Depends(get_db)):
    logger.info(f"Chat request received with content: {message.content}")

    # Simple echo response for now
    response = f"You said: {message.content}"
    
    # Store message in database
    try:
        db_message = MessageRecord(content=message.content, response=response)
        db.add(db_message)
        db.commit()
        logger.info(f"Message saved to database with ID: {db_message.id}")
    except Exception as e:
        logger.error(f"Database error: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Database error")
    
    return ChatResponse(response=response)

@app.get("/history")
def get_history(db: Session = Depends(get_db)):
    logger.info("History endpoint accessed")
    try:
        messages = db.query(MessageRecord).all()
        logger.info(f"Retrieved {len(messages)} messages from database")
        return {"history": [{"content": msg.content, "response": msg.response} for msg in messages]}
    except Exception as e:
        logger.error(f"Database error when retrieving history: {str(e)}")
        raise HTTPException(status_code=500, detail="Database error")

@app.get("/health")
def health_check():
    logger.info("Health check endpoint accessed")
    return {"status": "healthy"}
EOF

# Setup CloudWatch agent configuration
cat << EOF > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
{
    "agent": {
        "metrics_collection_interval": 60,
        "run_as_user": "root"
    },
    "logs": {
        "logs_collected": {
            "files": {
                "collect_list": [
                    {
                        "file_path": "/var/log/messages",
                        "log_group_name": "/aws/ec2/chatbot",
                        "log_stream_name": "{instance_id}/syslog",
                        "retention_in_days": 30
                    },
                    {
                        "file_path": "/var/log/nginx/access.log",
                        "log_group_name": "/aws/ec2/chatbot",
                        "log_stream_name": "{instance_id}/nginx-access",
                        "retention_in_days": 30
                    },
                    {
                        "file_path": "/var/log/nginx/error.log",
                        "log_group_name": "/aws/ec2/chatbot",
                        "log_stream_name": "{instance_id}/nginx-error",
                        "retention_in_days": 30
                    }
                ]
            }
        }
    },
    "metrics": {
        "metrics_collected": {
            "cpu": {
                "measurement": [
                    "cpu_usage_idle",
                    "cpu_usage_iowait",
                    "cpu_usage_user",
                    "cpu_usage_system"
                ],
                "metrics_collection_interval": 60,
                "totalcpu": false
            },
            "mem": {
                "measurement": [
                    "mem_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "disk": {
                "measurement": [
                    "used_percent"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "/"
                ]
            },
            "diskio": {
                "measurement": [
                    "io_time",
                    "write_bytes",
                    "read_bytes",
                    "writes",
                    "reads"
                ],
                "metrics_collection_interval": 60,
                "resources": [
                    "*"
                ]
            },
            "swap": {
                "measurement": [
                    "swap_used_percent"
                ],
                "metrics_collection_interval": 60
            },
            "netstat": {
                "measurement": [
                    "tcp_established",
                    "tcp_time_wait"
                ],
                "metrics_collection_interval": 60
            },
            "processes": {
                "measurement": [
                    "running",
                    "sleeping",
                    "dead"
                ],
                "metrics_collection_interval": 60
            }
        }
    }
}
EOF


# Create a service file for systemd
cat <<EOF > /etc/systemd/system/chatbot.service
[Unit]
Description=Chatbot FastAPI application
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/opt/chatbot
EnvironmentFile=/etc/profile.d/db_env.sh
ExecStart=/usr/local/bin/gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app -b 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Set permissions
chown -R ec2-user:ec2-user /opt/chatbot

systemctl daemon-reload

# Start the CloudWatch agent
systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

# Start and enable FastAPI service
systemctl enable chatbot
systemctl start chatbot

# Configure Nginx
cat <<EOF > /etc/nginx/conf.d/chatbot.conf
server {
    listen 80;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

# Start Nginx
systemctl enable nginx
systemctl start nginx