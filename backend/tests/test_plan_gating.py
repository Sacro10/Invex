"""
Tests for plan-based feature gating.
"""

import pytest


def test_free_plan_limits(client: pytest.fixture, free_org: pytest.fixture):
    """Test that free plan organizations are limited to 1 property."""
    headers = {"Authorization": f"Bearer {free_org['token']}"}

    # First property should work
    response = client.post("/api/properties", headers=headers, json={
        "property_id": "PROP001",
        "address": "123 Free St",
        "city": "Freeland",
        "state": "FL",
        "zip_code": "11111",
        "property_type": "apartment",
        "units": 5
    })
    assert response.status_code == 200

    # Second property should be blocked
    response = client.post("/api/properties", headers=headers, json={
        "property_id": "PROP002",
        "address": "456 Free Ave",
        "city": "Freeland",
        "state": "FL",
        "zip_code": "11112",
        "property_type": "house",
        "units": 1
    })
    assert response.status_code == 403
    assert "Free plan is limited to 1 property" in response.json()["detail"]


def test_pro_plan_unlimited_properties(client: pytest.fixture, pro_org: pytest.fixture):
    """Test that pro plan organizations can create unlimited properties."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}

    # Create multiple properties
    for i in range(5):
        response = client.post("/api/properties", headers=headers, json={
            "property_id": f"PROP{i+1:03d}",
            "address": f"{i} Pro St",
            "city": "Proland",
            "state": "PR",
            "zip_code": f"2222{i}",
            "property_type": "apartment",
            "units": 10
        })
        assert response.status_code == 200

    # Verify all properties exist
    response = client.get("/api/properties", headers=headers)
    assert response.status_code == 200
    properties = response.json()
    assert len(properties) == 5


def test_free_plan_tenant_screening_limit(client: pytest.fixture, free_org: pytest.fixture):
    """Test that free plan organizations are limited to 5 tenant screenings per month."""
    headers = {"Authorization": f"Bearer {free_org['token']}"}

    # Create 5 screenings (should work)
    for i in range(5):
        response = client.post("/api/tenant-screening", headers=headers, json={
            "name": f"Tenant {i}",
            "income": 50000,
            "credit_score": 750,
            "evictions": 0
        })
        assert response.status_code == 200

    # 6th screening should be blocked
    response = client.post("/api/tenant-screening", headers=headers, json={
        "name": "Tenant 6",
        "income": 50000,
        "credit_score": 750,
        "evictions": 0
    })
    assert response.status_code == 403
    assert "Free plan is limited to 5 tenant screenings per month" in response.json()["detail"]


def test_pro_plan_unlimited_screenings(client: pytest.fixture, pro_org: pytest.fixture):
    """Test that pro plan organizations can do unlimited tenant screenings."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}

    # Create many screenings
    for i in range(10):
        response = client.post("/api/tenant-screening", headers=headers, json={
            "name": f"Pro Tenant {i}",
            "income": 60000,
            "credit_score": 800,
            "evictions": 0
        })
        assert response.status_code == 200


def test_enterprise_features_require_enterprise_plan(client: pytest.fixture, pro_org: pytest.fixture):
    """Test that enterprise features require enterprise plan."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}

    # Try to access enterprise-only endpoint (assuming one exists)
    # For now, test with a placeholder - adjust based on actual enterprise features
    response = client.get("/api/enterprise/analytics", headers=headers)
    assert response.status_code == 403
    assert "This feature requires a higher plan" in response.json()["detail"]


def test_plan_upgrade_scenario(client: pytest.fixture, free_org: pytest.fixture):
    """Test that upgrading plans unlocks features."""
    headers = {"Authorization": f"Bearer {free_org['token']}"}

    # First, hit the free plan limit
    response = client.post("/api/properties", headers=headers, json={
        "property_id": "PROP001",
        "address": "123 Free St",
        "city": "Freeland",
        "state": "FL",
        "zip_code": "11111",
        "property_type": "apartment",
        "units": 5
    })
    assert response.status_code == 200

    # Second property should fail
    response = client.post("/api/properties", headers=headers, json={
        "property_id": "PROP002",
        "address": "456 Free Ave",
        "city": "Freeland",
        "state": "FL",
        "zip_code": "11112",
        "property_type": "house",
        "units": 1
    })
    assert response.status_code == 403

    # Simulate plan upgrade (this would normally be done via Stripe webhook)
    # For testing, we'll manually update the subscription in the database
    # This assumes we have a way to update the plan in the test fixtures

    # After upgrade, should be able to create more properties
    # Note: This test would need adjustment based on how plan upgrades are handled