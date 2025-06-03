from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
import time
import logging
import boto3
import json
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_secret(secret_name):
    """Retrieve secrets from AWS Secrets Manager"""
    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=os.environ.get('AWS_REGION', 'eu-west-2')
        )
        
        response = client.get_secret_value(SecretId=secret_name)
        secret = json.loads(response['SecretString'])
        return secret
    except ClientError as e:
        logger.error(f"Error retrieving secret {secret_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving secret: {e}")
        return None

def get_database_config():
    """Get database configuration from environment or secrets manager"""
    # Try to get from environment first (for local development)
    if all([
        os.getenv("DB_HOST"),
        os.getenv("DB_USERNAME"),
        os.getenv("DB_PASSWORD")
    ]):
        return {
            "host": os.getenv("DB_HOST"),
            "port": os.getenv("DB_PORT", "5432"),
            "dbname": os.getenv("DB_NAME", "chatbot"),
            "username": os.getenv("DB_USERNAME"),
            "password": os.getenv("DB_PASSWORD")
        }
    
    # Try to get from secrets manager (for production)
    secret_name = os.getenv("DB_SECRET_NAME")
    if secret_name:
        secrets = get_secret(secret_name)
        if secrets:
            return secrets
    
    raise Exception("Database configuration not found")

# Get database configuration
try:
    db_config = get_database_config()
    DATABASE_URL = f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
    logger.info("Database configuration loaded successfully")
except Exception as e:
    logger.error(f"Failed to load database configuration: {e}")
    raise

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
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

# Create FastAPI app
app = FastAPI(
    title="Chatbot API",
    description="A containerized FastAPI chatbot application",
    version="1.0.0"
)

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
    return {"status": "online", "message": "Welcome to the Containerized Chatbot API"}

@app.get("/health")
def health_check():
    """Health check endpoint for container orchestration"""
    try:
        # Test database connection
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

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