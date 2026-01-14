"""
Fix ALL subscription add-ons configuration
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)

def fix_all():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            print("="*80)
            print("FIXING SUBSCRIPTION ADD-ONS")
            print("="*80)
            
            # 1. Fix Starter (ID 2): Stay Active only
            print("\n1. Updating Starter...")
            conn.execute(text("""
                UPDATE subscriptions 
                SET tier_level = 1,
                    has_stay_active_bonus = TRUE,
                    has_bonus_credits = FALSE,
                    has_boost_pack = FALSE
                WHERE id = 2 OR name = 'Starter';
            """))
            print("   ✓ Starter: Stay Active only")
            
            # 2. Fix Professional (ID 3): Stay Active + Bonus Credits (NO Boost Pack!)
            print("\n2. Updating Professional...")
            conn.execute(text("""
                UPDATE subscriptions 
                SET tier_level = 2,
                    has_stay_active_bonus = TRUE,
                    has_bonus_credits = TRUE,
                    has_boost_pack = FALSE,
                    credits = 300
                WHERE id = 3 OR name = 'Professional';
            """))
            print("   ✓ Professional: Stay Active + Bonus Credits, 300 credits")
            
            # 3. Fix Enterprise (ID 4): Stay Active + Bonus Credits + Boost Pack
            print("\n3. Updating Enterprise...")
            conn.execute(text("""
                UPDATE subscriptions 
                SET tier_level = 3,
                    has_stay_active_bonus = TRUE,
                    has_bonus_credits = TRUE,
                    has_boost_pack = TRUE,
                    credits = 1000
                WHERE id = 4 OR name = 'Enterprise';
            """))
            print("   ✓ Enterprise: All add-ons, 1000 credits")
            
            # 4. Fix ALL Custom subscriptions
            print("\n4. Updating ALL Custom subscriptions...")
            result = conn.execute(text("""
                UPDATE subscriptions 
                SET tier_level = NULL,
                    has_stay_active_bonus = TRUE,
                    has_bonus_credits = TRUE,
                    has_boost_pack = TRUE
                WHERE id > 4;
            """))
            count = result.rowcount
            print(f"   ✓ Updated {count} custom subscriptions: All add-ons")
            
            # 5. Reset Professional subscribers' Boost Pack
            print("\n5. Removing Boost Pack from Professional subscribers...")
            result = conn.execute(text("""
                UPDATE subscribers 
                SET boost_pack_credits = 0,
                    boost_pack_seats = 0
                WHERE subscription_id = 3;
            """))
            count = result.rowcount
            print(f"   ✓ Reset Boost Pack for {count} Professional subscribers")
            
            # 6. Grant add-ons to Enterprise subscribers who don't have them
            print("\n6. Granting add-ons to Enterprise subscribers...")
            result = conn.execute(text("""
                UPDATE subscribers 
                SET stay_active_credits = 30,
                    bonus_credits = 50,
                    boost_pack_credits = 100,
                    boost_pack_seats = 1
                WHERE subscription_id = 4 
                AND (stay_active_credits = 0 OR stay_active_credits IS NULL);
            """))
            count = result.rowcount
            print(f"   ✓ Granted add-ons to {count} Enterprise subscribers")
            
            trans.commit()
            
            # Verify
            print("\n" + "="*80)
            print("VERIFICATION")
            print("="*80)
            
            result = conn.execute(text("""
                SELECT id, name, credits, tier_level, 
                       has_stay_active_bonus, has_bonus_credits, has_boost_pack
                FROM subscriptions 
                WHERE id <= 4
                ORDER BY id;
            """))
            
            for row in result:
                print(f"\nID {row[0]}: {row[1]}")
                print(f"  Credits: {row[2]}")
                print(f"  Tier: {row[3]}")
                print(f"  Stay Active: {'✓' if row[4] else '✗'}")
                print(f"  Bonus Credits: {'✓' if row[5] else '✗'}")
                print(f"  Boost Pack: {'✓' if row[6] else '✗'}")
            
            # Check custom subscriptions
            result = conn.execute(text("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN has_stay_active_bonus THEN 1 ELSE 0 END) as stay_active,
                       SUM(CASE WHEN has_bonus_credits THEN 1 ELSE 0 END) as bonus,
                       SUM(CASE WHEN has_boost_pack THEN 1 ELSE 0 END) as boost
                FROM subscriptions 
                WHERE id > 4;
            """))
            
            row = result.fetchone()
            print(f"\n{row[0]} Custom subscriptions:")
            print(f"  Stay Active: {row[1]}/{row[0]}")
            print(f"  Bonus Credits: {row[2]}/{row[0]}")
            print(f"  Boost Pack: {row[3]}/{row[0]}")
            
            print("\n✅ ALL FIXED!")
            print("\nCorrect configuration:")
            print("  - Starter: Stay Active (30)")
            print("  - Professional: Stay Active (30) + Bonus (50)")
            print("  - Enterprise: Stay Active (30) + Bonus (50) + Boost (100+1)")
            print("  - Custom: Stay Active (30) + Bonus (50) + Boost (100+1)")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            raise

if __name__ == "__main__":
    fix_all()
