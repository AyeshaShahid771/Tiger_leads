"""
pt to add the new optio file upload fields to the database.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import LargeBinary, String, text

from src.app.core.database import engine


def add_contractor_file_columns():
    """Add referrals and job_photos columns to contractors table."""

    print(
        "Starting migration: Adding referrals and job_photos columns to contractors table..."
    )

    with engine.connect() as conn:
        try:
            # Start transaction
            trans = conn.begin()

            # Add referrals columns
            print("Adding referrals columns...")
            conn.execute(
                text(
                    """
                ALTER TABLE contractors 
                ADD COLUMN IF NOT EXISTS referrals BYTEA,
                ADD COLUMN IF NOT EXISTS referrals_filename VARCHAR(255),
                ADD COLUMN IF NOT EXISTS referrals_content_type VARCHAR(50)
            """
                )
            )

            # Add job_photos columns
            print("Adding job_photos columns...")
            conn.execute(
                text(
                    """
                ALTER TABLE contractors 
                ADD COLUMN IF NOT EXISTS job_photos BYTEA,
                ADD COLUMN IF NOT EXISTS job_photos_filename VARCHAR(255),
                ADD COLUMN IF NOT EXISTS job_photos_content_type VARCHAR(50)
            """
                )
            )

            # Commit transaction
            trans.commit()

            print("✅ Migration completed successfully!")
            print("   - Added referrals, referrals_filename, referrals_content_type")
            print("   - Added job_photos, job_photos_filename, job_photos_content_type")

        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {str(e)}")
            raise


if __name__ == "__main__":
    print("=" * 70)
    print("Contractor Files Migration")
    print("=" * 70)

    try:
        add_contractor_file_columns()
        print("\n" + "=" * 70)
        print("Migration completed! Your database is now up to date.")
        print("=" * 70)
    except Exception as e:
        print("\n" + "=" * 70)
        print("Migration failed. Please check the error above.")
        print("=" * 70)
        sys.exit(1)
        print("=" * 70)
        sys.exit(1)
