"""
Application configuration
"""
import os
from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Perchspot API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Database - no default in production
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/housing_analysis"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3/MinIO - no hardcoded defaults for credentials
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET: str = "housing-analysis"

    # API Keys
    OPENAI_API_KEY: str = ""  # Used for chat agent and LLM analysis
    ANTHROPIC_API_KEY: str = ""  # For Claude Vision extraction
    GEMINI_API_KEY: str = ""  # For analysis (cheaper than Claude)
    GREATSCHOOLS_API_KEY: str = ""  # Optional, will scrape if not available
    GOOGLE_MAPS_API_KEY: str = ""  # For commute time calculations

    @field_validator('S3_ACCESS_KEY', 'S3_SECRET_KEY')
    @classmethod
    def validate_s3_credentials(cls, v: str, info) -> str:
        """Validate S3 credentials are set in production"""
        if not os.getenv('DEBUG', 'True').lower() == 'true' and not v:
            raise ValueError(f"{info.field_name} is required in production")
        return v

    # LLM Provider Selection for Analysis
    ANALYSIS_LLM_PROVIDER: str = "gemini"  # "gemini" or "claude"

    # Web Scraping Configuration
    USER_AGENT: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    SCRAPING_DELAY_SECONDS: int = 2
    MAX_RETRIES: int = 3

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 10
    MAX_CONCURRENT_ANALYSES: int = 3

    # Caching
    CACHE_TTL_HOURS: int = 24

    # Admin - no default in production
    ADMIN_PASSWORD: str = ""

    @field_validator('ADMIN_PASSWORD')
    @classmethod
    def validate_admin_password(cls, v: str) -> str:
        """Validate admin password is set and strong in production"""
        if not os.getenv('DEBUG', 'True').lower() == 'true':
            if not v:
                raise ValueError("ADMIN_PASSWORD is required in production")
            if len(v) < 16:
                raise ValueError("ADMIN_PASSWORD must be at least 16 characters in production")
        return v or "admin"  # Default for development only

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # LLM Configuration
    LLM_MODEL: str = "gpt-4o"
    LLM_CHEAP_MODEL: str = "gpt-4o-mini"
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.3

    # Feature Flags for LLM Analysis
    ENABLE_PROPERTY_LLM_ANALYSIS: bool = False  # Set to True to enable LLM analysis of property quality

    # Image Processing
    MAX_IMAGES_PER_ANALYSIS: int = 15
    IMAGE_MAX_SIZE_PX: int = 1024

    # Pricing
    PRICING_MARGIN: float = 0.80  # 80% margin: user pays cost / (1 - margin)

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""

    # AWS SES (Email)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    SES_FROM_EMAIL: str = "Perchspot <hello@perchspot.com>"

    # JWT / Auth - no default in production
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24
    STARTING_CREDIT: float = 0.00

    @field_validator('JWT_SECRET_KEY')
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret is set and strong in production"""
        if not os.getenv('DEBUG', 'True').lower() == 'true':
            if not v:
                raise ValueError("JWT_SECRET_KEY is required in production")
            if len(v) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
        return v or "dev-secret-change-in-production"  # Default for development only

    # Free Tier
    FREE_ANALYSES_PER_IP: int = 1

    # Scoring Weights
    WEIGHT_PROPERTY_CONDITION: float = 0.30
    WEIGHT_LOCATION_QUALITY: float = 0.25
    WEIGHT_SCHOOLS: float = 0.20
    WEIGHT_INVESTMENT_VALUE: float = 0.25

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
