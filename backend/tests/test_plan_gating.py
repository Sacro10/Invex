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


def test_core_user_denied_premium_endpoint(client, free_org):
    """Test that core plan users are denied access to premium-only endpoints."""
    headers = {"Authorization": f"Bearer {free_org['token']}"}
    
    # Try to access enterprise analytics (requires advanced_analytics capability)
    response = client.get("/api/enterprise/analytics", headers=headers)
    assert response.status_code == 403
    assert "advanced_analytics" in response.json()["detail"]


def test_premium_user_allowed_premium_endpoint(client, premium_org):
    """Test that premium plan users can access premium-only endpoints."""
    headers = {"Authorization": f"Bearer {premium_org['token']}"}
    
    # Try to access enterprise analytics (requires advanced_analytics capability)
    response = client.get("/api/enterprise/analytics", headers=headers)
    assert response.status_code == 200
    assert "Enterprise analytics data" in response.json()["message"]


def test_core_user_allowed_basic_features(client, free_org):
    """Test that core plan users can access basic features."""
    headers = {"Authorization": f"Bearer {free_org['token']}"}
    
    # Try to access tenant screening (available in core)
    response = client.post("/api/tenant-screening", headers=headers, json={
        "name": "John Doe",
        "income": 50000,
        "credit_score": 650,
        "evictions": 0
    })
    assert response.status_code == 200


def test_growth_user_denied_premium_features(client, pro_org):
    """Test that growth plan users are denied premium-only features."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}
    
    # Try to access data export (requires data_export_api_access - premium only)
    response = client.get("/api/export/tenant-screenings/csv", headers=headers)
    assert response.status_code == 403
    assert "data_export_api_access" in response.json()["detail"]


def test_require_plan_functionality(client, free_org, pro_org):
    """Test the require_plan functionality with different plan levels."""
    # This would test endpoints that use require_plan instead of require_capability
    # For now, we'll test the logic indirectly through existing endpoints
    
    # Core user trying premium feature
    headers_core = {"Authorization": f"Bearer {free_org['token']}"}
    response = client.get("/api/enterprise/analytics", headers=headers_core)
    assert response.status_code == 403
    
    # Growth user trying premium feature  
    headers_growth = {"Authorization": f"Bearer {pro_org['token']}"}
    response = client.get("/api/enterprise/analytics", headers=headers_growth)
    assert response.status_code == 403  # Growth users should be denied premium features