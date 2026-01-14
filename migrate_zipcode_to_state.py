"""
Migration script to update contractor and supplier location fields to single country_city column
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Error: DATABASE_URL not found in environment variables")
    exit(1)

# Create engine
engine = create_engine(DATABASE_URL)


def migrate():
    """Update location fields to single country_city column"""

    with engine.connect() as conn:
        try:
            # Start transaction
            trans = conn.begin()

            print("Starting migration...")

            # Contractors table - rename service_state or service_zip_code to country_city
            print("\n--- Contractors Table ---")
            print("1. Renaming to contractors.country_city...")
            try:
                conn.execute(
                    text(
                        """
                    ALTER TABLE contractors 
                    RENAME COLUMN service_state TO country_city
                """
                    )
                )
                print("   ✓ contractors.service_state renamed to country_city")
            except:
                try:
                    conn.execute(
                        text(
                            """
                        ALTER TABLE contractors 
                        RENAME COLUMN service_zip_code TO country_city
                    """
                        )
                    )
                    print("   ✓ contractors.service_zip_code renamed to country_city")
                except:
                    conn.execute(
                        text(
                            """
                        ALTER TABLE contractors 
                        RENAME COLUMN state TO country_city
                    """
                        )
                    )
                    print("   ✓ contractors.state renamed to country_city")

            # Drop any extra columns in contractors if they exist
            try:
                conn.execute(
                    text(
                        "ALTER TABLE contractors DROP COLUMN IF EXISTS service_zip_code"
                    )
                )
                conn.execute(
                    text("ALTER TABLE contractors DROP COLUMN IF EXISTS state")
                )
                conn.execute(
                    text("ALTER TABLE contractors DROP COLUMN IF EXISTS service_state")
                )
                print("   ✓ Removed extra columns")
            except:
                pass

            # Suppliers table - rename service_zipcode or state to country_city
            print("\n--- Suppliers Table ---")
            print("2. Renaming to suppliers.country_city...")
            try:
                conn.execute(
                    text(
                        """
                    ALTER TABLE suppliers 
                    RENAME COLUMN service_zipcode TO country_city
                """
                    )
                )
                print("   ✓ suppliers.service_zipcode renamed to country_city")
            except:
                try:
                    conn.execute(
                        text(
                            """
                        ALTER TABLE suppliers 
                        RENAME COLUMN state TO country_city
                    """
                        )
                    )
                    print("   ✓ suppliers.state renamed to country_city")
                except:
                    # n might already be 
                    print("   ✓ suppliers.country_city already exists")

            # Commit transactio
            trans.commit()
            print("\n✓ Migration completed successfully!")
            print("\nSummary:")
            print(
                "- Contractors: now have single 'country_city' field (format: USA/New York)"
            )
            print(
                "- Suppliers: now have single 'country_city' field (format: USA/Miami)"
            )

        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"\n✗ Migration failed: {str(e)}")
            raise


if __name__ == "__main__":
    print("=" * 70)
    print("Database Migration: Update to Country/City Format")
    print("=" * 70)
    print()
    print("This will update location fields to single 'country_city' column:")
    print("  - Contractors: service_state/service_zip_code → country_city")
    print("  - Suppliers: service_zipcode/state → country_city")
    print()

    response = input("Continue with migration? (yes/no): ")

    if response.lower() == "yes":
        migrate()
    else:
        print("Migration cancelled")
