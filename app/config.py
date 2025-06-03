import os
from enum import Enum
from pydantic import BaseSettings, Field
from typing import List, Optional
import logging

class Environment(str, Enum):
    DEVELOPMENT = "dev"
    PRODUCTION = "prod"
    TESTING = "testing"

class Settings(BaseSettings):
    # Application settings
    environment: Environment = Field(default=Environment.DEVELOPMENT, env="ENVIRONMENT")
    app_name: str = Field(default="Chatbot API", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    debug: bool = Field(default=False, env="DEBUG")
    
    # Server settings
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    reload: bool = Field(default=False, env="RELOAD")
    
    # Database settings
    db_host: Optional[str] = Field(default=None, env="DB_HOST")
    db_port: str = Field(default="5432", env="DB_PORT")
    db_name: str = Field(default="chatbot", env="DB_NAME")
    db_username: Optional[str] = Field(default=None, env="DB_USERNAME")
    db_password: Optional[str] = Field(default=None, env="DB_PASSWORD")
    db_ssm_prefix: Optional[str] = Field(default=None, env="DB_SSM_PREFIX")
    
    # Connection pool settings
    db_pool_size: int = Field(default=5, env="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, env="DB_MAX_OVERFLOW")
    db_pool_recycle: int = Field(default=3600, env="DB_POOL_RECYCLE")
    db_connect_timeout: int = Field(default=10, env="DB_CONNECT_TIMEOUT")
    
    # AWS settings
    aws_region: str = Field(default="us-west-2", env="AWS_REGION")
    
    # CORS settings
    allowed_origins: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    allowed_methods: List[str] = Field(default=["GET", "POST"], env="ALLOWED_METHODS")
    allowed_headers: List[str] = Field(default=["*"], env="ALLOWED_HEADERS")
    allow_credentials: bool = Field(default=True, env="ALLOW_CREDENTIALS")
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        env="LOG_FORMAT"
    )
    
    # API settings
    max_message_length: int = Field(default=5000, env="MAX_MESSAGE_LENGTH")
    max_history_limit: int = Field(default=100, env="MAX_HISTORY_LIMIT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def is_development(self) -> bool:
        return self.environment == Environment.DEVELOPMENT
    
    @property
    def is_production(self) -> bool:
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_testing(self) -> bool:
        return self.environment == Environment.TESTING

class DevelopmentSettings(Settings):
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    reload: bool = True
    log_level: str = "DEBUG"
    allowed_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    db_pool_size: int = 2
    db_max_overflow: int = 5

class ProductionSettings(Settings):
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    reload: bool = False
    log_level: str = "INFO"
    # In production, you should specify exact origins
    allowed_origins: List[str] = []  # Set via environment variable
    db_pool_size: int = 10
    db_max_overflow: int = 20

class TestingSettings(Settings):
    environment: Environment = Environment.TESTING
    debug: bool = True
    log_level: str = "WARNING"
    db_name: str = "chatbot_test"
    db_pool_size: int = 1
    db_max_overflow: int = 2

def get_settings() -> Settings:
    """Factory function to return the appropriate settings based on environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()
    
    if env == "production":
        return ProductionSettings()
    elif env == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()

# Global settings instance
settings = get_settings()

def setup_logging():
    """Configure logging based on environment settings"""
    numeric_level = getattr(logging, settings.log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f'Invalid log level: {settings.log_level}')
    
    logging.basicConfig(
        level=numeric_level,
        format=settings.log_format,
        handlers=[
            logging.StreamHandler(),
            # Add file handler for production
            *([logging.FileHandler('app.log')] if settings.is_production else [])
        ]
    )
    
    # Set different log levels for different modules in production
    if settings.is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)