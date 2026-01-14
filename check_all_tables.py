"""
Check all database tables for subscription system
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)

def check_tables():
    with engine.connect() as conn:
        print("="*80)
        print("SUBSCRIPTIONS TABLE")
        print("="*80)
        result = conn.execute(text("""
            SELECT id, name, price, credits, max_seats, 
                   tier_level, has_stay_active_bonus, has_bonus_credits, has_boost_pack,
                   stripe_price_id, stripe_product_id
            FROM subscriptions 
            ORDER BY id;
        """))
        
        for row in result:
            print(f"\nID: {row[0]}")
            print(f"  Name: {row[1]}")
            print(f"  Price: {row[2]}")
            print(f"  Credits: {row[3]}")
            print(f"  Max Seats: {row[4]}")
            print(f"  Tier Level: {row[5]}")
            print(f"  Has Stay Active: {row[6]}")
            print(f"  Has Bonus Credits: {row[7]}")
            print(f"  Has Boost Pack: {row[8]}")
            print(f"  Stripe Price ID: {row[9]}")
            print(f"  Stripe Product ID: {row[10]}")
        
        print("\n" + "="*80)
        print("SUBSCRIBERS TABLE (Last 10)")
        print("="*80)
        result = conn.execute(text("""
            SELECT s.id, s.user_id, u.email, sub.name as plan_name,
                   s.current_credits, s.subscription_status, s.is_active,
                   s.stay_active_credits, s.bonus_credits, 
                   s.boost_pack_credits, s.boost_pack_seats,
                   s.subscription_start_date, s.subscription_renew_date
            FROM subscribers s
            LEFT JOIN users u ON s.user_id = u.id
            LEFT JOIN subscriptions sub ON s.subscription_id = sub.id
            ORDER BY s.id DESC
            LIMIT 10;
        """))
        
        for row in result:
            print(f"\nSubscriber ID: {row[0]}")
            print(f"  User ID: {row[1]}")
            print(f"  Email: {row[2]}")
            print(f"  Plan: {row[3]}")
            print(f"  Current Credits: {row[4]}")
            print(f"  Status: {row[5]}")
            print(f"  Active: {row[6]}")
            print(f"  Stay Active Credits: {row[7]}")
            print(f"  Bonus Credits: {row[8]}")
            print(f"  Boost Pack Credits: {row[9]}")
            print(f"  Boost Pack Seats: {row[10]}")
            print(f"  Start Date: {row[11]}")
            print(f"  Renew Date: {row[12]}")
        
        print("\n" + "="*80)
        print("USERS TABLE (Last 10 with subscriptions)")
        print("="*80)
        result = conn.execute(text("""
            SELECT u.id, u.email, u.role, u.email_verified, u.is_active,
                   s.subscription_id, sub.name as plan_name
            FROM users u
            LEFT JOIN subscribers s ON u.id = s.user_id
            LEFT JOIN subscriptions sub ON s.subscription_id = sub.id
            WHERE s.id IS NOT NULL
            ORDER BY u.id DESC
            LIMIT 10;
        """))
        
        for row in result:
            print(f"\nUser ID: {row[0]}")
            print(f"  Email: {row[1]}")
            print(f"  Role: {row[2]}")
            print(f"  Email Verified: {row[3]}")
            print(f"  Active: {row[4]}")
            print(f"  Subscription ID: {row[5]}")
            print(f"  Plan Name: {row[6]}")

if __name__ == "__main__":
    check_tables()
