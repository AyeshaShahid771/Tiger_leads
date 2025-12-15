"""
Migration script to remove credit_cost column from jobs table.
TRS score will now be used as the credit cost when unlocking jobs.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    sys.exit(1)

try:
    # Connect to database
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    print("🔄 Removing credit_cost column from jobs table...")

    # Remove credit_cost column
    cursor.execute(
        """
        ALTER TABLE jobs DROP COLUMN IF EXISTS credit_cost;
    """
    )

    conn.commit()
    print("✅ Successfully removed credit_cost column")
    print("ℹ️  TRS score will now be used as credit cost for unlocking jobs")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
    sys.exit(1)
