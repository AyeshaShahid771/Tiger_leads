"""
Migration script to revert state and source_county back to STRING type.

This script:
1. Converts state from ARRAY back to String
2. Converts source_county from ARRAY back to String
3. Removes GIN indexes
4. Adds regular indexes
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
        print("Starting migration: Reverting state and source_county to STRING type...")

        # Step 1: Drop GIN indexes
        print("\n1. Dropping GIN indexes...")
        db.execute(text("DROP INDEX IF EXISTS idx_jobs_state"))
        db.execute(text("DROP INDEX IF EXISTS idx_jobs_source_county"))
        db.commit()
        print("✓ GIN indexes dropped")

        # Step 2: Convert state from ARRAY to String
        print("\n2. Converting state from ARRAY to String...")
        
        # Create temp column
        db.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS state_temp VARCHAR(100)"))
        db.commit()
        
        # Migrate data - take first element if array, otherwise NULL
        db.execute(text("""
            UPDATE jobs 
            SET state_temp = CASE 
                WHEN state IS NOT NULL AND array_length(state, 1) > 0 
                THEN state[1]
                ELSE NULL
            END
        """))
        db.commit()
        
        # Drop old column
        db.execute(text("ALTER TABLE jobs DROP COLUMN state"))
        db.commit()
        
        # Rename new column
        db.execute(text("ALTER TABLE jobs RENAME COLUMN state_temp TO state"))
        db.commit()
        print("✓ state converted to String")

        # Step 3: Convert source_county from ARRAY to String
        print("\n3. Converting source_county from ARRAY to String...")
        
        # Create temp column
        db.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS source_county_temp VARCHAR(100)"))
        db.commit()
        
        # Migrate data - take first element if array, otherwise NULL
        db.execute(text("""
            UPDATE jobs 
            SET source_county_temp = CASE 
                WHEN source_county IS NOT NULL AND array_length(source_county, 1) > 0 
                THEN source_county[1]
                ELSE NULL
            END
        """))
        db.commit()
        
        # Drop old column
        db.execute(text("ALTER TABLE jobs DROP COLUMN source_county"))
        db.commit()
        
        # Rename new column
        db.execute(text("ALTER TABLE jobs RENAME COLUMN source_county_temp TO source_county"))
        db.commit()
        print("✓ source_county converted to String")

        # Step 4: Add regular index on state
        print("\n4. Adding regular index on state...")
        db.execute(text("CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)"))
        db.commit()
        print("✓ Index added on state")

        print("\n✅ Migration completed successfully!")
        print("\nSummary:")
        print("- state is now VARCHAR(100)")
        print("- source_county is now VARCHAR(100)")
        print("- Regular B-tree indexes added")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    migrate()
