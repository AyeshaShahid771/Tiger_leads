# Subscription Add-On System Guide

## Overview
The add-on system allows users to earn and redeem bonus credits and seats based on their subscription tier. Add-ons are tier-specific rewards that users accumulate and then redeem when ready.

## Add-On Types

### 1. Stay Active Bonus (30 credits)
- **Available in**: All tiers (Starter, Professional, Enterprise)
- **Value**: 30 credits
- **Purpose**: Reward for consistent platform engagement

### 2. Bonus Credits (50 credits)
- **Available in**: Professional and Enterprise tiers
- **Value**: 50 credits
- **Purpose**: Additional credit boost for premium users

### 3. Boost Pack (100 credits + 1 seat)
- **Available in**: Professional tier only
- **Value**: 100 credits + 1 additional team seat
- **Purpose**: Team expansion reward for growing businesses

## Tier Configuration

| Tier | ID | Stay Active Bonus | Bonus Credits | Boost Pack |
|------|----|--------------------|---------------|------------|
| Starter | 2 | ✓ | ✗ | ✗ |
| Professional | 3 | ✓ | ✓ | ✓ |
| Enterprise | 4 | ✓ | ✓ | ✗ |

## Database Schema

### Subscriptions Table (New Columns)
```sql
tier_level INTEGER                -- 1=Starter, 2=Professional, 3=Enterprise
has_stay_active_bonus BOOLEAN     -- Whether Stay Active is available
has_bonus_credits BOOLEAN         -- Whether Bonus Credits is available
has_boost_pack BOOLEAN            -- Whether Boost Pack is available
```

### Subscribers Table (New Columns)
```sql
stay_active_credits INTEGER DEFAULT 0           -- Earned but unredeemed Stay Active credits
bonus_credits INTEGER DEFAULT 0                 -- Earned but unredeemed Bonus Credits
boost_pack_credits INTEGER DEFAULT 0            -- Earned but unredeemed Boost Pack credits
boost_pack_seats INTEGER DEFAULT 0              -- Earned but unredeemed Boost Pack seats
last_stay_active_redemption TIMESTAMP           -- Last redemption timestamp
last_bonus_redemption TIMESTAMP                 -- Last redemption timestamp
last_boost_redemption TIMESTAMP                 -- Last redemption timestamp
```

## API Endpoints

### 1. View Available Add-Ons
**GET** `/subscription/my-add-ons`

Returns available add-ons for the current user's subscription tier.

**Response:**
```json
{
  "subscription_tier": "Professional",
  "tier_level": 2,
  "stay_active_bonus": {
    "available": true,
    "credits_earned": 30,
    "credit_value": 30,
    "last_redeemed": "2024-01-15T10:30:00"
  },
  "bonus_credits": {
    "available": true,
    "credits_earned": 50,
    "credit_value": 50,
    "last_redeemed": null
  },
  "boost_pack": {
    "available": true,
    "credits_earned": 100,
    "seats_earned": 1,
    "credit_value": 100,
    "seat_value": 1,
    "last_redeemed": null
  }
}
```

### 2. Redeem Add-On
**POST** `/subscription/redeem-add-on`

Converts earned add-on credits/seats to active credits/seats.

**Request Body:**
```json
{
  "add_on_type": "stay_active_bonus"  // or "bonus_credits" or "boost_pack"
}
```

**Response (Stay Active Bonus):**
```json
{
  "message": "Stay Active Bonus redeemed successfully",
  "credits_added": 30,
  "new_credit_balance": 150,
  "redeemed_at": "2024-01-20T14:25:00"
}
```

**Response (Boost Pack):**
```json
{
  "message": "Boost Pack redeemed successfully",
  "credits_added": 100,
  "seats_added": 1,
  "new_credit_balance": 250,
  "redeemed_at": "2024-01-20T14:30:00",
  "note": "Contact support to activate your additional seat"
}
```

**Error Cases:**
- `400`: No earned credits/seats available
- `403`: Add-on not available for user's tier
- `404`: No subscription found

### 3. Grant Add-On (Admin Only)
**POST** `/subscription/admin/grant-add-on`

Admin endpoint to manually grant add-ons to users.

**Request Body:**
```json
{
  "user_id": 123,
  "add_on_type": "bonus_credits",
  "credits": 50,       // Optional override
  "seats": 1           // Optional, for boost_pack only
}
```

**Response:**
```json
{
  "message": "Granted 50 Bonus Credits to user 123",
  "user_id": 123,
  "add_on_type": "bonus_credits",
  "credits_granted": 50,
  "total_bonus_credits": 50
}
```

## Workflow

### User Workflow
1. **Earn Add-On**: Admin grants add-on or user earns through platform activity
2. **Check Availability**: Call `GET /subscription/my-add-ons` to see earned add-ons
3. **Redeem**: Call `POST /subscription/redeem-add-on` to convert to active credits/seats
4. **Use Credits**: Credits automatically added to `current_credits` for job access

### Admin Workflow
1. **Identify User**: Get user_id from database
2. **Grant Add-On**: Call `POST /subscription/admin/grant-add-on`
3. **Notify User**: User sees earned add-on in their dashboard
4. **User Redeems**: User chooses when to redeem via UI

## Business Logic

### Credit Flow
1. **Earned State**: Credits stored in `stay_active_credits`, `bonus_credits`, or `boost_pack_credits`
2. **Redemption**: User triggers redemption via endpoint
3. **Active State**: Credits moved to `current_credits` for immediate use
4. **Reset**: Earned amount reset to 0, redemption timestamp recorded

### Seat Management
- Boost Pack seats tracked in `boost_pack_seats`
- Admin manually updates `max_seats` after redemption
- Prevents automatic team size changes

## Implementation Notes

### Why Separate Columns? (Approach 1)
- **Clarity**: Each add-on type has dedicated columns
- **Performance**: Direct column queries faster than JSON parsing
- **Validation**: Database-level type checking
- **Limited Types**: Only 3 add-on types, not dynamic

### Redemption Tracking
- `last_*_redemption` timestamps prevent abuse
- Can implement cooldown periods if needed
- Audit trail for support inquiries

### Tier Changes
- If user downgrades tier, unavailable add-ons remain earned
- User cannot redeem if add-on not available in current tier
- Prevents loss of earned rewards during tier transitions

## Migration

Run the migration script:
```bash
python add_addon_columns.py
```

The script:
1. Checks for existing columns (idempotent)
2. Adds 4 columns to `subscriptions` table
3. Adds 7 columns to `subscribers` table
4. Updates tier configurations for 3 plans
5. Displays configuration summary

## Testing Guide

### Test 1: View Add-Ons (No Subscription)
```bash
curl -X GET http://localhost:8000/subscription/my-add-ons \
  -H "Authorization: Bearer {token}"
```
Expected: 404 error

### Test 2: Grant Stay Active Bonus (Admin)
```bash
curl -X POST http://localhost:8000/subscription/admin/grant-add-on \
  -H "Authorization: Bearer {admin_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 123,
    "add_on_type": "stay_active_bonus"
  }'
```
Expected: Credits granted confirmation

### Test 3: View Earned Add-Ons
```bash
curl -X GET http://localhost:8000/subscription/my-add-ons \
  -H "Authorization: Bearer {user_token}"
```
Expected: Shows 30 credits earned for Stay Active

### Test 4: Redeem Add-On
```bash
curl -X POST http://localhost:8000/subscription/redeem-add-on \
  -H "Authorization: Bearer {user_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "add_on_type": "stay_active_bonus"
  }'
```
Expected: Credits added to current_credits

### Test 5: Attempt Unavailable Add-On (Starter user tries Boost Pack)
```bash
curl -X POST http://localhost:8000/subscription/redeem-add-on \
  -H "Authorization: Bearer {starter_user_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "add_on_type": "boost_pack"
  }'
```
Expected: 403 error (not available for tier)

## Future Enhancements

### Potential Features
1. **Auto-Grant**: Automatically grant add-ons based on activity
   - Login streak → Stay Active Bonus
   - High engagement → Bonus Credits
   - Team growth → Boost Pack

2. **Cooldown Periods**: Limit redemption frequency
   - Once per month
   - Once per billing cycle

3. **Notifications**: Alert users when add-ons are earned
   - Email notification
   - In-app notification
   - Dashboard badge

4. **Expiration**: Set expiration on earned add-ons
   - Use within 90 days
   - Prevents indefinite accumulation

5. **Analytics Dashboard**: Track add-on usage
   - Most popular add-on
   - Redemption rate
   - Impact on engagement

## Support

### Common Issues

**Q: User redeemed but credits not showing?**
A: Check `current_credits` column - should be incremented. Check logs for commit errors.

**Q: Add-on shows available=false but user claims they should have it?**
A: Verify subscription tier level matches expected tier. Check `has_*` flags in subscriptions table.

**Q: Boost Pack redeemed but seat not activated?**
A: Boost Pack requires manual seat activation. Update `max_seats` in subscription record.

**Q: User downgraded tier but can still redeem unavailable add-on?**
A: This is a bug. Redemption endpoint checks `has_*` flags. If flags not updated after tier change, run migration again.

## Model Reference

### Subscription Model
```python
class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    tier_level = Column(Integer)  # 1, 2, or 3
    has_stay_active_bonus = Column(Boolean, default=False)
    has_bonus_credits = Column(Boolean, default=False)
    has_boost_pack = Column(Boolean, default=False)
    # ... other columns
```

### Subscriber Model
```python
class Subscriber(Base):
    __tablename__ = "subscribers"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    subscription_id = Column(Integer, ForeignKey("subscriptions.id"))
    
    # Current active credits/seats
    current_credits = Column(Integer, default=0)
    
    # Earned but unredeemed add-ons
    stay_active_credits = Column(Integer, default=0)
    bonus_credits = Column(Integer, default=0)
    boost_pack_credits = Column(Integer, default=0)
    boost_pack_seats = Column(Integer, default=0)
    
    # Redemption tracking
    last_stay_active_redemption = Column(TIMESTAMP)
    last_bonus_redemption = Column(TIMESTAMP)
    last_boost_redemption = Column(TIMESTAMP)
    # ... other columns
```
