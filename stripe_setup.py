#!/usr/bin/env python3
"""
Stripe Setup Helper Script

This script helps set up Stripe products and prices for the INDEX Property Management SaaS.
Run this script with your Stripe secret key to create the required products and prices.

Usage:
    export STRIPE_SECRET_KEY=sk_test_...
    python stripe_setup.py

Requirements:
    pip install stripe
"""

import os
import stripe
import json

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
if not stripe.api_key:
    print("❌ Error: STRIPE_SECRET_KEY environment variable not set")
    print("   Please set it with: export STRIPE_SECRET_KEY=sk_test_...")
    exit(1)

def create_product(name, description):
    """Create a Stripe product."""
    try:
        product = stripe.Product.create(
            name=name,
            description=description,
            type="service"
        )
        print(f"✅ Created product: {name} (ID: {product.id})")
        return product.id
    except Exception as e:
        print(f"❌ Error creating product {name}: {e}")
        return None

def create_price(product_id, unit_amount, currency="usd", interval="month"):
    """Create a Stripe price for a product."""
    try:
        price = stripe.Price.create(
            product=product_id,
            unit_amount=unit_amount,  # Amount in cents
            currency=currency,
            recurring={"interval": interval},
            metadata={"unit_based": "true"}
        )
        print(f"✅ Created price: ${unit_amount/100:.2f}/unit/month (ID: {price.id})")
        return price.id
    except Exception as e:
        print(f"❌ Error creating price: {e}")
        return None

def main():
    print("🚀 Setting up Stripe products and prices for INDEX Property Management")
    print("=" * 70)

    # Plan configurations
    plans = [
        {
            "name": "Core Plan",
            "description": "Essential property management features",
            "price_per_unit": 200,  # $2.00 per unit
        },
        {
            "name": "Growth Plan",
            "description": "Advanced property management with analytics",
            "price_per_unit": 400,  # $4.00 per unit
        },
        {
            "name": "Premium Plan",
            "description": "Full-featured property management suite",
            "price_per_unit": 500,  # $5.00 per unit
        }
    ]

    price_ids = {}

    for plan in plans:
        print(f"\n📦 Creating {plan['name']}...")
        product_id = create_product(plan["name"], plan["description"])
        if product_id:
            price_id = create_price(product_id, plan["price_per_unit"])
            if price_id:
                price_ids[plan["name"].lower().replace(" ", "_")] = price_id

    print("\n" + "=" * 70)
    print("🎉 Stripe setup complete!")
    print("\n📋 Add these environment variables to your Railway project:")
    print("# Stripe Configuration")
    for plan_name, price_id in price_ids.items():
        env_var = f"STRIPE_PRICE_{plan_name.upper()}"
        print(f'{env_var}={price_id}')

    print(f"\n# Webhook Secret (get this from Stripe Dashboard > Webhooks)")
    print("# STRIPE_WEBHOOK_SECRET=whsec_...")

    print("\n# Your Stripe Secret Key")
    print(f"STRIPE_SECRET_KEY={stripe.api_key}")

    print("\n# Frontend URL (update for production)")
    print("FRONTEND_URL=https://your-app.railway.app")

    print("\n🔗 Next steps:")
    print("1. Copy the environment variables above to your Railway project")
    print("2. Set up webhooks in Stripe Dashboard pointing to:")
    print("   https://your-app.railway.app/api/billing/webhook")
    print("3. Enable these webhook events:")
    print("   - customer.subscription.created")
    print("   - customer.subscription.updated")
    print("   - customer.subscription.deleted")
    print("4. Test the billing flow!")

    # Save to file for reference
    with open("stripe_config.json", "w") as f:
        json.dump({
            "products": plans,
            "price_ids": price_ids,
            "webhook_url": "https://your-app.railway.app/api/billing/webhook",
            "webhook_events": [
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted"
            ]
        }, f, indent=2)

    print("\n💾 Configuration saved to stripe_config.json")

if __name__ == "__main__":
    main()