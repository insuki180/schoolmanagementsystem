"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/school_db"

    # Security
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # Super Admin seed
    SUPER_ADMIN_EMAIL: str = "admin@school.com"
    SUPER_ADMIN_PASSWORD: str = "admin123"
    SUPER_ADMIN_NAME: str = "Super Admin"

    # Environment
    ENVIRONMENT: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def validate_production_settings(self):
        if self.ENVIRONMENT == "production":
            if self.SECRET_KEY == "change-this-in-production":
                raise ValueError("SECRET_KEY must be properly set in production")
            if "localhost" in self.DATABASE_URL or "sqlite" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must point to a production database")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
