"""
Migration script to add credit management columns to subscribers table.

This adds support for:
- Trial credits (25 free credits on signup, 14-day expiry)
- Credit rollover (carryover month-to-month)
- Credit freeze/restore (30-day window on subscription lapse)
"""

import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text, Integer, DateTime, Boolean
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

def run_migration():
    """Add credit management columns to subscribers table."""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Starting migration: Adding credit management columns...")
        
        # Start transaction
        trans = conn.begin()
        
        try:
            # Add trial credits columns
            print("Adding trial_credits column...")
            conn.execute(text(
                "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS trial_credits INTEGER DEFAULT 25"
            ))
            
            print("Adding trial_credits_expires_at column...")
            conn.execute(text(
                "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS trial_credits_expires_at TIMESTAMP"
            ))
            
            print("Adding trial_credits_used column...")
            conn.execute(text(
                "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS trial_credits_used BOOLEAN DEFAULT FALSE"
            ))
            
            # Add credit freeze/lapse columns
            print("Adding frozen_credits column...")
            conn.execute(text(
                "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS frozen_credits INTEGER DEFAULT 0"
            ))
            
            print("Adding frozen_at column...")
            conn.execute(text(
                "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS frozen_at TIMESTAMP"
            ))
            
            print("Adding last_active_date column...")
            conn.execute(text(
                "ALTER TABLE subscribers ADD COLUMN IF NOT EXISTS last_active_date TIMESTAMP"
            ))
            
            # Update existing active subscribers with last_active_date
            print("Setting last_active_date for existing active subscribers...")
            conn.execute(text(
                """
                UPDATE subscribers 
                SET last_active_date = subscription_start_date 
                WHERE is_active = TRUE AND last_active_date IS NULL
                """
            ))
            
            trans.commit()
            print("✅ Migration completed successfully!")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {str(e)}")
            raise

if __name__ == "__main__":
    print("=" * 60)
    print("Credit Management Migration")
    print("=" * 60)
    run_migration()
    print("\nMigration complete. New columns added:")
    print("  - trial_credits (25 free credits)")
    print("  - trial_credits_expires_at (14-day expiry)")
    print("  - trial_credits_used (trial claimed flag)")
    print("  - frozen_credits (credits frozen on lapse)")
    print("  - frozen_at (when subscription lapsed)")
    print("  - last_active_date (last active subscription date)")
