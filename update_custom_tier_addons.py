"""
Migration: Update Custom Tier Add-ons Configuration

This migration updates the Custom tier and any custom subscriptions to include all three add-ons:
- Stay Active Bonus
- Bonus Credits  
- Boost Pack

Run: python update_custom_tier_addons.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create database engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def update_custom_tier_addons():
    """Update Custom tier to have all three add-ons"""
    
    session = SessionLocal()
    try:
        print("Starting migration: Update Custom tier add-ons...")
        
        # Update the base "Custom" tier
        print("\n1. Updating base 'Custom' tier...")
        result = session.execute(text("""
            UPDATE subscriptions 
            SET tier_level = NULL,
                has_stay_active_bonus = TRUE,
                has_bonus_credits = TRUE,
                has_boost_pack = TRUE
            WHERE name = 'Custom';
        """))
        print(f"   ✓ Updated 'Custom' tier with all add-ons")
        
        # Update all custom subscriptions (those with names starting with "Custom -")
        print("\n2. Updating dynamically created custom subscriptions...")
        result = session.execute(text("""
            UPDATE subscriptions 
            SET tier_level = NULL,
                has_stay_active_bonus = TRUE,
                has_bonus_credits = TRUE,
                has_boost_pack = TRUE
            WHERE name LIKE 'Custom -%';
        """))
        custom_count = result.rowcount
        print(f"   ✓ Updated {custom_count} custom subscription(s) with all add-ons")
        
        # Commit changes
        session.commit()
        
        # Verify the changes
        print("\n" + "="*60)
        print("VERIFICATION - Custom Subscription Configuration:")
        print("="*60)
        
        result = session.execute(text("""
            SELECT id, name, tier_level, has_stay_active_bonus, 
                   has_bonus_credits, has_boost_pack
            FROM subscriptions 
            WHERE name = 'Custom' OR name LIKE 'Custom -%'
            ORDER BY id;
        """))
        
        for row in result:
            print(f"\nID {row[0]}: {row[1]}")
            tier_display = f"Tier {row[2]}" if row[2] else "Custom (no tier_level)"
            print(f"  Tier: {tier_display}")
            print(f"  - Stay Active Bonus: {'✓' if row[3] else '✗'}")
            print(f"  - Bonus Credits: {'✓' if row[4] else '✗'}")
            print(f"  - Boost Pack: {'✓' if row[5] else '✗'}")
        print("="*60)
        
        print("\n✅ Migration completed successfully!")
        print("\nCustom tier configuration:")
        print("  - Starter (tier_level=1): Stay Active only")
        print("  - Professional (tier_level=2): Stay Active + Bonus Credits")
        print("  - Enterprise (tier_level=3): Stay Active + Bonus Credits + Boost Pack")
        print("  - Custom (tier_level=NULL): Stay Active + Bonus Credits + Boost Pack")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    import sys
    
    print("\nThis migration will update Custom tier add-ons configuration.")
    print("Custom subscriptions will receive all three add-ons:")
    print("  - Stay Active Bonus (30 credits)")
    print("  - Bonus Credits (50 credits)")
    print("  - Boost Pack (100 credits + 1 seat)")
    
    response = input("\nProceed with migration? (yes/no): ")
    if response.lower() in ["yes", "y"]:
        success = update_custom_tier_addons()
        sys.exit(0 if success else 1)
    else:
        print("Migration cancelled.")
        sys.exit(0)
