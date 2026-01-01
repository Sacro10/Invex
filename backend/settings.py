"""
Centralized configuration management for INDEX Property Management SaaS.

Uses Pydantic BaseSettings for environment variable validation and loading.
Supports development and production environments with appropriate security defaults.
"""

from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment-specific validation."""

    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")

    # Security
    jwt_secret: str = Field(default="change-this-in-production", env="JWT_SECRET")
    jwt_algorithm: str = "HS256"

    # Database
    database_url: str = Field(default="sqlite:///./local.db", env="DATABASE_URL")

    # Stripe (optional - only needed for billing features)
    stripe_secret_key: Optional[str] = Field(default=None, env="STRIPE_SECRET_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, env="STRIPE_WEBHOOK_SECRET")

    # Email (optional - only needed for notifications)
    sendgrid_api_key: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    from_email: Optional[str] = Field(default=None, env="FROM_EMAIL")

    # CORS
    cors_origins: str = Field(default="http://localhost:8000", env="CORS_ORIGINS")

    # Server
    port: int = Field(default=8000, env="PORT")

    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        """Validate JWT secret based on environment."""
        # Get environment from info or default
        environment = info.data.get("environment", "development") if info.data else "development"

        if environment.lower() in ["production", "staging"]:
            if not v or v == "change-this-in-production":
                raise ValueError(
                    "JWT_SECRET is required in production/staging and cannot be the default value. "
                    "Set a secure random string in your environment variables."
                )
        else:
            # Development mode
            if not v:
                print("WARNING: JWT_SECRET not set in development, using default. This is NOT secure for production!")
                v = "dev-jwt-secret-change-in-production"
            elif v == "change-this-in-production":
                print("WARNING: Using default JWT_SECRET in development. Set a proper secret for production deployment.")

        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Validate ENVIRONMENT is one of the allowed values."""
        allowed_envs = ["development", "test", "production", "staging"]
        if v.lower() not in allowed_envs:
            raise ValueError(
                f"ENVIRONMENT must be one of {allowed_envs}, got '{v}'. "
                "Set ENVIRONMENT=production for production deployments."
            )
        return v.lower()

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str, info) -> str:
        """Validate DATABASE_URL is set in production."""
        environment = info.data.get("environment", "development") if info.data else "development"

        if environment in ["production", "staging"]:
            if not v or v.startswith("sqlite"):
                raise ValueError(
                    "DATABASE_URL must be set to a PostgreSQL URL in production/staging. "
                    "SQLite is not supported in production. "
                    f"Current value: {v}"
                )
        return v

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() in ["production", "staging"]

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS as comma-separated list."""
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins

    @property
    def cors_allow_credentials(self) -> bool:
        """Determine if CORS should allow credentials."""
        origins = self.cors_origins_list
        # Don't allow credentials with wildcard origins
        return "*" not in origins

    def get_cors_origins_for_fastapi(self) -> List[str]:
        """Get CORS origins list suitable for FastAPI CORSMiddleware."""
        origins = self.cors_origins_list
        # FastAPI expects None for wildcard, not ["*"]
        return origins if "*" not in origins else ["*"]


# Global settings instance
settings = Settings()