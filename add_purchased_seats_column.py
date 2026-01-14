"""
Migration: Add purchased_seats column to track accumulated seats from plan switches
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set")

engine = create_engine(DATABASE_URL)

def add_purchased_seats_column():
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Check if column exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = 'subscribers' 
                    AND column_name = 'purchased_seats'
                );
            """))
            
            if not result.scalar():
                # Add the column
                conn.execute(text("""
                    ALTER TABLE subscribers 
                    ADD COLUMN purchased_seats INTEGER DEFAULT 0;
                """))
                print("✓ Added purchased_seats column to subscribers table")
                
                # Initialize with 0 for all existing subscribers
                # They will accumulate seats on next plan switch
                conn.execute(text("""
                    UPDATE subscribers 
                    SET purchased_seats = 0
                    WHERE purchased_seats IS NULL;
                """))
                print("✓ Initialized purchased_seats to 0 for existing subscribers")
            else:
                print("✓ purchased_seats column already exists")
            
            trans.commit()
            print("\n✅ Migration completed!")
            print("\nHow it works:")
            print("- New subscription: purchased_seats = 0, total = plan.max_seats")
            print("- Switch plans: purchased_seats += old_plan.max_seats, total = plan.max_seats + purchased_seats")
            print("- Renewal: purchased_seats unchanged, total = plan.max_seats + purchased_seats")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Error: {e}")
            raise

if __name__ == "__main__":
    add_purchased_seats_column()
