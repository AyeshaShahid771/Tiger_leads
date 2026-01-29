"""
Add service_states column to contractors table

This migration adds the service_states column to match the suppliers table structure.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.app.core.database import engine


def run_migration():
    """Add service_states column to contractors table"""
    
    with engine.connect() as conn:
        print("Starting migration: Add service_states to contractors...")
        
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='service_states'
        """))
        
        if result.fetchone():
            print("✓ Column 'service_states' already exists in contractors table")
        else:
            print("Adding 'service_states' column to contractors table...")
            conn.execute(text("""
                ALTER TABLE contractors 
                ADD COLUMN service_states TEXT[]
            """))
            conn.commit()
            print("✓ Added 'service_states' column to contractors table")
        
        print("\n✅ Migration completed successfully!")
        print("\nNew column added:")
        print("  - service_states (TEXT[] - array of states)")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)
