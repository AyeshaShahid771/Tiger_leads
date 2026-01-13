"""
Migration: Add Add-on Columns to Subscriptions and Subscribers Tables

This migration:
1. Adds tier_level and add-on flags to subscriptions table
2. Adds earned add-on credits/seats to subscribers table
3. Updates existing subscription plans with correct tier levels and add-on availability

Tier Mapping:
- Tier 1 = Starter (id=2): Stay Active Bonus only
- Tier 2 = Professional (id=3): Stay Active Bonus + Bonus Credits + Boost Pack
- Tier 3 = Enterprise (id=4): Stay Active Bonus + Bonus Credits
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


def add_addon_columns():
    """Add add-on related columns to subscriptions and subscribers tables"""
    
    session = SessionLocal()
    try:
        print("Starting migration: Add add-on columns...")
        
        # ===== SUBSCRIPTIONS TABLE =====
        print("\n1. Updating subscriptions table...")
        
        # Check and add tier_level column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'tier_level'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN tier_level INTEGER;
            """))
            print("   ✓ Added tier_level column")
        else:
            print("   ✓ tier_level column already exists")
        
        # Check and add has_stay_active_bonus column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'has_stay_active_bonus'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN has_stay_active_bonus BOOLEAN DEFAULT FALSE;
            """))
            print("   ✓ Added has_stay_active_bonus column")
        else:
            print("   ✓ has_stay_active_bonus column already exists")
        
        # Check and add has_bonus_credits column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'has_bonus_credits'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN has_bonus_credits BOOLEAN DEFAULT FALSE;
            """))
            print("   ✓ Added has_bonus_credits column")
        else:
            print("   ✓ has_bonus_credits column already exists")
        
        # Check and add has_boost_pack column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscriptions' 
                AND column_name = 'has_boost_pack'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscriptions 
                ADD COLUMN has_boost_pack BOOLEAN DEFAULT FALSE;
            """))
            print("   ✓ Added has_boost_pack column")
        else:
            print("   ✓ has_boost_pack column already exists")
        
        # ===== UPDATE SUBSCRIPTION PLANS =====
        print("\n2. Updating subscription plan configurations...")
        
        # Starter (id=2, tier=1): Stay Active Bonus only
        session.execute(text("""
            UPDATE subscriptions 
            SET tier_level = 1,
                has_stay_active_bonus = TRUE,
                has_bonus_credits = FALSE,
                has_boost_pack = FALSE
            WHERE id = 2 OR name = 'Starter';
        """))
        print("   ✓ Updated Starter plan (Tier 1)")
        
        # Professional (id=3, tier=2): All add-ons
        session.execute(text("""
            UPDATE subscriptions 
            SET tier_level = 2,
                has_stay_active_bonus = TRUE,
                has_bonus_credits = TRUE,
                has_boost_pack = TRUE
            WHERE id = 3 OR name = 'Professional';
        """))
        print("   ✓ Updated Professional plan (Tier 2)")
        
        # Enterprise (id=4, tier=3): Stay Active + Bonus Credits
        session.execute(text("""
            UPDATE subscriptions 
            SET tier_level = 3,
                has_stay_active_bonus = TRUE,
                has_bonus_credits = TRUE,
                has_boost_pack = FALSE
            WHERE id = 4 OR name = 'Enterprise';
        """))
        print("   ✓ Updated Enterprise plan (Tier 3)")
        
        # ===== SUBSCRIBERS TABLE =====
        print("\n3. Updating subscribers table...")
        
        # Check and add stay_active_credits column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'stay_active_credits'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN stay_active_credits INTEGER DEFAULT 0;
            """))
            print("   ✓ Added stay_active_credits column")
        else:
            print("   ✓ stay_active_credits column already exists")
        
        # Check and add bonus_credits column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'bonus_credits'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN bonus_credits INTEGER DEFAULT 0;
            """))
            print("   ✓ Added bonus_credits column")
        else:
            print("   ✓ bonus_credits column already exists")
        
        # Check and add boost_pack_credits column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'boost_pack_credits'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN boost_pack_credits INTEGER DEFAULT 0;
            """))
            print("   ✓ Added boost_pack_credits column")
        else:
            print("   ✓ boost_pack_credits column already exists")
        
        # Check and add boost_pack_seats column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'boost_pack_seats'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN boost_pack_seats INTEGER DEFAULT 0;
            """))
            print("   ✓ Added boost_pack_seats column")
        else:
            print("   ✓ boost_pack_seats column already exists")
        
        # Check and add last_stay_active_redemption column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'last_stay_active_redemption'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN last_stay_active_redemption TIMESTAMP;
            """))
            print("   ✓ Added last_stay_active_redemption column")
        else:
            print("   ✓ last_stay_active_redemption column already exists")
        
        # Check and add last_bonus_redemption column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'last_bonus_redemption'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN last_bonus_redemption TIMESTAMP;
            """))
            print("   ✓ Added last_bonus_redemption column")
        else:
            print("   ✓ last_bonus_redemption column already exists")
        
        # Check and add last_boost_redemption column
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'subscribers' 
                AND column_name = 'last_boost_redemption'
            );
        """))
        if not result.scalar():
            session.execute(text("""
                ALTER TABLE subscribers 
                ADD COLUMN last_boost_redemption TIMESTAMP;
            """))
            print("   ✓ Added last_boost_redemption column")
        else:
            print("   ✓ last_boost_redemption column already exists")
        
        session.commit()
        print("\n✅ Migration completed successfully!")
        
        # Display configuration summary
        print("\n" + "="*60)
        print("SUBSCRIPTION TIER CONFIGURATION:")
        print("="*60)
        result = session.execute(text("""
            SELECT id, name, tier_level, has_stay_active_bonus, 
                   has_bonus_credits, has_boost_pack
            FROM subscriptions 
            WHERE tier_level IS NOT NULL
            ORDER BY tier_level;
        """))
        for row in result:
            print(f"\nID {row[0]}: {row[1]} (Tier {row[2]})")
            print(f"  - Stay Active Bonus: {'✓' if row[3] else '✗'}")
            print(f"  - Bonus Credits: {'✓' if row[4] else '✗'}")
            print(f"  - Boost Pack: {'✓' if row[5] else '✗'}")
        print("="*60)
        
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
    success = add_addon_columns()
    sys.exit(0 if success else 1)
