"""
Migration script to add credit_price and seat_price columns to subscriptions table.
This supports Custom tier pricing where credits and seats have individual prices.
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


def add_pricing_columns():
    """Add credit_price and seat_price columns to subscriptions table."""

    with engine.connect() as conn:
        try:
            # Start transaction
            trans = conn.begin()

            # Add credit_price column
            print("Adding credit_price column to subscriptions table...")
            conn.execute(
                text(
                    """
                ALTER TABLE subscriptions 
                ADD COLUMN IF NOT EXISTS credit_price VARCHAR(20)
            """
                )
            )

            # Add seat_price column
            print("Adding seat_price column to subscriptions table...")
            conn.execute(
                text(
                    """
                ALTER TABLE subscriptions 
                ADD COLUMN IF NOT EXISTS seat_price VARCHAR(20)
            """
                )
            )

            # Commit transaction
            trans.commit()
            print("✓ Successfully added credit_price and seat_price columns")

        except Exception as e:
            trans.rollback()
            print(f"✗ Error adding columns: {e}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("Subscription Pricing Columns Migration")
    print("=" * 60)

    try:
        add_pricing_columns()
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
    except Exception as e:
        print(f"\nMigration failed: {e}")
        sys.exit(1)
        sys.exit(1)
