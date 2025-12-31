"""
Tests for authentication endpoints.
"""

import pytest
from sqlalchemy.orm import Session


def test_register_new_organization(client: pytest.fixture, db_session: Session):
    """Test registering a new organization and user."""
    response = client.post("/api/auth/register", json={
        "organization_name": "New Test Org",
        "email": "newuser@example.com",
        "password": "secure123"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user_id" in data
    assert "org_id" in data
    assert data["email"] == "newuser@example.com"
    assert data["role"] == "owner"


def test_register_duplicate_email(client: pytest.fixture, test_user: pytest.fixture):
    """Test that duplicate email registration fails."""
    response = client.post("/api/auth/register", json={
        "organization_name": "Another Org",
        "email": "test@example.com",  # Same email as test_user
        "password": "another123"
    })

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


def test_login_success(client: pytest.fixture, test_user: pytest.fixture):
    """Test successful login."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "user_id" in data
    assert "org_id" in data
    assert data["email"] == "test@example.com"


def test_login_wrong_password(client: pytest.fixture, test_user: pytest.fixture):
    """Test login with wrong password."""
    response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword"
    })

    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


def test_login_nonexistent_user(client: pytest.fixture):
    """Test login with nonexistent user."""
    response = client.post("/api/auth/login", json={
        "email": "nonexistent@example.com",
        "password": "password123"
    })

    assert response.status_code == 401
    assert "invalid email or password" in response.json()["detail"].lower()


def test_get_me_authenticated(client: pytest.fixture, test_user: pytest.fixture):
    """Test getting current user info when authenticated."""
    from unittest.mock import patch
    
    with patch('auth.verify_token', return_value={"sub": test_user.id, "org_id": test_user.org_id, "email": test_user.email}):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer fake_token"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == test_user.id
    assert data["org_id"] == test_user.org_id
    assert data["email"] == test_user.email
    assert data["role"] == test_user.role
    assert "organization_name" in data


def test_get_me_unauthenticated(client: pytest.fixture):
    """Test getting current user info when not authenticated."""
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert "missing or invalid authorization header" in response.json()["detail"].lower()