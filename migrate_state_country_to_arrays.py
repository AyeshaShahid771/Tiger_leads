"""
Migration script to convert state and country_city columns to ARRAY type.

This script:
1. Adds new country_city column as ARRAY
2. Converts state from String to ARRAY
3. Migrates existing data from source_county to country_city array
4. Migrates existing state string to state array
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def migrate():
    """Execute the migration."""
    db = SessionLocal()
    try:
        print("Starting migration: Converting state and adding country_city as arrays...")

        # Step 1: Add country_city column as ARRAY
        print("\n1. Adding country_city column as ARRAY...")
        db.execute(text("""
            ALTER TABLE jobs 
            ADD COLUMN IF NOT EXISTS country_city TEXT[]
        """))
        db.commit()
        print("✓ country_city column added")

        # Step 2: Migrate data from source_county to country_city array
        print("\n2. Migrating data from source_county to country_city...")
        db.execute(text("""
            UPDATE jobs 
            SET country_city = ARRAY[source_county]::TEXT[]
            WHERE source_county IS NOT NULL AND source_county != ''
        """))
        db.commit()
        print("✓ Data migrated to country_city array")

        # Step 3: Create temporary column for state array
        print("\n3. Creating temporary state_array column...")
        db.execute(text("""
            ALTER TABLE jobs 
            ADD COLUMN IF NOT EXISTS state_array TEXT[]
        """))
        db.commit()
        print("✓ state_array column added")

        # Step 4: Migrate existing state data to array
        print("\n4. Migrating state data to array format...")
        db.execute(text("""
            UPDATE jobs 
            SET state_array = ARRAY[state]::TEXT[]
            WHERE state IS NOT NULL AND state != ''
        """))
        db.commit()
        print("✓ State data migrated to array")

        # Step 5: Drop old state column
        print("\n5. Dropping old state column...")
        db.execute(text("""
            ALTER TABLE jobs 
            DROP COLUMN IF EXISTS state
        """))
        db.commit()
        print("✓ Old state column dropped")

        # Step 6: Rename state_array to state
        print("\n6. Renaming state_array to state...")
        db.execute(text("""
            ALTER TABLE jobs 
            RENAME COLUMN state_array TO state
        """))
        db.commit()
        print("✓ Column renamed to state")

        # Step 7: Add index on state array
        print("\n7. Adding index on state array...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_state 
            ON jobs USING GIN (state)
        """))
        db.commit()
        print("✓ Index added on state")

        # Step 8: Add index on country_city array
        print("\n8. Adding index on country_city array...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_country_city 
            ON jobs USING GIN (country_city)
        """))
        db.commit()
        print("✓ Index added on country_city")

        print("\n✅ Migration completed successfully!")
        print("\nSummary:")
        print("- Added country_city as TEXT[] with data from source_county")
        print("- Converted state from String to TEXT[]")
        print("- Added GIN indexes for array searching")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
