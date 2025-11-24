"""
Migration script to add missing country_city column to suppliers table
Run this once to update the database schema
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

try:
    with engine.connect() as conn:
        # Add country_city column to suppliers table
        print("Adding country_city column to suppliers table...")
        conn.execute(
            text(
                "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS country_city VARCHAR(200)"
            )
        )
        conn.commit()
        print("✓ Successfully added country_city column to suppliers table")

except Exception as e:
    print(f"✗ Error during migration: {str(e)}")
    exit(1)

print("\n✓ Migration completed successfully!")
print("You can now use the supplier endpoints.")
