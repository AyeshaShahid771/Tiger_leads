"""
Migration script to add Custom tier to subscriptions table.

Run this script once to add the Custom tier with credit_price and seat_price.
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
    """Add Custom tier to subscriptions table."""

    print("Starting migration to add Custom tier...")

    try:
        with engine.connect() as conn:
            # Start transaction
            trans = conn.begin()

            try:
                # Check if Custom tier already exists
                result = conn.execute(
                    text("SELECT COUNT(*) FROM subscriptions WHERE name = 'Custom'")
                )
                count = result.scalar()

                if count > 0:
                    print("⚠️  Custom tier already exists. Skipping insertion.")
                    trans.rollback()
                    return

                # Insert Custom tier
                print("Adding Custom tier to subscriptions table...")
                conn.execute(
                    text(
                        """
                    INSERT INTO subscriptions 
                    (name, price, credits, max_seats, credit_price, seat_price, stripe_price_id, stripe_product_id) 
                    VALUES 
                    ('Custom', '0', 0, 0, NULL, NULL, NULL, NULL)
                    """
                    )
                )

                # Commit transaction
                trans.commit()
                print("✅ Migration completed successfully!")
                print("   - Added Custom tier to subscriptions table")
                print(
                    "   - You can now update credit_price and seat_price using the admin endpoint"
                )

            except Exception as e:
                # Rollback on error
                trans.rollback()
                print(f"❌ Error during migration: {e}")
                raise

    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("\nThis will add a Custom tier to the subscriptions table.")
    print("The Custom tier will have:")
    print("  - name: 'Custom'")
    print("  - price: '0' (not used for Custom)")
    print("  - credits: 0 (not used for Custom)")
    print("  - max_seats: 0 (not used for Custom)")
    print("  - credit_price: NULL (to be set by admin)")
    print("  - seat_price: NULL (to be set by admin)")
    print()
    response = input("Continue? (yes/no): ")
    if response.lower() == "yes":
        run_migration()
    else:
        print("Migration cancelled.")
        print("Migration cancelled.")
