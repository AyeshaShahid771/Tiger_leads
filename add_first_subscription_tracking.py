"""
Migration: Add first-time subscription tracking columns to subscriber table

This migration adds timestamp columns to track when a user first subscribes to each tier.
Add-ons will only be granted on the first subscription to each tier.

Columns added:
- first_starter_subscription_at: Timestamp of first Starter subscription
- first_professional_subscription_at: Timestamp of first Professional subscription
- first_enterprise_subscription_at: Timestamp of first Enterprise subscription
- first_custom_subscription_at: Timestamp of first Custom plan subscription
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

print(f"🔗 Connecting to database...")

# Create engine
engine = create_engine(DATABASE_URL)

# SQL to add columns
migration_sql = """
-- Add first-time subscription tracking columns
ALTER TABLE subscribers 
ADD COLUMN IF NOT EXISTS first_starter_subscription_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS first_professional_subscription_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS first_enterprise_subscription_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS first_custom_subscription_at TIMESTAMP;

-- Add comments for documentation
COMMENT ON COLUMN subscribers.first_starter_subscription_at IS 'Timestamp when user first subscribed to Starter tier';
COMMENT ON COLUMN subscribers.first_professional_subscription_at IS 'Timestamp when user first subscribed to Professional tier';
COMMENT ON COLUMN subscribers.first_enterprise_subscription_at IS 'Timestamp when user first subscribed to Enterprise tier';
COMMENT ON COLUMN subscribers.first_custom_subscription_at IS 'Timestamp when user first subscribed to any Custom plan';
"""

try:
    with engine.connect() as conn:
        print("📝 Running migration...")
        
        # Execute migration
        conn.execute(text(migration_sql))
        conn.commit()
        
        print("✅ Migration completed successfully!")
        print("\n📊 Added columns:")
        print("   - first_starter_subscription_at")
        print("   - first_professional_subscription_at")
        print("   - first_enterprise_subscription_at")
        print("   - first_custom_subscription_at")
        
        # Verify columns were added
        verify_sql = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'subscribers' 
        AND column_name LIKE 'first_%_subscription_at'
        ORDER BY column_name;
        """
        
        result = conn.execute(text(verify_sql))
        columns = result.fetchall()
        
        print("\n✓ Verification:")
        for col in columns:
            print(f"   ✓ {col[0]} ({col[1]})")
        
        print("\n🎉 Migration successful! Add-ons will now be granted only on first subscription per tier.")

except Exception as e:
    print(f"\n❌ Migration failed: {str(e)}")
    sys.exit(1)
