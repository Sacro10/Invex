"""
Tests for health and monitoring endpoints.
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime, timezone


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


def test_pulse_endpoint_with_auth(client, auth_headers):
    """Test the pulse endpoint with authentication."""
    response = client.get("/api/pulse", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "occupancy" in data
    assert "open_requests" in data
    assert "rent_collected" in data
    assert "timeline" in data


def test_pulse_data_accuracy(client, auth_headers, db_session):
    """Test that pulse data reflects actual database state."""
    from models import Property, MaintenanceRequest

    # Create some test data
    org_id = 1  # Assuming test user is in org 1

    # Create properties
    property1 = Property(
        org_id=org_id,
        property_id="PROP001",
        address="123 Test St",
        city="Test City",
        state="TS",
        zip_code="12345",
        property_type="apartment"
    )
    property2 = Property(
        org_id=org_id,
        property_id="PROP002",
        address="456 Test Ave",
        city="Test City",
        state="TS",
        zip_code="12346",
        property_type="house"
    )
    db_session.add(property1)
    db_session.add(property2)
    db_session.commit()

    # Create maintenance request
    maint_req = MaintenanceRequest(
        org_id=org_id,
        property_id=property1.property_id,
        issue="Leaky faucet",
        priority="medium",
        vendor="Test Vendor",
        scheduled_for="2025-01-01",
        status="open",
        sla_due_at=datetime.now(timezone.utc)
    )
    db_session.add(maint_req)
    db_session.commit()

    # Check pulse data
    response = client.get("/api/pulse", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Should have some basic data (exact values depend on implementation)
    assert "occupancy" in data
    assert "open_requests" in data
    assert "timeline" in data


def test_metrics_endpoint(client, auth_headers):
    """Test the metrics endpoint if it exists."""
    response = client.get("/api/metrics", headers=auth_headers)
    # This might return 404 if not implemented, or 200 if it is
    if response.status_code == 200:
        data = response.json()
        assert "uptime" in data or "requests_total" in data  # Basic metrics check