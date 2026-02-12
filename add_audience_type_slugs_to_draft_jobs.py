"""
Migration script to add audience_type_slugs column to draft_jobs table.
This allows draft jobs to store slugs for matching logic (same as Job model).
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)


def add_audience_type_slugs_column():
    """Add audience_type_slugs column to draft_jobs table."""

    with engine.connect() as conn:
        try:
            # Start transaction
            trans = conn.begin()

            # Add audience_type_slugs column
            print("Adding audience_type_slugs column to draft_jobs table...")
            conn.execute(
                text(
                    """
                ALTER TABLE draft_jobs 
                ADD COLUMN IF NOT EXISTS audience_type_slugs TEXT
            """
                )
            )

            # Commit transaction
            trans.commit()
            print("✓ Successfully added audience_type_slugs column")

        except Exception as e:
            trans.rollback()
            print(f"✗ Error adding column: {e}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("Draft Jobs Audience Type Slugs Migration")
    print("=" * 60)

    try:
        add_audience_type_slugs_column()
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)
