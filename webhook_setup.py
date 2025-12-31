#!/usr/bin/env python3
"""
Stripe Webhook Setup Helper

This script helps set up the Stripe webhook for your INDEX Property Management app.
Run this after deploying to Railway to get the webhook secret.

Usage:
    export RAILWAY_APP_URL=https://your-app.railway.app
    python webhook_setup.py

Requirements:
    pip install stripe requests
"""

import os
import json
import requests

# Get the Railway app URL
app_url = os.getenv("RAILWAY_APP_URL")
if not app_url:
    print("❌ Error: RAILWAY_APP_URL environment variable not set")
    print("   Please set it with: export RAILWAY_APP_URL=https://your-app.railway.app")
    exit(1)

webhook_url = f"{app_url}/api/billing/webhook"

print("🔗 Setting up Stripe webhook...")
print(f"   Webhook URL: {webhook_url}")
print()

# Webhook configuration
webhook_config = {
    "url": webhook_url,
    "enabled_events": [
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted"
    ],
    "description": "INDEX Property Management - Subscription Webhooks"
}

print("📋 Webhook Configuration:")
print(f"   URL: {webhook_config['url']}")
print(f"   Events: {', '.join(webhook_config['enabled_events'])}")
print()

print("🚀 Next Steps:")
print("1. Go to https://dashboard.stripe.com/webhooks")
print("2. Click 'Add endpoint'")
print(f"3. Enter URL: {webhook_url}")
print("4. Select these events:")
for event in webhook_config['enabled_events']:
    print(f"   - {event}")
print("5. Click 'Add endpoint'")
print("6. Copy the 'Webhook signing secret' (starts with whsec_)")
print("7. Add STRIPE_WEBHOOK_SECRET to your Railway environment variables")
print()

print("💡 Test the webhook:")
print(f"   curl -X POST {webhook_url} \\")
print("        -H 'Content-Type: application/json' \\")
print("        -d '{\"type\": \"test\", \"data\": {\"test\": true}}'")
print()

# Save configuration
with open("webhook_config.json", "w") as f:
    json.dump(webhook_config, f, indent=2)

print("💾 Configuration saved to webhook_config.json")

print("\n✅ Webhook setup instructions complete!")
print("   Follow the steps above in your Stripe Dashboard.")