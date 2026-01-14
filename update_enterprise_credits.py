"""
Update Enterprise subscription to 1000 credits to match UI
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)

def update():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Update Enterprise to 1000 credits
            result = conn.execute(text("""
                UPDATE subscriptions 
                SET credits = 1000
                WHERE name = 'Enterprise';
            """))
            
            # Verify
            row = conn.execute(text("""
                SELECT id, name, price, credits, max_seats 
                FROM subscriptions 
                WHERE name = 'Enterprise';
            """)).fetchone()
            
            if row:
                print(f"✅ Updated Enterprise plan:")
                print(f"   ID: {row[0]}")
                print(f"   Name: {row[1]}")
                print(f"   Price: {row[2]}")
                print(f"   Credits: {row[3]}")
                print(f"   Seats: {row[4]}")
            
            trans.commit()
            print("\n✅ Migration completed!")
        except Exception as e:
            trans.rollback()
            print(f"❌ Error: {e}")
            raise

if __name__ == "__main__":
    print("Updating Enterprise plan to 1000 credits...")
    update()
