"""
Add licenses column to contractors and suppliers tables

This migration adds a new 'licenses' JSON column to store multiple licenses.
The existing single license columns (state_license_number, license_expiration_date, 
license_status) are kept for backward compatibility.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.app.database import engine


def run_migration():
    """Add licenses column to contractors and suppliers tables"""
    
    with engine.connect() as conn:
        print("Starting migration: Add licenses column...")
        
        # Check if column already exists in contractors table
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='licenses'
        """))
        
        if result.fetchone():
            print("✓ Column 'licenses' already exists in contractors table")
        else:
            print("Adding 'licenses' column to contractors table...")
            conn.execute(text("""
                ALTER TABLE contractors 
                ADD COLUMN licenses JSON
            """))
            conn.commit()
            print("✓ Added 'licenses' column to contractors table")
        
        # Check if column already exists in suppliers table
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='suppliers' AND column_name='licenses'
        """))
        
        if result.fetchone():
            print("✓ Column 'licenses' already exists in suppliers table")
        else:
            print("Adding 'licenses' column to suppliers table...")
            conn.execute(text("""
                ALTER TABLE suppliers 
                ADD COLUMN licenses JSON
            """))
            conn.commit()
            print("✓ Added 'licenses' column to suppliers table")
        
        print("\n✅ Migration completed successfully!")
        print("\nExisting columns retained:")
        print("  - state_license_number")
        print("  - license_expiration_date")
        print("  - license_status")
        print("\nNew column added:")
        print("  - licenses (JSON array)")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)
