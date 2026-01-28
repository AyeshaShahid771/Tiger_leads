"""
Convert existing license columns to JSON arrays for multiple licenses support

This migration converts the existing single license columns to JSON arrays:
- state_license_number: String -> JSON array of strings
- license_expiration_date: Date -> JSON array of date strings
- license_status: String -> JSON array of strings

Existing data will be migrated to the new format.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.app.core.database import engine


def run_migration():
    """Convert license columns to JSON arrays"""
    
    with engine.connect() as conn:
        print("Starting migration: Convert license columns to JSON arrays...")
        
        # ===== CONTRACTORS TABLE =====
        print("\n📋 Processing CONTRACTORS table...")
        
        # 1. Create temporary columns
        print("  1. Creating temporary JSON columns...")
        conn.execute(text("""
            ALTER TABLE contractors 
            ADD COLUMN IF NOT EXISTS state_license_number_new JSON,
            ADD COLUMN IF NOT EXISTS license_expiration_date_new JSON,
            ADD COLUMN IF NOT EXISTS license_status_new JSON
        """))
        conn.commit()
        
        # 2. Migrate existing data to JSON arrays
        print("  2. Migrating existing data to JSON arrays...")
        conn.execute(text("""
            UPDATE contractors
            SET 
                state_license_number_new = CASE 
                    WHEN state_license_number IS NOT NULL 
                    THEN json_build_array(state_license_number)::json
                    ELSE '[]'::json
                END,
                license_expiration_date_new = CASE 
                    WHEN license_expiration_date IS NOT NULL 
                    THEN json_build_array(license_expiration_date::text)::json
                    ELSE '[]'::json
                END,
                license_status_new = CASE 
                    WHEN license_status IS NOT NULL 
                    THEN json_build_array(license_status)::json
                    ELSE '[]'::json
                END
        """))
        conn.commit()
        
        # 3. Drop old columns
        print("  3. Dropping old columns...")
        conn.execute(text("""
            ALTER TABLE contractors 
            DROP COLUMN IF EXISTS state_license_number,
            DROP COLUMN IF EXISTS license_expiration_date,
            DROP COLUMN IF EXISTS license_status
        """))
        conn.commit()
        
        # 4. Rename new columns to original names
        print("  4. Renaming new columns...")
        conn.execute(text("""
            ALTER TABLE contractors 
            RENAME COLUMN state_license_number_new TO state_license_number;
            
            ALTER TABLE contractors 
            RENAME COLUMN license_expiration_date_new TO license_expiration_date;
            
            ALTER TABLE contractors 
            RENAME COLUMN license_status_new TO license_status
        """))
        conn.commit()
        
        print("  ✓ Contractors table updated")
        
        # ===== SUPPLIERS TABLE =====
        print("\n📋 Processing SUPPLIERS table...")
        
        # 1. Create temporary columns
        print("  1. Creating temporary JSON columns...")
        conn.execute(text("""
            ALTER TABLE suppliers 
            ADD COLUMN IF NOT EXISTS state_license_number_new JSON,
            ADD COLUMN IF NOT EXISTS license_expiration_date_new JSON,
            ADD COLUMN IF NOT EXISTS license_status_new JSON
        """))
        conn.commit()
        
        # 2. Migrate existing data to JSON arrays
        print("  2. Migrating existing data to JSON arrays...")
        conn.execute(text("""
            UPDATE suppliers
            SET 
                state_license_number_new = CASE 
                    WHEN state_license_number IS NOT NULL 
                    THEN json_build_array(state_license_number)::json
                    ELSE '[]'::json
                END,
                license_expiration_date_new = CASE 
                    WHEN license_expiration_date IS NOT NULL 
                    THEN json_build_array(license_expiration_date::text)::json
                    ELSE '[]'::json
                END,
                license_status_new = CASE 
                    WHEN license_status IS NOT NULL 
                    THEN json_build_array(license_status)::json
                    ELSE '[]'::json
                END
        """))
        conn.commit()
        
        # 3. Drop old columns
        print("  3. Dropping old columns...")
        conn.execute(text("""
            ALTER TABLE suppliers 
            DROP COLUMN IF EXISTS state_license_number,
            DROP COLUMN IF EXISTS license_expiration_date,
            DROP COLUMN IF EXISTS license_status
        """))
        conn.commit()
        
        # 4. Rename new columns to original names
        print("  4. Renaming new columns...")
        conn.execute(text("""
            ALTER TABLE suppliers 
            RENAME COLUMN state_license_number_new TO state_license_number;
            
            ALTER TABLE suppliers 
            RENAME COLUMN license_expiration_date_new TO license_expiration_date;
            
            ALTER TABLE suppliers 
            RENAME COLUMN license_status_new TO license_status
        """))
        conn.commit()
        
        print("  ✓ Suppliers table updated")
        
        print("\n✅ Migration completed successfully!")
        print("\nColumns converted to JSON arrays:")
        print("  - state_license_number: String -> JSON array")
        print("  - license_expiration_date: Date -> JSON array")
        print("  - license_status: String -> JSON array")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
