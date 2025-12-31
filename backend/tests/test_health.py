"""
Tests for health and monitoring endpoints.
"""

import pytest


def test_health_endpoint(client: pytest.fixture):
    """Test the basic health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert "version" in data


def test_health_database_check(client: pytest.fixture):
    """Test that health endpoint checks database connectivity."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    # Assuming the health endpoint includes database status
    assert "database" in data
    assert data["database"] == "connected"


def test_pulse_endpoint_requires_auth(client: pytest.fixture):
    """Test that pulse endpoint requires authentication."""
    response = client.get("/api/pulse")
    assert response.status_code == 401


def test_pulse_endpoint_with_auth(client: pytest.fixture, pro_org: pytest.fixture):
    """Test the pulse endpoint with authentication."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}
    response = client.get("/api/pulse", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "occupancy_rate" in data
    assert "rent_collected" in data
    assert "open_requests" in data
    assert "recent_activity" in data


def test_pulse_data_accuracy(client: pytest.fixture, pro_org: pytest.fixture, db_session: Session):
    """Test that pulse data reflects actual database state."""
    from backend.models import Property, MaintenanceRequest

    headers = {"Authorization": f"Bearer {pro_org['token']}"}

    # Create some test data
    org_id = pro_org["org_id"]

    # Create properties
    property1 = Property(
        org_id=org_id,
        address="123 Test St",
        city="Test City",
        state="TS",
        zip_code="12345",
        property_type="apartment",
        units=10,
        occupied_units=7
    )
    property2 = Property(
        org_id=org_id,
        address="456 Test Ave",
        city="Test City",
        state="TS",
        zip_code="12346",
        property_type="house",
        units=1,
        occupied_units=1
    )
    db_session.add(property1)
    db_session.add(property2)
    db_session.commit()

    # Create maintenance request
    maint_req = MaintenanceRequest(
        org_id=org_id,
        property_id=property1.id,
        issue_description="Leaky faucet",
        priority="medium",
        status="open"
    )
    db_session.add(maint_req)
    db_session.commit()

    # Check pulse data
    response = client.get("/api/pulse", headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Should have 80% occupancy (8/10 units occupied)
    assert data["occupancy_rate"] == 80.0
    assert data["open_requests"] == 1
    assert len(data["recent_activity"]) >= 1


def test_metrics_endpoint(client: pytest.fixture, pro_org: pytest.fixture):
    """Test the metrics endpoint if it exists."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}
    response = client.get("/api/metrics", headers=headers)
    # This might return 404 if not implemented, or 200 if it is
    if response.status_code == 200:
        data = response.json()
        assert "uptime" in data or "requests_total" in data  # Basic metrics check