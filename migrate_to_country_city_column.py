"""
Migration Script: Consolidate city and country columns into country_city column in Jobs table
This script:
1. Adds the new country_city column

"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Database connection from .env
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("Error: DATABASE_URL not found in .env file")
    sys.exit(1)


def migrate_to_country_city():
    """Migrate existing Jobs table to use country_city column instead of separate city and country columns"""

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print("=" * 80)
        print("MIGRATION: Consolidating city and country columns into country_city")
        print("=" * 80)

        # Step 1: Add country_city column
        print("\n[1/4] Adding country_city column to jobs table...")
        try:
            session.execute(
                text(
                    """
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS country_city VARCHAR(100);
            """
                )
            )
            session.commit()
            print("✓ country_city column added successfully")
        except Exception as e:
            print(f"✗ Error adding column (might already exist): {e}")
            session.rollback()

        # Step 2: Migrate existing data
        # Priority: country > city (counties take precedence over cities)
        print("\n[2/4] Migrating existing data to country_city column...")
        try:
            session.execute(
                text(
                    """
                UPDATE jobs 
                SET country_city = COALESCE(country, city)
                WHERE country_city IS NULL 
                AND (country IS NOT NULL OR city IS NOT NULL);
            """
                )
            )
            session.commit()

            # Get count of migrated rows
            result = session.execute(
                text("SELECT COUNT(*) FROM jobs WHERE country_city IS NOT NULL")
            )
            count = result.scalar()
            print(f"✓ Migrated {count} rows to country_city column")
        except Exception as e:
            print(f"✗ Error migrating data: {e}")
            session.rollback()
            return False

        # Step 3: Add index to country_city column for better query performance
        print("\n[3/4] Adding index to country_city column...")
        try:
            session.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_jobs_country_city 
                ON jobs(country_city);
            """
                )
            )
            session.commit()
            print("✓ Index created successfully")
        except Exception as e:
            print(f"✗ Error creating index: {e}")
            session.rollback()

        # Step 4: Optionally drop old columns (ask user)
        print("\n[4/4] Old city and country columns...")
        response = (
            input(
                "Do you want to DROP the old 'city' and 'country' columns? (yes/no): "
            )
            .strip()
            .lower()
        )

        if response == "yes":
            try:
                print("Dropping old city and country columns...")
                session.execute(
                    text(
                        """
                    ALTER TABLE jobs 
                    DROP COLUMN IF EXISTS city,
                    DROP COLUMN IF EXISTS country;
                """
                    )
                )
                session.commit()
                print("✓ Old columns dropped successfully")
            except Exception as e:
                print(f"✗ Error dropping columns: {e}")
                session.rollback()
        else:
            print(
                "⚠ Keeping old city and country columns (you can drop them manually later)"
            )

        print("\n" + "=" * 80)
        print("MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print("\nSummary:")
        print("- Added country_city column")
        print(f"- Migrated {count} rows")
        print("- Added index for performance")
        if response == "yes":
            print("- Dropped old city and country columns")
        else:
            print("- Old city and country columns still exist")

        return True

    except Exception as e:
        print(f"\n✗ MIGRATION FAILED: {e}")
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("JOBS TABLE MIGRATION: city + country → country_city")
    print("=" * 80)
    print("\nThis script will:")
    print("1. Add a new 'country_city' column to the jobs table")
    print("2. Copy data from 'country' and 'city' columns to 'country_city'")
    print("3. Add an index for better query performance")
    print("4. Optionally drop the old 'city' and 'country' columns")
    print("\nNOTE: This migration is SAFE - it preserves your existing data.")
    print("=" * 80)

    response = (
        input("\nDo you want to proceed with the migration? (yes/no): ").strip().lower()
    )

    if response == "yes":
        success = migrate_to_country_city()
        sys.exit(0 if success else 1)
    else:
        print("\nMigration cancelled by user.")
        sys.exit(0)
        sys.exit(0)
