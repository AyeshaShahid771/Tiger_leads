"""
Migration script to update contractor fields:

Step 1 changes:
1. Adds the business_website_url column
2. Drops the business_type column
3. Drops the years_in_business column

Step 3 changes:
4. Adds the user_type column (array of strings)
5. Drops the trade_categories column
6. Drops the trade_specialities column
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)


def run_migration():
    """Execute the migration."""
    with engine.connect() as conn:
        print("=" * 60)
        print("Contractor Fields Migration")
        print("=" * 60)
        
        # Check if business_website_url column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='business_website_url'
        """))
        
        if result.fetchone():
            print("✓ Column 'business_website_url' already exists in contractors table")
        else:
            print("Adding 'business_website_url' column to contractors table...")
            
            # Add business_website_url column
            conn.execute(text("""
                ALTER TABLE contractors
                ADD COLUMN business_website_url VARCHAR(500)
            """))
            conn.commit()
            
            print("✓ Column 'business_website_url' added successfully")
        
        # Check if business_type column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='business_type'
        """))
        
        if result.fetchone():
            print("Dropping 'business_type' column from contractors table...")
            conn.execute(text("""
                ALTER TABLE contractors
                DROP COLUMN business_type
            """))
            conn.commit()
            print("✓ Column 'business_type' dropped successfully")
        else:
            print("✓ Column 'business_type' already removed")
        
        # Check if years_in_business column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='years_in_business'
        """))
        
        if result.fetchone():
            print("Dropping 'years_in_business' column from contractors table...")
            conn.execute(text("""
                ALTER TABLE contractors
                DROP COLUMN years_in_business
            """))
            conn.commit()
            print("✓ Column 'years_in_business' dropped successfully")
        else:
            print("✓ Column 'years_in_business' already removed")
        
        # Step 3 Changes: Add user_type, drop trade_categories and trade_specialities
        print("\n" + "=" * 60)
        print("Step 3 Fields Migration")
        print("=" * 60)
        
        # Check if user_type column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='user_type'
        """))
        
        if result.fetchone():
            print("✓ Column 'user_type' already exists in contractors table")
        else:
            print("Adding 'user_type' column to contractors table...")
            
            # Add user_type column as array of strings
            conn.execute(text("""
                ALTER TABLE contractors
                ADD COLUMN user_type VARCHAR(255)[]
            """))
            conn.commit()
            
            print("✓ Column 'user_type' added successfully")
        
        # Check if trade_categories column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='trade_categories'
        """))
        
        if result.fetchone():
            print("Dropping 'trade_categories' column from contractors table...")
            conn.execute(text("""
                ALTER TABLE contractors
                DROP COLUMN trade_categories
            """))
            conn.commit()
            print("✓ Column 'trade_categories' dropped successfully")
        else:
            print("✓ Column 'trade_categories' already removed")
        
        # Check if trade_specialities column exists before dropping
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='contractors' AND column_name='trade_specialities'
        """))
        
        if result.fetchone():
            print("Dropping 'trade_specialities' column from contractors table...")
            conn.execute(text("""
                ALTER TABLE contractors
                DROP COLUMN trade_specialities
            """))
            conn.commit()
            print("✓ Column 'trade_specialities' dropped successfully")
        else:
            print("✓ Column 'trade_specialities' already removed")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
        # Verify final schema
        print("\nVerifying contractors table schema:")
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name='contractors' 
            AND column_name IN ('business_website_url', 'business_type', 'years_in_business', 
                                'user_type', 'trade_categories', 'trade_specialities')
            ORDER BY column_name
        """))
        
        columns = result.fetchall()
        if columns:
            print("\nMigrated columns:")
            for col in columns:
                print(f"  - {col[0]}: {col[1]} - Nullable: {col[2]}")
        
        # Check which old columns remain (should be none)
        old_columns = [c for c in columns if c[0] in ['business_type', 'years_in_business', 'trade_categories', 'trade_specialities']]
        new_columns = [c for c in columns if c[0] in ['business_website_url', 'user_type']]
        
        if not old_columns and len(new_columns) == 2:
            print("\n✓ All old columns successfully removed")
            print("✓ New columns (business_website_url, user_type) successfully added")
        elif old_columns:
            print(f"\n⚠ Warning: Some old columns still exist: {[c[0] for c in old_columns]}")
        else:
            print(f"\n⚠ Warning: Expected columns may be missing")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
