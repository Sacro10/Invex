"""
SQLAlchemy database configuration and session management.

Supports:
- PostgreSQL in production (via DATABASE_URL env var from Railway)
- SQLite locally (fallback to ./local.db if DATABASE_URL not set)
"""

import logging
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from settings import settings

logger = logging.getLogger(__name__)

# Use database URL from settings
DATABASE_URL = settings.database_url

# Configure engine based on database type
if DATABASE_URL.startswith("postgresql"):
    # PostgreSQL - use psycopg3 driver (compatible with Python 3.13)
    engine = create_engine(
        DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1),
        echo=False,
        pool_pre_ping=True,  # Verify connections before use
    )
else:
    # SQLite - use StaticPool for thread safety
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base for models
Base = declarative_base()


def get_db():
    """
    Dependency function for FastAPI to inject database session.
    
    Yields:
        Session: SQLAlchemy session for database operations
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database by running Alembic migrations."""
    from alembic.config import Config
    from alembic import command
    import os

    try:
        # Get the directory of this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        alembic_dir = os.path.join(current_dir, 'alembic')

        # Create Alembic config
        alembic_cfg = Config()
        alembic_cfg.set_main_option('script_location', alembic_dir)
        alembic_cfg.set_main_option('sqlalchemy.url', DATABASE_URL)

        # Run migrations
        command.upgrade(alembic_cfg, 'head')
        logger.info("Database migrations completed successfully")

    except Exception as e:
        error_msg = f"Database migration failed: {e}"

        if settings.is_production:
            # In production, fail hard - don't create tables manually
            logger.error(f"{error_msg} - Failing in production (no fallback to create_all)")
            raise RuntimeError(f"Database migration failed in production: {e}")
        else:
            # In development/test, fallback to create_all for convenience
            logger.warning(f"{error_msg} - Using create_all fallback in {settings.environment}")
            Base.metadata.create_all(bind=engine)
            logger.info("Fallback: Created tables using create_all")
