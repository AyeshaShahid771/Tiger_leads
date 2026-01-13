"""
Check if subscription add-on columns exist and have correct values
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

# Check subscription columns
with engine.connect() as conn:
    # Get Professional plan (ID 3)
    result = conn.execute(text("""
        SELECT id, name, tier_level, has_stay_active_bonus, has_bonus_credits, has_boost_pack
        FROM subscriptions
        WHERE id = 3
    """))
    
    row = result.fetchone()
    
    if row:
        print(f"\nProfessional Plan (ID {row[0]}):")
        print(f"  Name: {row[1]}")
        print(f"  tier_level: {row[2]}")
        print(f"  has_stay_active_bonus: {row[3]}")
        print(f"  has_bonus_credits: {row[4]}")
        print(f"  has_boost_pack: {row[5]}")
    else:
        print("Professional plan not found!")
    
    # Check all subscriptions
    print("\nAll Subscriptions:")
    result = conn.execute(text("""
        SELECT id, name, tier_level, has_stay_active_bonus, has_bonus_credits, has_boost_pack
        FROM subscriptions
        ORDER BY id
    """))
    
    for row in result:
        print(f"  ID {row[0]}: {row[1]} - Tier {row[2]}")
        print(f"    stay_active={row[3]}, bonus={row[4]}, boost={row[5]}")

