"""
Tests for billing functionality including subscription upgrades.
"""

import pytest
from unittest.mock import patch, MagicMock


def test_upgrade_subscription_success(client, pro_org):
    """Test successful subscription upgrade."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}
    
    # Mock Stripe API calls and PRICE_MAP
    with patch('stripe.Subscription.retrieve') as mock_retrieve, \
         patch('stripe.Subscription.modify') as mock_modify, \
         patch('main.PRICE_MAP', {
             'core': 'price_core123',
             'growth': 'price_growth123',
             'premium': 'price_premium123'
         }):
        
        # Mock the subscription retrieval
        mock_sub = MagicMock()
        mock_item = MagicMock()
        mock_item.id = "si_test123"
        mock_sub.items.data = [mock_item]
        mock_retrieve.return_value = mock_sub
        
        # Mock the subscription modification
        mock_modify.return_value = MagicMock()
        
        # Attempt upgrade to premium
        response = client.post("/api/billing/upgrade", headers=headers, json={
            "plan": "premium"
        })
        
        assert response.status_code == 200
        assert "upgraded to premium plan" in response.json()["message"]
        
        # Verify Stripe calls were made
        mock_retrieve.assert_called_once_with(pro_org['subscription'].stripe_subscription_id)
        mock_modify.assert_called_once()


def test_upgrade_subscription_invalid_plan(client, pro_org):
    """Test upgrade with invalid plan."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}
    
    response = client.post("/api/billing/upgrade", headers=headers, json={
        "plan": "invalid_plan"
    })
    
    assert response.status_code == 400
    assert "Invalid plan" in response.json()["detail"]


def test_upgrade_subscription_no_subscription(client, free_org):
    """Test upgrade attempt by organization without subscription."""
    headers = {"Authorization": f"Bearer {free_org['token']}"}
    
    response = client.post("/api/billing/upgrade", headers=headers, json={
        "plan": "growth"
    })
    
    assert response.status_code == 404
    assert "No active subscription found" in response.json()["detail"]


def test_upgrade_subscription_stripe_error(client, pro_org):
    """Test upgrade when Stripe API fails."""
    headers = {"Authorization": f"Bearer {pro_org['token']}"}
    
    with patch('stripe.Subscription.retrieve') as mock_retrieve, \
         patch('stripe.Subscription.modify') as mock_modify, \
         patch('main.PRICE_MAP', {
             'core': 'price_core123',
             'growth': 'price_growth123',
             'premium': 'price_premium123'
         }):
        
        # Mock successful retrieval
        mock_sub = MagicMock()
        mock_item = MagicMock()
        mock_item.id = "si_test123"
        mock_sub.items.data = [mock_item]
        mock_retrieve.return_value = mock_sub
        
        # Mock Stripe error on modify
        import stripe
        mock_modify.side_effect = stripe.error.StripeError("Card declined")
        
        response = client.post("/api/billing/upgrade", headers=headers, json={
            "plan": "premium"
        })
        
        assert response.status_code == 400
        assert "Card declined" in response.json()["detail"]