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


def test_login_wrong_password(client: pytest.fixture):
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


def test_homepage_public_access(client: pytest.fixture):
    """Test that homepage (/) is publicly accessible without authentication."""
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "INDEX" in response.text  # Check for content from index.html


def test_protected_page_fallback_to_auth(client: pytest.fixture):
    """Test that protected pages return auth.html content when not authenticated."""
    response = client.get("/maintenance.html")

    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Check that it contains content from auth.html (like login form)
    assert "Login" in response.text or "Sign Up" in response.text


def test_protected_page_with_auth(client: pytest.fixture, test_user: pytest.fixture):
    """Test that protected pages return the actual page content when authenticated."""
    # First login to get token
    login_response = client.post("/api/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]
    
    # Now access protected page with token
    response = client.get("/maintenance.html", headers={"Authorization": f"Bearer {token}"})
    
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Should contain content from maintenance.html, not auth.html
    assert "maintenance" in response.text.lower() or "Maintenance" in response.text


def test_catch_all_unknown_api_route(client: pytest.fixture):
    """Test that unknown API routes return 404."""
    response = client.get("/api/unknown-endpoint")
    
    assert response.status_code == 404
    assert "API endpoint not found" in response.json()["detail"]


def test_catch_all_api_health_still_works(client: pytest.fixture):
    """Test that existing API routes still work through catch-all."""
    response = client.get("/api/health")
    
    assert response.status_code == 200
    assert "status" in response.json()


def test_catch_all_unknown_frontend_path_unauthenticated(client: pytest.fixture):
    """Test that unknown frontend paths return auth.html when not authenticated."""
    response = client.get("/some-protected-route")
    
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    # Should contain auth.html content
    assert "Login" in response.text or "Sign Up" in response.text


def test_catch_all_unknown_static_file(client: pytest.fixture):
    """Test that unknown static files return 404."""
    response = client.get("/unknown-file.css")
    
    assert response.status_code == 404
    assert "Static file not found" in response.json()["detail"]


def test_public_static_assets_accessible(client: pytest.fixture):
    """Test that public static assets required by index.html are accessible."""
    # Test CSS
    response = client.get("/styles.css")
    assert response.status_code == 200
    assert "text/css" in response.headers.get("content-type", "")

    # Test JavaScript
    response = client.get("/script.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers.get("content-type", "")

    # Test images
    response = client.get("/pic1.jpeg")
    assert response.status_code == 200
    assert "image/jpeg" in response.headers.get("content-type", "")