"""
Migration script to add missing columns to contractors table.
Run this once to update the database schema.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    exit(1)

print(f"Connecting to database...")
print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")

engine = create_engine(DATABASE_URL)

# SQL to add missing columns
sql_commands = [
    """
    ALTER TABLE contractors 
    ADD COLUMN IF NOT EXISTS state VARCHAR(255);
    """,
    """
    ALTER TABLE contractors 
    ADD COLUMN IF NOT EXISTS country_city VARCHAR(255);
    """,
    """
    ALTER TABLE suppliers 
    ADD COLUMN IF NOT EXISTS country_city VARCHAR(255);
    """,
]

try:
    with engine.connect() as conn:
        for sql in sql_commands:
            print(f"\nExecuting: {sql.strip()}")
            conn.execute(text(sql))
            conn.commit()
            print("✓ Success")

    print("\n" + "=" * 50)
    print("✓ All columns added successfully!")
    print("=" * 50)
    print("\nYou can now:")
    print("1. Restart your Vercel deployment (or wait for auto-deploy)")
    print("2. Test your API endpoints")

except Exception as e:
    print(f"\n✗ Error: {str(e)}")
    print("\nThis might mean:")
    print("- Database connection failed")
    print("- Columns already exist (not an error)")
    print("- Permission issues")

finally:
    engine.dispose()
