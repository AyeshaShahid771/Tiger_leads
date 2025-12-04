"""
Database Schema Change: Update Jobs table structure
This script:
1. Adds the new country_city column
2. Drops the old city and country columns
"""

import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection from .env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env file")
    sys.exit(1)

def alter_jobs_schema():
    """Change Jobs table schema to use country_city instead of separate city and country columns"""
    
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("=" * 80)
        print("SCHEMA CHANGE: Updating Jobs table structure")
        print("=" * 80)
        
        # Step 1: Add country_city column
        print("\n[1/3] Adding country_city column to jobs table...")
        try:
            session.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS country_city VARCHAR(100);
            """))
            session.commit()
            print("✓ country_city column added successfully")
        except Exception as e:
            print(f"✗ Error adding column: {e}")
            session.rollback()
            return False
        
        # Step 2: Add index to country_city column
        print("\n[2/3] Adding index to country_city column...")
        try:
            session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_country_city 
                ON jobs(country_city);
            """))
            session.commit()
            print("✓ Index created successfully")
        except Exception as e:
            print(f"✗ Error creating index: {e}")
            session.rollback()
        
        # Step 3: Drop old city and country columns
        print("\n[3/3] Dropping old city and country columns...")
        try:
            session.execute(text("""
                ALTER TABLE jobs 
                DROP COLUMN IF EXISTS city,
                DROP COLUMN IF EXISTS country;
            """))
            session.commit()
            print("✓ Old columns dropped successfully")
        except Exception as e:
            print(f"✗ Error dropping columns: {e}")
            session.rollback()
            return False
        
        print("\n" + "=" * 80)
        print("SCHEMA CHANGE COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("\nSummary:")
        print("- Added country_city column (VARCHAR 100)")
        print("- Added index for performance")
        print("- Dropped old city and country columns")
        print("\nNew Jobs table structure:")
        print("  - state (VARCHAR 100)")
        print("  - country_city (VARCHAR 100)")
        
        return True
        
    except Exception as e:
        print(f"\n✗ SCHEMA CHANGE FAILED: {e}")
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("JOBS TABLE SCHEMA CHANGE")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Add a new 'country_city' column")
    print("2. Drop the old 'city' and 'country' columns")
    print("\n⚠️  WARNING: This will DELETE any existing data in city/country columns!")
    print("=" * 80)
    
    response = input("\nDo you want to proceed? (yes/no): ").strip().lower()
    
    if response == 'yes':
        success = alter_jobs_schema()
        sys.exit(0 if success else 1)
    else:
        print("\nSchema change cancelled by user.")
        sys.exit(0)
