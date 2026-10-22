import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "HealthRisk AI"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Security & Tokens
    SECRET_KEY: str = os.getenv("SECRET_KEY", "healthrisk-ai-secure-production-ready-jwt-secret-key-32chars-min")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./healthrisk.db")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # ML Model directory
    MODEL_DIR: str = os.getenv("MODEL_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ml_models"))
    
    # Rate Limiting
    RATE_LIMIT_LOGIN_MAX: int = 5
    RATE_LIMIT_LOGIN_WINDOW_SEC: int = 60
    LOCKOUT_DURATION_SEC: int = 900  # 15 minutes
    
    RATE_LIMIT_PREDICT_MAX: int = 30
    RATE_LIMIT_PREDICT_WINDOW_SEC: int = 60
    
    RATE_LIMIT_DIARY_MAX: int = 60
    RATE_LIMIT_DIARY_WINDOW_SEC: int = 3600  # 1 hour
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000"
    ]

    class Config:
        case_sensitive = True
        extra = "ignore"

settings = Settings()
