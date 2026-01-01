"""Tests for settings configuration module."""

import pytest
from unittest.mock import patch
import os
from pydantic import ValidationError
from settings import Settings


class TestSettings:
    """Test the Settings class configuration."""

    def test_default_values(self):
        """Test default values when no environment variables are set."""
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            assert settings.environment == "development"
            assert settings.database_url == "sqlite:///./local.db"
            assert settings.jwt_secret == "change-this-in-production"
            assert settings.cors_origins == "http://localhost:8000"
            assert settings.cors_origins_list == ["http://localhost:8000"]
            assert settings.is_production is False

    def test_production_environment(self):
        """Test production environment detection."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production", 
            "JWT_SECRET": "valid-secret",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
        }, clear=True):
            settings = Settings()
            assert settings.environment == "production"
            assert settings.is_production is True

    def test_staging_environment(self):
        """Test staging environment detection."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "staging", 
            "JWT_SECRET": "valid-secret",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
        }, clear=True):
            settings = Settings()
            assert settings.environment == "staging"
            assert settings.is_production is True

    def test_development_environment(self):
        """Test development environment detection."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            settings = Settings()
            assert settings.environment == "development"
            assert settings.is_production is False

    def test_custom_database_url(self):
        """Test custom database URL from environment."""
        test_url = "postgresql://user:pass@localhost:5432/db"
        with patch.dict(os.environ, {"DATABASE_URL": test_url}, clear=True):
            settings = Settings()
            assert settings.database_url == test_url

    def test_custom_jwt_secret(self):
        """Test custom JWT secret from environment."""
        test_secret = "my-super-secret-key"
        with patch.dict(os.environ, {"JWT_SECRET": test_secret}, clear=True):
            settings = Settings()
            assert settings.jwt_secret == test_secret

    def test_cors_origins_parsing(self):
        """Test CORS origins parsing from environment."""
        test_origins = "https://example.com,https://app.example.com"
        with patch.dict(os.environ, {"CORS_ORIGINS": test_origins}, clear=True):
            settings = Settings()
            assert settings.cors_origins == test_origins
            assert settings.cors_origins_list == ["https://example.com", "https://app.example.com"]

    def test_cors_origins_single_value(self):
        """Test CORS origins parsing with single value."""
        test_origin = "https://example.com"
        with patch.dict(os.environ, {"CORS_ORIGINS": test_origin}, clear=True):
            settings = Settings()
            assert settings.cors_origins == test_origin
            assert settings.cors_origins_list == ["https://example.com"]

    def test_cors_origins_empty_string(self):
        """Test CORS origins parsing with empty string."""
        with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=True):
            settings = Settings()
            assert settings.cors_origins == ""
            assert settings.cors_origins_list == []

    @pytest.mark.parametrize("env_value,expected_production", [
        ("production", True),
        ("PRODUCTION", True),
        ("staging", True),
        ("STAGING", True),
        ("development", False),
        ("DEVELOPMENT", False),
        ("test", False),
        ("TEST", False),
    ])
    def test_is_production_various_values(self, env_value, expected_production):
        """Test is_production property with various environment values."""
        env_vars = {"ENVIRONMENT": env_value}
        if expected_production:
            env_vars["JWT_SECRET"] = "valid-secret"
            env_vars["DATABASE_URL"] = "postgresql://user:pass@localhost:5432/db"
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.is_production == expected_production

    @pytest.mark.parametrize("invalid_env_value", ["", "random", "invalid"])
    def test_invalid_environment_values_raise_validation_error(self, invalid_env_value):
        """Test that invalid environment values raise ValidationError."""
        with patch.dict(os.environ, {"ENVIRONMENT": invalid_env_value}, clear=True):
            with pytest.raises(ValidationError, match="ENVIRONMENT must be one of"):
                Settings()

    def test_production_requires_jwt_secret(self):
        """Test that production environment requires JWT_SECRET to be set."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "JWT_SECRET": "change-this-in-production"  # Default value
        }, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET is required in production/staging"):
                Settings()

    def test_production_accepts_custom_jwt_secret(self):
        """Test that production environment accepts custom JWT secret."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "JWT_SECRET": "my-custom-secret-key",
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
        }, clear=True):
            settings = Settings()
            assert settings.jwt_secret == "my-custom-secret-key"

    def test_staging_requires_jwt_secret(self):
        """Test that staging environment requires JWT_SECRET to be set."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "staging",
            "JWT_SECRET": "change-this-in-production",  # Default value
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/db"
        }, clear=True):
            with pytest.raises(ValueError, match="JWT_SECRET is required in production/staging"):
                Settings()