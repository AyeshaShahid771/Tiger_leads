"""
Add contact_name column to jobs table
Run this script to add the missing contact_name column
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import text
from app.core.database import engine

def run_migration():
    """Add contact_name column to jobs table"""
    
    try:
        with engine.connect() as conn:
            print("Connected to database successfully")
            
            # Check if column already exists
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='jobs' AND column_name='contact_name'
            """))
            
            if result.fetchone():
                print("✓ Column 'contact_name' already exists in jobs table")
                return True
            
            # Add contact_name column
            print("Adding contact_name column to jobs table...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN contact_name VARCHAR(255);
            """))
            
            conn.commit()
            print("✓ Successfully added contact_name column to jobs table")
            
            # Verify the column was added
            result = conn.execute(text("""
                SELECT column_name, data_type, character_maximum_length
                FROM information_schema.columns 
                WHERE table_name='jobs' AND column_name='contact_name'
            """))
            
            row = result.fetchone()
            if row:
                print(f"✓ Verified: contact_name column exists")
                print(f"  - Type: {row[1]}")
                print(f"  - Max Length: {row[2]}")
            
            return True
            
    except Exception as e:
        print(f"ERROR: Migration failed - {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Migration: Add contact_name column to jobs table")
    print("=" * 60)
    
    success = run_migration()
    
    if success:
        print("\n✅ Migration completed successfully!")
    else:
        print("\n❌ Migration failed!")
        sys.exit(1)
