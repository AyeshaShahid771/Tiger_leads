"""
Migration script to remove credit_price and seat_price columns from subscriptions table.
Also removes the Custom tier if it exists.

Run this script once to update the database schema.
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment variables")
    sys.exit(1)

# Create engine
engine = create_engine(DATABASE_URL)


def run_migration():
    """Remove credit_price and seat_price columns from subscriptions table."""

    print("Starting migration to remove custom pricing columns...")

    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            try:
                # Delete Custom tier if it exists
                print("Removing Custom tier from subscriptions...")
                conn.execute(text("DELETE FROM subscriptions WHERE name = 'Custom'"))

                # Drop credit_price column
                print("Dropping credit_price column...")
                conn.execute(
                    text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS credit_price")
                )

                # Drop seat_price column
                print("Dropping seat_price column...")
                conn.execute(
                    text("ALTER TABLE subscriptions DROP COLUMN IF EXISTS seat_price")
                )

                # Commit transaction
                trans.commit()
                print("✅ Migration completed successfully!")
                print("   - Removed Custom tier")
                print("   - Removed credit_price column")
                print("   - Removed seat_price column")

            except Exception as e:
                # Rollback on error
                trans.rollback()
                print(f"❌ Error during migration: {e}")
                raise

    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    response = input(
        "This will remove credit_price and seat_price columns and delete Custom tier. Continue? (yes/no): "
    )
    if response.lower() == "yes":
        run_migration()
    else:
        print("Migration cancelled.")
        print("Migration cancelled.")
