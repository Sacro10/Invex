"""
Tests for multi-tenancy isolation.
"""

import pytest
from sqlalchemy.orm import Session


def test_property_isolation_between_orgs(client: pytest.fixture, db_session: Session):
    """Test that organizations cannot see each other's properties."""
    # Create first organization and user
    response1 = client.post("/api/auth/register", json={
        "org_name": "Org One",
        "email": "org1@example.com",
        "password": "password123"
    })
    assert response1.status_code == 200
    token1 = response1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Create second organization and user
    response2 = client.post("/api/auth/register", json={
        "org_name": "Org Two",
        "email": "org2@example.com",
        "password": "password123"
    })
    assert response2.status_code == 200
    token2 = response2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Org 1 creates a property
    response = client.post("/api/properties", headers=headers1, json={
        "address": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "zip_code": "12345",
        "property_type": "apartment",
        "units": 10
    })
    assert response.status_code == 200
    property_data = response.json()

    # Org 2 creates a different property
    response = client.post("/api/properties", headers=headers2, json={
        "address": "456 Oak Ave",
        "city": "Othertown",
        "state": "NY",
        "zip_code": "67890",
        "property_type": "house",
        "units": 1
    })
    assert response.status_code == 200

    # Org 1 should only see their property
    response = client.get("/api/properties", headers=headers1)
    assert response.status_code == 200
    properties = response.json()
    assert len(properties) == 1
    assert properties[0]["address"] == "123 Main St"
    assert properties[0]["city"] == "Anytown"

    # Org 2 should only see their property
    response = client.get("/api/properties", headers=headers2)
    assert response.status_code == 200
    properties = response.json()
    assert len(properties) == 1
    assert properties[0]["address"] == "456 Oak Ave"
    assert properties[0]["city"] == "Othertown"

    # Org 1 should not be able to access Org 2's property directly
    response = client.put(f"/api/properties/{property_data['id']}", headers=headers2, json={
        "address": "456 Oak Ave",
        "city": "Othertown",
        "state": "NY",
        "zip_code": "67890",
        "property_type": "house",
        "units": 1
    })
    assert response.status_code == 404  # Not found because it belongs to different org


def test_tenant_screening_isolation(client: pytest.fixture):
    """Test that tenant screenings are isolated between organizations."""
    # Create first organization and user
    response1 = client.post("/api/auth/register", json={
        "org_name": "Screening Org One",
        "email": "screen1@example.com",
        "password": "password123"
    })
    assert response1.status_code == 200
    token1 = response1.json()["access_token"]
    headers1 = {"Authorization": f"Bearer {token1}"}

    # Create second organization and user
    response2 = client.post("/api/auth/register", json={
        "org_name": "Screening Org Two",
        "email": "screen2@example.com",
        "password": "password123"
    })
    assert response2.status_code == 200
    token2 = response2.json()["access_token"]
    headers2 = {"Authorization": f"Bearer {token2}"}

    # Org 1 creates a tenant screening
    response = client.post("/api/tenant-screening", headers=headers1, json={
        "name": "John Doe",
        "income": 50000,
        "credit_score": 750,
        "evictions": 0
    })
    assert response.status_code == 200

    # Org 2 creates a different tenant screening
    response = client.post("/api/tenant-screening", headers=headers2, json={
        "name": "Jane Smith",
        "income": 60000,
        "credit_score": 800,
        "evictions": 0
    })
    assert response.status_code == 200

    # Each org should only see their own screenings
    response = client.get("/api/tenant-screenings", headers=headers1)
    assert response.status_code == 200
    screenings = response.json()
    assert len(screenings) == 1
    assert screenings[0]["name"] == "John Doe"

    response = client.get("/api/tenant-screenings", headers=headers2)
    assert response.status_code == 200
    screenings = response.json()
    assert len(screenings) == 1
    assert screenings[0]["name"] == "Jane Smith"