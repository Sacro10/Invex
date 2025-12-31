#!/usr/bin/env python3
"""
Multi-Tenant Isolation Test Script

This script tests that the multi-tenant SaaS implementation properly isolates
data between organizations. It creates two organizations and verifies that
each can only access its own data.

Usage:
    python test_multi_tenant.py

Requirements:
    - Server running at http://localhost:8000
    - pip install requests
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_result(success, message):
    """Print a test result."""
    status = "✓" if success else "✗"
    color = "\033[92m" if success else "\033[91m"
    reset = "\033[0m"
    print(f"{color}{status}{reset} {message}")


def test_health_check():
    """Test health check endpoint."""
    print_section("Health Check")
    response = requests.get(f"{BASE_URL}/api/health")
    success = response.status_code == 200
    print_result(success, f"Health check: {response.json().get('status')}")
    return success


def create_organization(org_name, email, password):
    """Register a new organization and user."""
    print_section(f"Creating Organization: {org_name}")
    
    response = requests.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": email,
            "password": password,
            "organization_name": org_name
        }
    )
    
    if response.status_code != 200:
        print_result(False, f"Failed to create organization: {response.text}")
        return None
    
    data = response.json()
    print_result(True, f"Organization created: {org_name}")
    print(f"  - User ID: {data['user_id']}")
    print(f"  - Org ID: {data['org_id']}")
    print(f"  - Email: {data['email']}")
    print(f"  - Token: {data['access_token'][:50]}...")
    
    return data


def create_property(token, address, city, org_name):
    """Create a property for testing."""
    print_section(f"Creating Property for {org_name}")
    
    response = requests.post(
        f"{BASE_URL}/api/properties",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "address": address,
            "city": city,
            "state": "OR",
            "zip_code": "97201",
            "property_type": "apartment",
            "units": 10
        }
    )
    
    if response.status_code != 200:
        print_result(False, f"Failed to create property: {response.text}")
        return None
    
    data = response.json()
    print_result(True, f"Property created: {data['address']}")
    print(f"  - Property ID: {data['id']}")
    
    return data


def list_properties(token, org_name):
    """List all properties for an organization."""
    print_section(f"Listing Properties for {org_name}")
    
    response = requests.get(
        f"{BASE_URL}/api/properties",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print_result(False, f"Failed to list properties: {response.text}")
        return []
    
    properties = response.json()
    print_result(True, f"Found {len(properties)} properties")
    
    for prop in properties:
        print(f"  - ID {prop['id']}: {prop['address']}, {prop['city']}")
    
    return properties


def create_tenant_screening(token, name, org_name):
    """Create a tenant screening for testing."""
    print_section(f"Creating Tenant Screening for {org_name}")
    
    response = requests.post(
        f"{BASE_URL}/api/tenant-screening",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": name,
            "income": 75000,
            "credit_score": 720,
            "evictions": 0
        }
    )
    
    if response.status_code != 200:
        print_result(False, f"Failed to create screening: {response.text}")
        return None
    
    data = response.json()
    print_result(True, f"Screening created for: {name}")
    print(f"  - Screening ID: {data['id']}")
    print(f"  - Risk Score: {data['risk_score']}")
    print(f"  - Risk Level: {data['risk_level']}")
    
    return data


def list_screenings(token, org_name):
    """List all tenant screenings for an organization."""
    print_section(f"Listing Tenant Screenings for {org_name}")
    
    response = requests.get(
        f"{BASE_URL}/api/tenant-screenings",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print_result(False, f"Failed to list screenings: {response.text}")
        return []
    
    screenings = response.json()
    print_result(True, f"Found {len(screenings)} screenings")
    
    for screening in screenings:
        print(f"  - ID {screening['id']}: {screening['name']} (Risk: {screening['risk_level']})")
    
    return screenings


def test_cross_org_access(token1, token2, org1_name, org2_name):
    """Test that organizations cannot access each other's data."""
    print_section("Testing Cross-Organization Access")
    
    # Org 1 should see its own properties
    props1 = list_properties(token1, org1_name)
    success1 = len(props1) > 0
    print_result(success1, f"{org1_name} can see its own properties")
    
    # Org 2 should NOT see Org 1's properties
    props2 = list_properties(token2, org2_name)
    success2 = len(props2) == 0
    print_result(success2, f"{org2_name} CANNOT see {org1_name}'s properties (isolated!)")
    
    return success1 and success2


def test_dashboard_pulse(token, org_name):
    """Test dashboard pulse endpoint."""
    print_section(f"Dashboard Pulse for {org_name}")
    
    response = requests.get(
        f"{BASE_URL}/api/pulse",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    if response.status_code != 200:
        print_result(False, f"Failed to get pulse: {response.text}")
        return False
    
    data = response.json()
    print_result(True, "Dashboard pulse retrieved")
    print(f"  - Occupancy: {data['occupancy']}%")
    print(f"  - Rent Collected: ${data['rent_collected']}")
    print(f"  - Open Requests: {data['open_requests']}")
    
    return True


def main():
    """Run all multi-tenant tests."""
    print("\n" + "=" * 60)
    print("  INDEX Property Management - Multi-Tenant Test Suite")
    print("=" * 60)
    
    all_tests_passed = True
    
    # Test 1: Health Check
    if not test_health_check():
        print("\n❌ Server is not running or not healthy!")
        print("   Start server with: cd backend && uvicorn main:app --reload")
        sys.exit(1)
    
    # Test 2: Create Organization 1
    org1 = create_organization(
        "Acme Properties LLC",
        "owner@acme-test.local",
        "testpass123"
    )
    if not org1:
        all_tests_passed = False
        sys.exit(1)
    
    # Test 3: Create Organization 2
    org2 = create_organization(
        "XYZ Realty Group",
        "owner@xyz-test.local",
        "testpass456"
    )
    if not org2:
        all_tests_passed = False
        sys.exit(1)
    
    # Test 4: Create property in Org 1
    prop1 = create_property(
        org1['access_token'],
        "100 Main Street",
        "Portland",
        "Acme Properties"
    )
    all_tests_passed &= (prop1 is not None)
    
    # Test 5: Create property in Org 2
    prop2 = create_property(
        org2['access_token'],
        "200 Oak Avenue",
        "Seattle",
        "XYZ Realty"
    )
    all_tests_passed &= (prop2 is not None)
    
    # Test 6: Create tenant screening in Org 1
    screen1 = create_tenant_screening(
        org1['access_token'],
        "John Doe",
        "Acme Properties"
    )
    all_tests_passed &= (screen1 is not None)
    
    # Test 7: Verify cross-org isolation
    all_tests_passed &= test_cross_org_access(
        org1['access_token'],
        org2['access_token'],
        "Acme Properties",
        "XYZ Realty"
    )
    
    # Test 8: Create property in Org 2 and verify still isolated
    prop3 = create_property(
        org2['access_token'],
        "300 Pine Boulevard",
        "Seattle",
        "XYZ Realty"
    )
    
    # Org 2 should now have its own properties
    props_org2 = list_properties(org2['access_token'], "XYZ Realty")
    success = len(props_org2) == 2  # Should have 2 properties
    print_result(success, f"XYZ Realty has {len(props_org2)} properties (expected 2)")
    all_tests_passed &= success
    
    # Org 1 should still only have 1 property
    props_org1 = list_properties(org1['access_token'], "Acme Properties")
    success = len(props_org1) == 1  # Should still have only 1
    print_result(success, f"Acme Properties has {len(props_org1)} properties (expected 1)")
    all_tests_passed &= success
    
    # Test 9: Verify screenings are isolated
    screenings_org1 = list_screenings(org1['access_token'], "Acme Properties")
    success = len(screenings_org1) == 1
    print_result(success, f"Acme Properties has {len(screenings_org1)} screenings (expected 1)")
    all_tests_passed &= success
    
    screenings_org2 = list_screenings(org2['access_token'], "XYZ Realty")
    success = len(screenings_org2) == 0
    print_result(success, f"XYZ Realty has {len(screenings_org2)} screenings (expected 0)")
    all_tests_passed &= success
    
    # Test 10: Dashboard pulse
    all_tests_passed &= test_dashboard_pulse(org1['access_token'], "Acme Properties")
    all_tests_passed &= test_dashboard_pulse(org2['access_token'], "XYZ Realty")
    
    # Final Results
    print_section("Test Results")
    if all_tests_passed:
        print("\n🎉 \033[92mALL TESTS PASSED!\033[0m")
        print("\n✓ Multi-tenant data isolation is working correctly")
        print("✓ Organizations cannot access each other's data")
        print("✓ Authentication and authorization are functioning properly")
    else:
        print("\n❌ \033[91mSOME TESTS FAILED!\033[0m")
        print("\nPlease review the errors above.")
        sys.exit(1)
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
