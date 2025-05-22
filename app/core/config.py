import os
from typing import List
from pydantic import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Chatbot"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Security settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    
    # CORS settings
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # AWS settings
    AWS_REGION: str = os.getenv("AWS_REGION", "us-west-2")
    
    class Config:
        case_sensitive = True

settings = Settings()