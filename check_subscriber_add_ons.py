"""
Check subscriber add-on columns to see what was actually granted
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

# Create engine
engine = create_engine(DATABASE_URL)

# First check what columns exist
print("Subscriber table columns:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'subscribers' 
        ORDER BY ordinal_position
    """))
    
    columns = [row[0] for row in result]
    for col in columns:
        print(f"  - {col}")

print("\n" + "=" * 100)

# Check subscriber add-on columns
with engine.connect() as conn:
    # Get recent subscribers who have Professional plan (subscription_id = 3)
    result = conn.execute(text("""
        SELECT s.id, s.user_id, s.subscription_id, sub.name as plan_name,
               s.current_credits, s.stay_active_credits, s.bonus_credits, 
               s.boost_pack_credits, s.boost_pack_seats
        FROM subscribers s
        LEFT JOIN subscriptions sub ON s.subscription_id = sub.id
        WHERE s.subscription_id = 3
        ORDER BY s.id DESC
        LIMIT 10
    """))
    
    print("\nSubscribers with Professional Plan (ID 3):")
    print("=" * 100)
    
    for row in result:
        print(f"\nSubscriber ID: {row[0]}, User ID: {row[1]}")
        print(f"  Plan: {row[3]} (ID: {row[2]})")
        print(f"  Current Credits: {row[4]}")
        print(f"  Stay Active Credits: {row[5]}")
        print(f"  Bonus Credits: {row[6]}")
        print(f"  Boost Pack Credits: {row[7]}")
        print(f"  Boost Pack Seats: {row[8]}")
        
        # Check if add-ons were granted
        if row[5] == 0 and row[6] == 0 and row[7] == 0:
            print(f"  ⚠️ WARNING: NO ADD-ONS GRANTED!")
        else:
            print(f"  ✓ Add-ons granted")

