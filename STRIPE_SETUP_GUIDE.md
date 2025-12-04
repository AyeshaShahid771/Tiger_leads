# Stripe Subscription Integration Guide

## Overview

This document explains how to set up and use the Stripe-integrated subscription system for Tigerleads.ai.

## Subscription Tiers

### Tier 1 – Starter

- **Price**: $89/month
- **Credits**: 100 credits/month
- **Seats**: 1 user (no team members)

### Tier 2 – Pro

- **Price**: $199/month
- **Credits**: 250 credits/month
- **Seats**: Up to 3 users

### Tier 3 – Enterprise

- **Price**: $399/month
- **Credits**: 650 credits/month
- **Seats**: Up to 10 users

## Setup Instructions

### 1. Run Database Migrations

```bash
# Add Stripe fields to database
python add_stripe_fields_migration.py

# Update subscription plans with correct pricing
python update_subscription_plans.py
```

### 2. Install Stripe Python Package

```bash
pip install stripe==7.8.0
```

Or if using the requirements.txt:

```bash
pip install -r requirements.txt
```

### 3. Create Stripe Products and Prices

1. **Log in to Stripe Dashboard**: https://dashboard.stripe.com
2. **Go to Products**: Click "Products" in the left sidebar
3. **Create Products for each tier**:

#### Starter Product

- Click "+ Add product"
- Name: "Tigerleads Starter Plan"
- Description: "100 credits per month, single user access"
- Pricing Model: Recurring
- Price: $89.00 USD
- Billing period: Monthly
- Click "Save product"
- **Copy the Price ID** (starts with `price_...`)
- **Copy the Product ID** (starts with `prod_...`)

#### Pro Product

- Click "+ Add product"
- Name: "Tigerleads Pro Plan"
- Description: "250 credits per month, up to 3 team members"
- Pricing Model: Recurring
- Price: $199.00 USD
- Billing period: Monthly
- Click "Save product"
- **Copy the Price ID** and **Product ID**

#### Enterprise Product

- Click "+ Add product"
- Name: "Tigerleads Enterprise Plan"
- Description: "650 credits per month, up to 10 team members"
- Pricing Model: Recurring
- Price: $399.00 USD
- Billing period: Monthly
- Click "Save product"
- **Copy the Price ID** and **Product ID**

### 4. Update Database with Stripe IDs

Connect to your database and run:

```sql
-- Update Starter plan
UPDATE subscriptions
SET stripe_price_id = 'price_YOUR_STARTER_PRICE_ID',
    stripe_product_id = 'prod_YOUR_STARTER_PRODUCT_ID'
WHERE name = 'Starter';

-- Update Pro plan
UPDATE subscriptions
SET stripe_price_id = 'price_YOUR_PRO_PRICE_ID',
    stripe_product_id = 'prod_YOUR_PRO_PRODUCT_ID'
WHERE name = 'Pro';

-- Update Enterprise plan
UPDATE subscriptions
SET stripe_price_id = 'price_YOUR_ENTERPRISE_PRICE_ID',
    stripe_product_id = 'prod_YOUR_ENTERPRISE_PRODUCT_ID'
WHERE name = 'Enterprise';
```

### 5. Set Up Webhook Endpoint

1. **Go to Webhooks** in Stripe Dashboard: https://dashboard.stripe.com/webhooks
2. Click "+ Add endpoint"
3. **Endpoint URL**: `https://your-backend-domain.com/api/subscription/webhook`
4. **Events to listen to**:
   - `checkout.session.completed`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `customer.subscription.deleted`
   - `customer.subscription.updated`
5. Click "Add endpoint"
6. **Copy the Webhook Secret** (starts with `whsec_...`)

### 6. Configure Environment Variables

Add to your `.env` file:

```env
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_xxxxxxxxxxxxxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxx

# Frontend URL for redirects
FRONTEND_URL=https://tigerleads.vercel.app
```

**Note**: Use test keys (`sk_test_...`) for development and live keys (`sk_live_...`) for production.

## API Endpoints

### 1. Get Available Subscription Plans

```http
GET /api/subscription/plans
Authorization: Bearer <token>
```

**Response**:

```json
[
  {
    "id": 1,
    "name": "Starter",
    "price": "$89/month",
    "credits": 100,
    "max_seats": 1,
    "stripe_price_id": "price_xxxxx",
    "stripe_product_id": "prod_xxxxx"
  },
  {
    "id": 2,
    "name": "Pro",
    "price": "$199/month",
    "credits": 250,
    "max_seats": 3,
    "stripe_price_id": "price_yyyyy",
    "stripe_product_id": "prod_yyyyy"
  },
  {
    "id": 3,
    "name": "Enterprise",
    "price": "$399/month",
    "credits": 650,
    "max_seats": 10,
    "stripe_price_id": "price_zzzzz",
    "stripe_product_id": "prod_zzzzz"
  }
]
```

### 2. Create Checkout Session (Subscribe)

```http
POST /api/subscription/create-checkout-session
Authorization: Bearer <token>
Content-Type: application/json

{
  "subscription_id": 2
}
```

**Response**:

```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_...",
  "session_id": "cs_test_xxxxx"
}
```

**Frontend Flow**:

1. User clicks "Subscribe to Pro Plan"
2. Frontend calls this endpoint
3. Frontend redirects user to `checkout_url`
4. User enters payment details on Stripe's page
5. After payment, Stripe redirects to success page
6. Webhook activates subscription in background

### 3. Get Current Subscription

```http
GET /api/subscription/my-subscription
Authorization: Bearer <token>
```

**Response**:

```json
{
  "id": 1,
  "user_id": 123,
  "subscription_id": 2,
  "current_credits": 250,
  "total_spending": 50,
  "seats_used": 1,
  "subscription_start_date": "2025-12-01T00:00:00",
  "subscription_renew_date": "2025-12-31T00:00:00",
  "is_active": true,
  "stripe_subscription_id": "sub_xxxxx",
  "subscription_status": "active"
}
```

### 4. Get Wallet Info

```http
GET /api/subscription/wallet
Authorization: Bearer <token>
```

**Response**:

```json
{
  "current_credits": 250,
  "total_spending": 50,
  "subscription": "Pro",
  "subscription_renew_date": "2025-12-31T00:00:00",
  "unlocked_leads": 10,
  "spending_history": [
    {
      "job_id": 456,
      "credits_spent": 5,
      "unlocked_at": "2025-12-15T10:30:00"
    }
  ],
  "subscription_status": "active",
  "is_sub_user": false
}
```

### 5. Cancel Subscription

```http
POST /api/subscription/cancel-subscription
Authorization: Bearer <token>
```

**Response**:

```json
{
  "message": "Subscription will be canceled at the end of the current billing period",
  "renew_date": "2025-12-31T00:00:00"
}
```

### 6. Reactivate Subscription

```http
POST /api/subscription/reactivate-subscription
Authorization: Bearer <token>
```

**Response**:

```json
{
  "message": "Subscription has been reactivated and will continue automatically",
  "renew_date": "2025-12-31T00:00:00"
}
```

### 7. Update Payment Method

```http
POST /api/subscription/update-payment-method
Authorization: Bearer <token>
```

**Response**:

```json
{
  "portal_url": "https://billing.stripe.com/p/session/xxxxx"
}
```

**Frontend Flow**:

1. User clicks "Update Payment Method"
2. Frontend calls this endpoint
3. Frontend redirects user to `portal_url`
4. User updates card on Stripe's Billing Portal
5. Stripe redirects back to your app

### 8. Webhook Endpoint (For Stripe)

```http
POST /api/subscription/webhook
Stripe-Signature: <stripe_signature_header>
Content-Type: application/json

<stripe_event_payload>
```

**Note**: This endpoint is called by Stripe, not your frontend.

## Payment Flow Diagrams

### First-Time Subscription

```
User → Frontend → Backend API → Stripe API → Stripe Checkout Page
                                                      ↓
                                                User enters card
                                                      ↓
                                        Payment processed by Stripe
                                                      ↓
Webhook received ← Backend API ← Stripe sends webhook
     ↓
Database updated
Credits added
Seats activated
     ↓
Email sent to user
```

### Monthly Auto-Renewal

```
Billing date arrives
     ↓
Stripe automatically charges card
     ↓
Stripe sends webhook (invoice.payment_succeeded)
     ↓
Backend receives webhook
     ↓
Database updated:
- Credits reset to plan amount
- Renewal date extended
     ↓
Confirmation email sent
```

### Payment Failure

```
Billing date arrives
     ↓
Stripe attempts to charge card → FAILS
     ↓
Stripe sends webhook (invoice.payment_failed)
     ↓
Backend receives webhook
     ↓
Database updated:
- Status → "past_due"
- is_active → false
     ↓
Urgent email sent to user
     ↓
Stripe retries payment (multiple attempts over days)
     ↓
If all retries fail → Subscription canceled
```

## Subscription Status Values

- **`active`**: Subscription is paid and active
- **`past_due`**: Payment failed, awaiting retry
- **`canceled`**: Subscription has been canceled
- **`incomplete`**: Initial payment is pending
- **`incomplete_expired`**: Initial payment failed
- **`trialing`**: In trial period (if you enable trials)
- **`unpaid`**: Payment failed after all retries

## Testing with Stripe Test Mode

Use these test card numbers:

### Successful Payment

- **Card**: `4242 4242 4242 4242`
- **Exp**: Any future date
- **CVC**: Any 3 digits
- **ZIP**: Any 5 digits

### Payment Requires Authentication

- **Card**: `4000 0025 0000 3155`

### Payment Declined

- **Card**: `4000 0000 0000 9995`

### Insufficient Funds

- **Card**: `4000 0000 0000 9995`

## Important Notes

1. **Sub-users share the main account's subscription** - Only main account holders can subscribe/cancel
2. **Credits are shared** - All team members use credits from the same pool
3. **Automatic renewals** - Subscriptions auto-renew monthly
4. **Prorated upgrades** - Stripe automatically handles mid-cycle plan changes
5. **Webhooks are critical** - Without webhooks, subscriptions won't activate properly

## Security Considerations

1. Always verify webhook signatures
2. Never expose Stripe secret keys to frontend
3. Use HTTPS for webhook endpoint
4. Validate user permissions before allowing subscription changes
5. Test thoroughly in Stripe test mode before going live

## Troubleshooting

### Webhook not received

- Check webhook endpoint URL is correct
- Verify webhook secret matches `.env`
- Check server logs for errors
- Test webhook in Stripe Dashboard

### Payment fails immediately

- Check if test card is being used
- Verify Stripe API keys are correct
- Check for any error logs

### Subscription not activating

- Verify webhook is set up correctly
- Check database for subscription records
- Review server logs for webhook processing errors

## Support

For issues with Stripe integration:

1. Check Stripe Dashboard logs
2. Review application server logs
3. Test with Stripe CLI for local webhook testing
4. Contact Stripe support for payment-specific issues
