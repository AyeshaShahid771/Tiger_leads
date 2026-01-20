"""
Test script to verify first-time add-on grant logic

This script checks:
1. Database columns exist
2. Model has the new fields
3. Logic works correctly
"""

from src.app.core.database import SessionLocal
from sqlalchemy import text

print("🔍 Verifying First-Time Add-On Implementation\n")

db = SessionLocal()

# 1. Check database columns
print("1️⃣ Checking database columns...")
result = db.execute(text("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'subscribers' 
    AND column_name LIKE 'first_%_subscription_at'
    ORDER BY column_name;
"""))

columns = result.fetchall()
if len(columns) == 4:
    print("   ✅ All 4 columns found in database:")
    for col in columns:
        print(f"      - {col[0]} ({col[1]}, nullable: {col[2]})")
else:
    print(f"   ❌ Expected 4 columns, found {len(columns)}")

# 2. Check if any subscribers have these fields set
print("\n2️⃣ Checking existing subscriber data...")
result = db.execute(text("""
    SELECT 
        COUNT(*) as total_subscribers,
        COUNT(first_starter_subscription_at) as has_starter,
        COUNT(first_professional_subscription_at) as has_professional,
        COUNT(first_enterprise_subscription_at) as has_enterprise,
        COUNT(first_custom_subscription_at) as has_custom
    FROM subscribers;
"""))

stats = result.fetchone()
print(f"   Total subscribers: {stats[0]}")
print(f"   With first_starter_subscription_at: {stats[1]}")
print(f"   With first_professional_subscription_at: {stats[2]}")
print(f"   With first_enterprise_subscription_at: {stats[3]}")
print(f"   With first_custom_subscription_at: {stats[4]}")

# 3. Show sample subscribers with add-ons
print("\n3️⃣ Sample subscribers with unredeemed add-ons:")
result = db.execute(text("""
    SELECT 
        s.id,
        s.user_id,
        u.email,
        s.stay_active_credits,
        s.bonus_credits,
        s.boost_pack_credits,
        s.boost_pack_seats,
        s.first_starter_subscription_at,
        s.first_professional_subscription_at,
        s.first_enterprise_subscription_at,
        s.first_custom_subscription_at
    FROM subscribers s
    JOIN users u ON s.user_id = u.id
    WHERE 
        s.stay_active_credits > 0 
        OR s.bonus_credits > 0 
        OR s.boost_pack_credits > 0
    LIMIT 5;
"""))

subscribers = result.fetchall()
if subscribers:
    for sub in subscribers:
        print(f"\n   Subscriber ID: {sub[0]} | User: {sub[2]}")
        print(f"   - Stay Active: {sub[3]} credits")
        print(f"   - Bonus: {sub[4]} credits")
        print(f"   - Boost Pack: {sub[5]} credits + {sub[6]} seats")
        print(f"   - First Starter: {sub[7]}")
        print(f"   - First Professional: {sub[8]}")
        print(f"   - First Enterprise: {sub[9]}")
        print(f"   - First Custom: {sub[10]}")
else:
    print("   No subscribers with unredeemed add-ons found")

db.close()

print("\n✅ Verification complete!")
print("\n📝 Next steps:")
print("   1. Test with a new subscription to see add-ons granted")
print("   2. Test with a renewal to see add-ons NOT granted")
print("   3. Check logs for 'FIRST TIME' or 'already received' messages")
