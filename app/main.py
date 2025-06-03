from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Text, text, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import os
import time
import logging
from datetime import datetime, timedelta
import boto3
from botocore.exceptions import ClientError
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_ssm_parameters(parameter_prefix):
    """Retrieve parameters from AWS Systems Manager Parameter Store"""
    try:
        session = boto3.session.Session()
        ssm_client = session.client(
            service_name='ssm',
            region_name=os.environ.get('AWS_REGION', 'us-west-2')
        )
        
        # Get all parameters with the given prefix
        paginator = ssm_client.get_paginator('get_parameters_by_path')
        parameters = {}
        
        for page in paginator.paginate(
            Path=parameter_prefix,
            Recursive=True,
            WithDecryption=True
        ):
            for param in page['Parameters']:
                # Extract the key name (remove the prefix)
                key = param['Name'].replace(parameter_prefix, '').lstrip('/')
                parameters[key] = param['Value']
        
        return parameters
    except ClientError as e:
        logger.error(f"Error retrieving SSM parameters {parameter_prefix}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error retrieving SSM parameters: {e}")
        return None

def get_database_config():
    """Get database configuration from environment or SSM Parameter Store"""
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
    
    # Try to get from SSM Parameter Store (for production)
    ssm_prefix = os.getenv("DB_SSM_PREFIX")
    if ssm_prefix:
        parameters = get_ssm_parameters(ssm_prefix)
        if parameters:
            required_params = ["host", "username", "password"]
            missing_params = [param for param in required_params if not parameters.get(param)]
            
            if missing_params:
                logger.error(f"Missing required database parameters: {missing_params}")
                return None
            
            return {
                "host": parameters.get("host"),
                "port": parameters.get("port", "5432"),
                "dbname": parameters.get("dbname", "chatbot"),
                "username": parameters.get("username"),
                "password": parameters.get("password")
            }
    
    logger.error("Database configuration not found in environment or SSM")
    return None

# Get database configuration
db_config = get_database_config()
if not db_config:
    logger.error("Failed to load database configuration")
    raise Exception("Database configuration not found")

DATABASE_URL = f"postgresql://{db_config['username']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
logger.info("Database configuration loaded successfully")

# SQLAlchemy setup with connection pooling
engine = create_engine(
    DATABASE_URL, 
    pool_pre_ping=True,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,  # Recycle connections after 1 hour
    connect_args={"connect_timeout": 10}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Define database models
class MessageRecord(Base):
    __tablename__ = "chatbot_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")
    raise

# FastAPI models with validation
class Message(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000, description="Message content")

class ChatResponse(BaseModel):
    response: str
    message_id: Optional[int] = None

class HistoryItem(BaseModel):
    id: int
    content: str
    response: str
    created_at: datetime

class HistoryResponse(BaseModel):
    history: List[HistoryItem]
    total_count: int

# Create FastAPI app
app = FastAPI(
    title="Chatbot API",
    description="A containerized FastAPI chatbot application",
    version="1.0.0"
)

# Configure CORS more securely - replace with actual allowed origins in production
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only allow needed methods
    allow_headers=["*"],
)

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        logger.info(f"{request.method} {request.url.path} - Status: {response.status_code} - Duration: {process_time:.4f}s")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"{request.method} {request.url.path} - Error: {str(e)} - Duration: {process_time:.4f}s")
        raise

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@app.get("/")
def read_root():
    logger.info("Root endpoint accessed")
    return {"status": "online", "message": "Welcome to the Containerized Chatbot API"}

@app.get("/health")
def health_check(request: Request):
    """Health check endpoint for container orchestration"""
    print(f"Health check called from: {request.client.host}:{request.client.port}")
    try:
        # Test database connection
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return {"status": "healthy", "database": "connected", "timestamp": datetime.utcnow()}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/chat", response_model=ChatResponse)
def chat(message: Message, db: Session = Depends(get_db)):
    logger.info(f"Chat request received with content length: {len(message.content)}")
    
    try:
        # Simple echo response for now - replace with actual chatbot logic
        response = f"You said: {message.content}"
        
        # Store message in database
        db_message = MessageRecord(content=message.content, response=response)
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        
        logger.info(f"Message saved to database with ID: {db_message.id}")
        return ChatResponse(response=response, message_id=db_message.id)
        
    except Exception as e:
        logger.error(f"Database error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")

@app.get("/history", response_model=HistoryResponse)
def get_history(
    limit: int = 50, 
    offset: int = 0, 
    db: Session = Depends(get_db)
):
    """Get chat history with pagination"""
    logger.info(f"History endpoint accessed with limit={limit}, offset={offset}")
    
    try:
        # Validate pagination parameters
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        if offset < 0:
            raise HTTPException(status_code=400, detail="Offset must be non-negative")
        
        # Get total count
        total_count = db.query(MessageRecord).count()
        
        # Get paginated messages ordered by creation date (newest first)
        messages = (
            db.query(MessageRecord)
            .order_by(MessageRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        history_items = [
            HistoryItem(
                id=msg.id,
                content=msg.content,
                response=msg.response,
                created_at=msg.created_at
            )
            for msg in messages
        ]
        
        logger.info(f"Retrieved {len(history_items)} messages from database (total: {total_count})")
        return HistoryResponse(history=history_items, total_count=total_count)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Database error when retrieving history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve chat history")

# Add a cleanup endpoint for maintenance
@app.delete("/history/cleanup")
def cleanup_old_messages(days: int = 30, db: Session = Depends(get_db)):
    """Delete messages older than specified days (admin endpoint)"""
    if days < 1:
        raise HTTPException(status_code=400, detail="Days must be positive")
    
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        deleted_count = (
            db.query(MessageRecord)
            .filter(MessageRecord.created_at < cutoff_date)
            .delete()
        )
        db.commit()
        
        logger.info(f"Cleaned up {deleted_count} messages older than {days} days")
        return {"deleted_count": deleted_count, "cutoff_date": cutoff_date}
        
    except Exception as e:
        logger.error(f"Error during cleanup: {str(e)}")
        raise HTTPException(status_code=500, detail="Cleanup failed")

if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting FastAPI server on port {port}...")
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=port, 
        reload=False,  # Disable reload in production
        access_log=True
    )