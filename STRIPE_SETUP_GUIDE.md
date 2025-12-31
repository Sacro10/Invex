# 🚀 Stripe Setup Guide for INDEX Property Management

This guide will help you set up Stripe billing for your multi-tenant SaaS application.

## 📋 Prerequisites

1. **Stripe Account**: Sign up at [stripe.com](https://stripe.com) if you don't have one
2. **Test Mode**: Use Stripe's test mode for development
3. **Python Environment**: Make sure you have Python and the required dependencies

## 🔧 Step 1: Get Your Stripe API Keys

1. Go to [Stripe Dashboard](https://dashboard.stripe.com)
2. Make sure you're in **Test Mode** (toggle in top-right corner)
3. Go to **Developers** > **API Keys**
4. Copy your **Secret Key** (starts with `sk_test_`)

```bash
export STRIPE_SECRET_KEY=sk_test_your_key_here
```

## 🔧 Step 2: Run the Setup Script

The `stripe_setup.py` script will create all the necessary products and prices:

```bash
cd /path/to/your/project
python stripe_setup.py
```

This will:
- ✅ Create 3 products: Core, Growth, Premium
- ✅ Create prices: $2/unit, $4/unit, $5/unit per month
- ✅ Display the environment variables you need
- ✅ Save configuration to `stripe_config.json`

## 🔧 Step 3: Configure Environment Variables

Add these to your Railway project environment variables:

```bash
# From the setup script output
STRIPE_PRICE_CORE=price_1AbCdEfGhIjKlMn
STRIPE_PRICE_GROWTH=price_2BcDeFgHiJkLmNo
STRIPE_PRICE_PREMIUM=price_3CdEfGhIjKlMnOp

# Your webhook secret (see Step 4)
STRIPE_WEBHOOK_SECRET=whsec_...

# Your app's URL
FRONTEND_URL=https://your-app.railway.app
```

## 🔧 Step 4: Set Up Webhooks

1. In Stripe Dashboard, go to **Developers** > **Webhooks**
2. Click **"Add endpoint"**
3. Set the endpoint URL to: `https://your-app.railway.app/api/billing/webhook`
4. Select these events:
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
5. Click **"Add endpoint"**
6. Copy the **Webhook Secret** (starts with `whsec_`) to your environment variables

## 🔧 Step 5: Test the Integration

1. **Start your server**:
   ```bash
   cd backend
   uvicorn main:app --reload
   ```

2. **Test the billing flow**:
   - Go to `http://localhost:8000/payment.html`
   - Select a plan and enter units
   - Click "Start subscription"
   - You should be redirected to Stripe Checkout
   - Use test card: `4242 4242 4242 4242`
   - Complete the checkout
   - You should return to the success page

3. **Check your database**:
   - A new subscription record should be created
   - The webhook should update subscription status

## 🎯 Plan Details

| Plan    | Price/Unit | Description |
|---------|------------|-------------|
| Core    | $2         | Essential property management features |
| Growth  | $4         | Advanced features with analytics |
| Premium | $5         | Full-featured property management suite |

**Billing**: Monthly subscription, billed per unit (number of units managed)

## 🧪 Testing in Stripe

Use these test cards in Stripe Checkout:
- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Requires Authentication**: `4000 0025 0000 3155`

## 🚀 Going Live

When ready for production:

1. **Switch to Live Mode** in Stripe Dashboard
2. **Update API Keys** to live keys (start with `sk_live_`)
3. **Update Webhook URL** to your production domain
4. **Update Environment Variables** in Railway
5. **Test thoroughly** with live mode (use small amounts)

## 🆘 Troubleshooting

**Webhook not working?**
- Check that the webhook URL is correct
- Verify the webhook secret is set correctly
- Check Railway logs for webhook errors

**Checkout not redirecting?**
- Verify `FRONTEND_URL` is set correctly
- Check that success/cancel URLs are configured

**Database not updating?**
- Check webhook events are being received
- Verify subscription IDs match

**Need help?**
- Check Stripe Dashboard > Events for webhook delivery
- Use Stripe CLI for local webhook testing: `stripe listen --forward-to localhost:8000/api/billing/webhook`

---

🎉 **Your Stripe billing is now set up!** Users can now subscribe to your SaaS with the three pricing tiers.