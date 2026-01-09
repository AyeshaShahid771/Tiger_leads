"""
Migration script to fix column naming - keep source_county as the array column.

This script:
1. Drops the country_city column (data already in source_county)
2. Converts source_county from String to ARRAY if not already
3. Adds GIN index on source_county
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
        print("Starting migration: Fixing source_county as array column...")

        # Step 1: Check if source_county is already an array
        print("\n1. Checking source_county column type...")
        result = db.execute(text("""
            SELECT data_type 
            FROM information_schema.columns 
            WHERE table_name='jobs' AND column_name='source_county'
        """))
        current_type = result.scalar()
        print(f"Current type: {current_type}")

        # Step 2: If source_county is not array, convert it
        if current_type != 'ARRAY':
            print("\n2. Converting source_county to array...")
            
            # Create temp column
            db.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS source_county_array TEXT[]
            """))
            db.commit()
            
            # Migrate data
            db.execute(text("""
                UPDATE jobs 
                SET source_county_array = ARRAY[source_county]::TEXT[]
                WHERE source_county IS NOT NULL AND source_county != ''
            """))
            db.commit()
            
            # Drop old column
            db.execute(text("""
                ALTER TABLE jobs 
                DROP COLUMN source_county
            """))
            db.commit()
            
            # Rename new column
            db.execute(text("""
                ALTER TABLE jobs 
                RENAME COLUMN source_county_array TO source_county
            """))
            db.commit()
            print("✓ source_county converted to array")
        else:
            print("✓ source_county is already an array")

        # Step 3: Drop country_city column if it exists
        print("\n3. Dropping country_city column...")
        db.execute(text("""
            ALTER TABLE jobs 
            DROP COLUMN IF EXISTS country_city
        """))
        db.commit()
        print("✓ country_city column dropped")

        # Step 4: Drop old index if exists
        print("\n4. Dropping old country_city index...")
        db.execute(text("""
            DROP INDEX IF EXISTS idx_jobs_country_city
        """))
        db.commit()
        print("✓ Old index dropped")

        # Step 5: Add index on source_county
        print("\n5. Adding index on source_county...")
        db.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_source_county 
            ON jobs USING GIN (source_county)
        """))
        db.commit()
        print("✓ Index added on source_county")

        print("\n✅ Migration completed successfully!")
        print("\nSummary:")
        print("- source_county is now TEXT[] array")
        print("- country_city column removed")
        print("- GIN index created on source_county")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
