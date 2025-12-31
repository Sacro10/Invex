"""
Test configuration for pytest.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from models import Organization, User, Subscription, Plan


# Create file-based SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the database dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all tables before running tests."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clear_database():
    """Clear all data from tables before each test."""
    yield
    # Clear all tables after each test
    from sqlalchemy import text
    with engine.connect() as conn:
        # Disable foreign key checks for SQLite
        conn.execute(text("PRAGMA foreign_keys = OFF"))
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
        conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()


@pytest.fixture
def client():
    """Create a test client with overridden database dependency."""
    # Mock password functions before importing app to avoid bcrypt issues
    import sys
    from unittest.mock import patch
    
    mock_hash = lambda pwd: f"mock_hash_{pwd}"
    mock_verify = lambda plain, hashed: plain in hashed
    
    with patch('auth.hash_password', side_effect=mock_hash), \
         patch('auth.verify_password', side_effect=mock_verify):
        
        # Import app after mocking
        from main import app
        
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app) as test_client:
            yield test_client
        app.dependency_overrides.clear()


@pytest.fixture
def test_org(db_session):
    """Create a test organization."""
    import uuid
    org = Organization(name=f"Test Org {uuid.uuid4()}", created_at=None)
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_user(db_session, test_org):
    """Create a test user."""
    from auth import hash_password
    user = User(
        org_id=test_org.id,
        email="test@example.com",
        password_hash=hash_password("password123"),
        role="owner"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_subscription(db_session, test_org):
    """Create a test subscription."""
    from datetime import datetime, timezone, timedelta
    subscription = Subscription(
        org_id=test_org.id,
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        plan="core",
        status="active",
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30)
    )
    db_session.add(subscription)
    db_session.commit()
    db_session.refresh(subscription)
    return subscription


@pytest.fixture
def auth_headers(client, test_user):
    """Get authentication headers for test user."""
    # Login to get access token
    response = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "password123"
    })
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def db_session():
    """Get a database session for direct database operations in tests."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()