# Credit Management System Documentation

## Overview

TigerLeads implements a comprehensive credit management system with three key features:

1. **Introductory Trial**: 140 free credits upon signup, expires in 14 days if unused
2. **Auto-Renew & Carryover**: Credits roll over month-to-month while subscription is active
3. **Lapse Policy**: Credits freeze (not deleted) if subscription lapses; reactivation within 30 days restores them

---

## Trial Credits

### How It Works

When a new user signs up and verifies their email:
- A `Subscriber` record is created automatically
- `current_credits` = **140** (free trial credits)
- `trial_credits_expires_at` = signup date + **14 days**
- `subscription_status` = `"trial"`

### Trial Expiration

A background service runs **daily** to check for expired trials:
- If `trial_credits_expires_at` <= current time AND no paid subscription
- Credits are zeroed out: `current_credits = 0`
- Status changes to `"trial_expired"`
- User must upgrade to paid subscription to get more credits

### Database Fields

```python
trial_credits = 140                    # Initial trial amount
trial_credits_expires_at = datetime    # 14 days from signup
trial_credits_used = True              # Flag indicating trial was claimed
```

---

## Credit Rollover (Carryover)

### How It Works

When a paid subscription renews (Stripe webhook: `invoice.payment_succeeded`):
- **OLD BEHAVIOR**: `current_credits = subscription_plan.credits` (replaced credits)
- **NEW BEHAVIOR**: `current_credits += subscription_plan.credits` (adds to existing)

This allows credits to **accumulate month-to-month** as long as the subscription remains active.

### Example

- User has 50 unused credits from last month
- Subscription renews with 200 credits/month plan
- After renewal: `current_credits = 50 + 200 = 250`

### Code Location

File: [subscription.py](src/app/api/endpoints/subscription.py#L1015-L1020)

```python
# Update subscriber state with credit rollover
if subscription_plan:
    # Add credits instead of replacing (rollover)
    subscriber.current_credits += subscription_plan.credits
```

---

## Credit Freeze & Restore

### Freeze on Subscription Lapse

When a subscription is canceled or ends (Stripe webhook: `customer.subscription.deleted`):
- Current credits are **frozen**, not deleted
- `frozen_credits = current_credits`
- `current_credits = 0`
- `frozen_at = datetime.now()`
- `is_active = False`
- `subscription_status = "canceled"`

### Restore Within 30 Days

If the user reactivates their subscription within **30 days**:
- Frozen credits are **restored**: `current_credits += frozen_credits`
- Frozen tracking is cleared: `frozen_credits = 0`, `frozen_at = None`
- New subscription credits are added on top

### After 30 Days

If the user waits **more than 30 days** to reactivate:
- Frozen credits are **permanently lost**
- They start fresh with only the new subscription credits

### Database Fields

```python
frozen_credits = 0           # Credits frozen when subscription lapsed
frozen_at = datetime         # When subscription was canceled
last_active_date = datetime  # Last date subscription was active
```

### Code Location

**Freeze on cancellation**: [subscription.py](src/app/api/endpoints/subscription.py#L1365-L1370)

```python
# Freeze credits when subscription is canceled
subscriber.frozen_credits = subscriber.current_credits
subscriber.frozen_at = datetime.utcnow()
subscriber.current_credits = 0
```

**Restore on reactivation**: [subscription.py](src/app/api/endpoints/subscription.py#L1019-L1027)

```python
# Clear frozen credits if reactivating within 30 days
if subscriber.frozen_credits > 0 and subscriber.frozen_at:
    days_since_freeze = (datetime.utcnow() - subscriber.frozen_at).days
    if days_since_freeze <= 30:
        # Restore frozen credits
        subscriber.current_credits += subscriber.frozen_credits
```

---

## Database Schema

### New Columns in `subscribers` Table

| Column | Type | Description |
|--------|------|-------------|
| `trial_credits` | Integer | Number of trial credits (default: 140) |
| `trial_credits_expires_at` | DateTime | When trial credits expire (14 days from signup) |
| `trial_credits_used` | Boolean | Whether trial has been claimed |
| `frozen_credits` | Integer | Credits frozen when subscription lapsed |
| `frozen_at` | DateTime | When subscription was canceled |
| `last_active_date` | DateTime | Last date subscription was active |

---

## Background Services

### Trial Expiry Service

- **File**: [trial_expiry_service.py](src/app/services/trial_expiry_service.py)
- **Frequency**: Runs every **24 hours**
- **Function**: Expires trial credits after 14 days

**Startup**: Automatically starts when FastAPI server starts ([main.py](src/app/main.py#L90-L96))

```python
@app.on_event("startup")
async def startup_event():
    await trial_expiry_service.start()
```

---

## Migration

### Run Database Migration

Before deploying, run the migration script to add new columns:

```bash
python add_credit_management_columns.py
```

This adds all required columns to the `subscribers` table.

**Migration file**: [add_credit_management_columns.py](add_credit_management_columns.py)

---

## User Journey Examples

### Example 1: Trial User → Paid Subscriber

1. User signs up → Gets **140 trial credits** (expires in 14 days)
2. User verifies email → Trial starts
3. Day 5: User upgrades to $50/month plan (200 credits)
   - Current credits: `140 + 200 = 340`
4. Day 35: Subscription renews
   - User has 100 credits left
   - After renewal: `100 + 200 = 300` (rollover)

### Example 2: Trial Expiration

1. User signs up → Gets **140 trial credits** (expires in 14 days)
2. Day 15: Trial expires → Credits zeroed out
3. User must upgrade to paid plan to get more credits

### Example 3: Subscription Lapse & Restore

1. User has paid subscription with **150 unused credits**
2. Subscription ends (payment failed or user canceled)
   - `frozen_credits = 150`
   - `current_credits = 0`
3. Day 10: User reactivates subscription (200 credits/month)
   - Restore frozen credits: `current_credits = 150 + 200 = 350`
4. Day 35: If user had waited **35 days** to reactivate
   - Frozen credits lost (30-day window passed)
   - Only new subscription credits: `current_credits = 200`

---

## Testing

### Test Trial Credits on Signup

1. Create new account and verify email
2. Check `subscribers` table:
   ```sql
   SELECT current_credits, trial_credits, trial_credits_expires_at, subscription_status 
   FROM subscribers 
   WHERE user_id = <user_id>;
   ```
3. Should show:
   - `current_credits = 140`
   - `trial_credits_expires_at` = 14 days from now
   - `subscription_status = 'trial'`

### Test Credit Rollover

1. Create paid subscription via Stripe
2. Wait for renewal (or trigger manually via Stripe dashboard)
3. Check credits before and after renewal
4. Verify credits were **added**, not replaced

### Test Credit Freeze/Restore

1. Create paid subscription with credits
2. Cancel subscription via Stripe
3. Check `frozen_credits` field (should equal old `current_credits`)
4. Reactivate within 30 days
5. Verify frozen credits were restored

---

## API Endpoints

No new endpoints were added. All logic is handled automatically via:

1. **Signup/Verification**: [auth.py](src/app/api/endpoints/auth.py#L246-L263)
2. **Subscription Webhooks**: [subscription.py](src/app/api/endpoints/subscription.py)
   - `invoice.payment_succeeded` → Credit rollover
   - `customer.subscription.deleted` → Credit freeze

---

## Configuration

All credit amounts and timeframes are configurable:

| Setting | Location | Default |
|---------|----------|---------|
| Trial credits | [auth.py#L250](src/app/api/endpoints/auth.py#L250) | 140 |
| Trial duration | [auth.py#L252](src/app/api/endpoints/auth.py#L252) | 14 days |
| Restore window | [subscription.py#L1022](src/app/api/endpoints/subscription.py#L1022) | 30 days |
| Expiry check frequency | [trial_expiry_service.py#L53](src/app/services/trial_expiry_service.py#L53) | 24 hours |

---

## Monitoring & Logs

### Log Examples

**Trial creation**:
```
Trial subscriber created with 140 credits for user: user@example.com
```

**Trial expiration**:
```
Expired trial for subscriber 123: Removed 140 credits
```

**Credit rollover**:
```
Subscriber 456 renewal: added 200 credits (rollover enabled)
```

**Credit freeze**:
```
Canceled subscription for user user@example.com. Froze 150 credits.
```

**Credit restore**:
```
Restored 150 frozen credits for subscriber 456
```

---

## Troubleshooting

### Trial credits not appearing on signup

- Check email verification completed successfully
- Verify `Subscriber` record created in database
- Check logs for "Trial subscriber created" message

### Credits being replaced instead of rolling over

- Verify migration script was run
- Check `subscription.py` line 1016-1017 uses `+=` not `=`
- Check Stripe webhook is triggering `invoice.payment_succeeded`

### Frozen credits not restoring

- Verify reactivation happened within 30 days
- Check `frozen_at` timestamp in database
- Check logs for "Restored X frozen credits" message

---

## Support

For issues or questions, contact the development team or check:
- [Subscription API Documentation](SUBSCRIPTION_JOBS_API.md)
- [Stripe Setup Guide](STRIPE_SETUP_GUIDE.md)


































































































































































































































































































































- [Stripe Setup Guide](STRIPE_SETUP_GUIDE.md)- [Subscription API Documentation](SUBSCRIPTION_JOBS_API.md)For issues or questions, contact the development team or check:## Support---- Check logs for "Restored X frozen credits" message- Check `frozen_at` timestamp in database- Verify reactivation happened within 30 days### Frozen credits not restoring- Check Stripe webhook is triggering `invoice.payment_succeeded`- Check `subscription.py` line 1016-1017 uses `+=` not `=`- Verify migration script was run### Credits being replaced instead of rolling over- Check logs for "Trial subscriber created" message- Verify `Subscriber` record created in database- Check email verification completed successfully### Trial credits not appearing on signup## Troubleshooting---```Restored 150 frozen credits for subscriber 456```**Credit restore**:```Canceled subscription for user user@example.com. Froze 150 credits.```**Credit freeze**:```Subscriber 456 renewal: added 200 credits (rollover enabled)```**Credit rollover**:```Expired trial for subscriber 123: Removed 140 credits```**Trial expiration**:```Trial subscriber created with 140 credits for user: user@example.com```**Trial creation**:### Log Examples## Monitoring & Logs---| Expiry check frequency | [trial_expiry_service.py#L53](src/app/services/trial_expiry_service.py#L53) | 24 hours || Restore window | [subscription.py#L1022](src/app/api/endpoints/subscription.py#L1022) | 30 days || Trial duration | [auth.py#L252](src/app/api/endpoints/auth.py#L252) | 14 days || Trial credits | [auth.py#L250](src/app/api/endpoints/auth.py#L250) | 140 ||---------|----------|---------|| Setting | Location | Default |All credit amounts and timeframes are configurable:## Configuration---   - `customer.subscription.deleted` → Credit freeze   - `invoice.payment_succeeded` → Credit rollover2. **Subscription Webhooks**: [subscription.py](src/app/api/endpoints/subscription.py)1. **Signup/Verification**: [auth.py](src/app/api/endpoints/auth.py#L246-L263)No new endpoints were added. All logic is handled automatically via:## API Endpoints---5. Verify frozen credits were restored4. Reactivate within 30 days3. Check `frozen_credits` field (should equal old `current_credits`)2. Cancel subscription via Stripe1. Create paid subscription with credits### Test Credit Freeze/Restore4. Verify credits were **added**, not replaced3. Check credits before and after renewal2. Wait for renewal (or trigger manually via Stripe dashboard)1. Create paid subscription via Stripe### Test Credit Rollover   - `subscription_status = 'trial'`   - `trial_credits_expires_at` = 14 days from now   - `current_credits = 140`3. Should show:   ```   WHERE user_id = <user_id>;   FROM subscribers    SELECT current_credits, trial_credits, trial_credits_expires_at, subscription_status    ```sql2. Check `subscribers` table:1. Create new account and verify email### Test Trial Credits on Signup## Testing---   - Only new subscription credits: `current_credits = 200`   - Frozen credits lost (30-day window passed)4. Day 35: If user had waited **35 days** to reactivate   - Restore frozen credits: `current_credits = 150 + 200 = 350`3. Day 10: User reactivates subscription (200 credits/month)   - `current_credits = 0`   - `frozen_credits = 150`2. Subscription ends (payment failed or user canceled)1. User has paid subscription with **150 unused credits**### Example 3: Subscription Lapse & Restore3. User must upgrade to paid plan to get more credits2. Day 15: Trial expires → Credits zeroed out1. User signs up → Gets **140 trial credits** (expires in 14 days)### Example 2: Trial Expiration   - After renewal: `100 + 200 = 300` (rollover)   - User has 100 credits left4. Day 35: Subscription renews   - Current credits: `140 + 200 = 340`3. Day 5: User upgrades to $50/month plan (200 credits)2. User verifies email → Trial starts1. User signs up → Gets **140 trial credits** (expires in 14 days)### Example 1: Trial User → Paid Subscriber## User Journey Examples---**Migration file**: [add_credit_management_columns.py](add_credit_management_columns.py)This adds all required columns to the `subscribers` table.```python add_credit_management_columns.py```bashBefore deploying, run the migration script to add new columns:### Run Database Migration## Migration---```    await trial_expiry_service.start()async def startup_event():@app.on_event("startup")```python**Startup**: Automatically starts when FastAPI server starts ([main.py](src/app/main.py#L90-L96))- **Function**: Expires trial credits after 14 days- **Frequency**: Runs every **24 hours**- **File**: [trial_expiry_service.py](src/app/services/trial_expiry_service.py)### Trial Expiry Service## Background Services---| `last_active_date` | DateTime | Last date subscription was active || `frozen_at` | DateTime | When subscription was canceled || `frozen_credits` | Integer | Credits frozen when subscription lapsed || `trial_credits_used` | Boolean | Whether trial has been claimed || `trial_credits_expires_at` | DateTime | When trial credits expire (14 days from signup) || `trial_credits` | Integer | Number of trial credits (default: 140) ||--------|------|-------------|| Column | Type | Description |### New Columns in `subscribers` Table## Database Schema---```        subscriber.current_credits += subscriber.frozen_credits        # Restore frozen credits    if days_since_freeze <= 30:    days_since_freeze = (datetime.utcnow() - subscriber.frozen_at).daysif subscriber.frozen_credits > 0 and subscriber.frozen_at:# Clear frozen credits if reactivating within 30 days```python**Restore on reactivation**: [subscription.py](src/app/api/endpoints/subscription.py#L1019-L1027)```subscriber.current_credits = 0subscriber.frozen_at = datetime.utcnow()subscriber.frozen_credits = subscriber.current_credits# Freeze credits when subscription is canceled```python**Freeze on cancellation**: [subscription.py](src/app/api/endpoints/subscription.py#L1365-L1370)### Code Location```last_active_date = datetime  # Last date subscription was activefrozen_at = datetime         # When subscription was canceledfrozen_credits = 0           # Credits frozen when subscription lapsed```python### Database Fields- They start fresh with only the new subscription credits- Frozen credits are **permanently lost**If the user waits **more than 30 days** to reactivate:### After 30 Days- New subscription credits are added on top- Frozen tracking is cleared: `frozen_credits = 0`, `frozen_at = None`- Frozen credits are **restored**: `current_credits += frozen_credits`If the user reactivates their subscription within **30 days**:### Restore Within 30 Days- `subscription_status = "canceled"`- `is_active = False`- `frozen_at = datetime.now()`- `current_credits = 0`- `frozen_credits = current_credits`- Current credits are **frozen**, not deletedWhen a subscription is canceled or ends (Stripe webhook: `customer.subscription.deleted`):### Freeze on Subscription Lapse## Credit Freeze & Restore---```    subscriber.current_credits += subscription_plan.credits    # Add credits instead of replacing (rollover)if subscription_plan:# Update subscriber state with credit rollover```pythonFile: [subscription.py](src/app/api/endpoints/subscription.py#L1015-L1020)### Code Location- After renewal: `current_credits = 50 + 200 = 250`- Subscription renews with 200 credits/month plan- User has 50 unused credits from last month### ExampleThis allows credits to **accumulate month-to-month** as long as the subscription remains active.- **NEW BEHAVIOR**: `current_credits += subscription_plan.credits` (adds to existing)- **OLD BEHAVIOR**: `current_credits = subscription_plan.credits` (replaced credits)When a paid subscription renews (Stripe webhook: `invoice.payment_succeeded`):### How It Works## Credit Rollover (Carryover)---```trial_credits_used = True              # Flag indicating trial was claimedtrial_credits_expires_at = datetime    # 14 days from signuptrial_credits = 140                    # Initial trial amount```python### Database Fields- User must upgrade to paid subscription to get more credits- Status changes to `"trial_expired"`- Credits are zeroed out: `current_credits = 0`- If `trial_credits_expires_at` <= current time AND no paid subscriptionA background service runs **daily** to check for expired trials:### Trial Expiration- `subscription_status` = `"trial"`- `trial_credits_expires_at` = signup date + **14 days**- `current_credits` = **140** (free trial credits)- A `Subscriber` record is created automaticallyWhen a new user signs up and verifies their email:### How It Works## Trial Credits---3. **Lapse Policy**: Credits freeze (not deleted) if subscription lapses; reactivation within 30 days restores them2. **Auto-Renew & Carryover**: Credits roll over month-to-month while subscription is active1. **Introductory Trial**: 140 free credits upon signup, expires in 14 days if unusedTigerLeads implements a comprehensive credit management system with three key features:## Overview
## Overview

TigerLeads implements a comprehensive credit management system with three key features:

1. **Introductory Trial**: 140 free credits upon signup, expires in 14 days if unused
2. **Auto-Renew & Carryover**: Credits roll over month-to-month while subscription is active
3. **Lapse Policy**: Credits freeze (not deleted) if subscription lapses; reactivation within 30 days restores them

---

## Trial Credits

### How It Works

When a new user signs up and verifies their email:
- A `Subscriber` record is created automatically
- `current_credits` = **140** (free trial credits)
- `trial_credits_expires_at` = signup date + **14 days**
- `subscription_status` = `"trial"`

### Trial Expiration

A background service runs **daily** to check for expired trials:
- If `trial_credits_expires_at` <= current time AND no paid subscription
- Credits are zeroed out: `current_credits = 0`
- Status changes to `"trial_expired"`
- User must upgrade to paid subscription to get more credits

### Database Fields

```python
trial_credits = 140                    # Initial trial amount
trial_credits_expires_at = datetime    # 14 days from signup
trial_credits_used = True              # Flag indicating trial was claimed
```

---

## Credit Rollover (Carryover)

### How It Works

When a paid subscription renews (Stripe webhook: `invoice.payment_succeeded`):
- **OLD BEHAVIOR**: `current_credits = subscription_plan.credits` (replaced credits)
- **NEW BEHAVIOR**: `current_credits += subscription_plan.credits` (adds to existing)

This allows credits to **accumulate month-to-month** as long as the subscription remains active.

### Example

- User has 50 unused credits from last month
- Subscription renews with 200 credits/month plan
- After renewal: `current_credits = 50 + 200 = 250`

### Code Location

File: [subscription.py](src/app/api/endpoints/subscription.py#L1015-L1020)

```python
# Update subscriber state with credit rollover
if subscription_plan:
    # Add credits instead of replacing (rollover)
    subscriber.current_credits += subscription_plan.credits
```

---

## Credit Freeze & Restore

### Freeze on Subscription Lapse

When a subscription is canceled or ends (Stripe webhook: `customer.subscription.deleted`):
- Current credits are **frozen**, not deleted
- `frozen_credits = current_credits`
- `current_credits = 0`
- `frozen_at = datetime.now()`
- `is_active = False`
- `subscription_status = "canceled"`

### Restore Within 30 Days

If the user reactivates their subscription within **30 days**:
- Frozen credits are **restored**: `current_credits += frozen_credits`
- Frozen tracking is cleared: `frozen_credits = 0`, `frozen_at = None`
- New subscription credits are added on top

### After 30 Days

If the user waits **more than 30 days** to reactivate:
- Frozen credits are **permanently lost**
- They start fresh with only the new subscription credits

### Database Fields

```python
frozen_credits = 0           # Credits frozen when subscription lapsed
frozen_at = datetime         # When subscription was canceled
last_active_date = datetime  # Last date subscription was active
```

### Code Location

**Freeze on cancellation**: [subscription.py](src/app/api/endpoints/subscription.py#L1365-L1370)

```python
# Freeze credits when subscription is canceled
subscriber.frozen_credits = subscriber.current_credits
subscriber.frozen_at = datetime.utcnow()
subscriber.current_credits = 0
```

**Restore on reactivation**: [subscription.py](src/app/api/endpoints/subscription.py#L1019-L1027)

```python
# Clear frozen credits if reactivating within 30 days
if subscriber.frozen_credits > 0 and subscriber.frozen_at:
    days_since_freeze = (datetime.utcnow() - subscriber.frozen_at).days
    if days_since_freeze <= 30:
        # Restore frozen credits
        subscriber.current_credits += subscriber.frozen_credits
```

---

## Database Schema

### New Columns in `subscribers` Table

| Column | Type | Description |
|--------|------|-------------|
| `trial_credits` | Integer | Number of trial credits (default: 140) |
| `trial_credits_expires_at` | DateTime | When trial credits expire (14 days from signup) |
| `trial_credits_used` | Boolean | Whether trial has been claimed |
| `frozen_credits` | Integer | Credits frozen when subscription lapsed |
| `frozen_at` | DateTime | When subscription was canceled |
| `last_active_date` | DateTime | Last date subscription was active |

---

## Background Services

### Trial Expiry Service

- **File**: [trial_expiry_service.py](src/app/services/trial_expiry_service.py)
- **Frequency**: Runs every **24 hours**
- **Function**: Expires trial credits after 14 days

**Startup**: Automatically starts when FastAPI server starts ([main.py](src/app/main.py#L90-L96))

```python
@app.on_event("startup")
async def startup_event():
    await trial_expiry_service.start()
```

---

## Migration

### Run Database Migration

Before deploying, run the migration script to add new columns:

```bash
python add_credit_management_columns.py
```

This adds all required columns to the `subscribers` table.

**Migration file**: [add_credit_management_columns.py](add_credit_management_columns.py)

---

## User Journey Examples

### Example 1: Trial User → Paid Subscriber

1. User signs up → Gets **140 trial credits** (expires in 14 days)
2. User verifies email → Trial starts
3. Day 5: User upgrades to $50/month plan (200 credits)
   - Current credits: `140 + 200 = 340`
4. Day 35: Subscription renews
   - User has 100 credits left
   - After renewal: `100 + 200 = 300` (rollover)

### Example 2: Trial Expiration

1. User signs up → Gets **140 trial credits** (expires in 14 days)
2. Day 15: Trial expires → Credits zeroed out
3. User must upgrade to paid plan to get more credits

### Example 3: Subscription Lapse & Restore

1. User has paid subscription with **150 unused credits**
2. Subscription ends (payment failed or user canceled)
   - `frozen_credits = 150`
   - `current_credits = 0`
3. Day 10: User reactivates subscription (200 credits/month)
   - Restore frozen credits: `current_credits = 150 + 200 = 350`
4. Day 35: If user had waited **35 days** to reactivate
   - Frozen credits lost (30-day window passed)
   - Only new subscription credits: `current_credits = 200`

---

## Testing

### Test Trial Credits on Signup

1. Create new account and verify email
2. Check `subscribers` table:
   ```sql
   SELECT current_credits, trial_credits, trial_credits_expires_at, subscription_status 
   FROM subscribers 
   WHERE user_id = <user_id>;
   ```
3. Should show:
   - `current_credits = 140`
   - `trial_credits_expires_at` = 14 days from now
   - `subscription_status = 'trial'`

### Test Credit Rollover

1. Create paid subscription via Stripe
2. Wait for renewal (or trigger manually via Stripe dashboard)
3. Check credits before and after renewal
4. Verify credits were **added**, not replaced

### Test Credit Freeze/Restore

1. Create paid subscription with credits
2. Cancel subscription via Stripe
3. Check `frozen_credits` field (should equal old `current_credits`)
4. Reactivate within 30 days
5. Verify frozen credits were restored

---

## API Endpoints

No new endpoints were added. All logic is handled automatically via:

1. **Signup/Verification**: [auth.py](src/app/api/endpoints/auth.py#L246-L263)
2. **Subscription Webhooks**: [subscription.py](src/app/api/endpoints/subscription.py)
   - `invoice.payment_succeeded` → Credit rollover
   - `customer.subscription.deleted` → Credit freeze

---

## Configuration

All credit amounts and timeframes are configurable:

| Setting | Location | Default |
|---------|----------|---------|
| Trial credits | [auth.py#L250](src/app/api/endpoints/auth.py#L250) | 140 |
| Trial duration | [auth.py#L252](src/app/api/endpoints/auth.py#L252) | 14 days |
| Restore window | [subscription.py#L1022](src/app/api/endpoints/subscription.py#L1022) | 30 days |
| Expiry check frequency | [trial_expiry_service.py#L53](src/app/services/trial_expiry_service.py#L53) | 24 hours |

---

## Monitoring & Logs

### Log Examples

**Trial creation**:
```
Trial subscriber created with 140 credits for user: user@example.com
```

**Trial expiration**:
```
Expired trial for subscriber 123: Removed 140 credits
```

**Credit rollover**:
```
Subscriber 456 renewal: added 200 credits (rollover enabled)
```

**Credit freeze**:
```
Canceled subscription for user user@example.com. Froze 150 credits.
```

**Credit restore**:
```
Restored 150 frozen credits for subscriber 456
```

---

## Troubleshooting

### Trial credits not appearing on signup

- Check email verification completed successfully
- Verify `Subscriber` record created in database
- Check logs for "Trial subscriber created" message

### Credits being replaced instead of rolling over

- Verify migration script was run
- Check `subscription.py` line 1016-1017 uses `+=` not `=`
- Check Stripe webhook is triggering `invoice.payment_succeeded`

### Frozen credits not restoring

- Verify reactivation happened within 30 days
- Check `frozen_at` timestamp in database
- Check logs for "Restored X frozen credits" message

---

## Support

For issues or questions, contact the development team or check:
- [Subscription API Documentation](SUBSCRIPTION_JOBS_API.md)
- [Stripe Setup Guide](STRIPE_SETUP_GUIDE.md)
