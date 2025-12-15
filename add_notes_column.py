"""
Migration script to add notes column to unlocked_leads table.
"""

import os

import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def add_notes_column():
    """Add notes column to unlocked_leads table"""
    try:
        # Connect to database
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()

        print("Adding notes column to unlocked_leads table...")

        # Add notes column
        cursor.execute(
            """
            ALTER TABLE unlocked_leads 
            ADD COLUMN IF NOT EXISTS notes TEXT;
        """
        )

        conn.commit()
        print("✓ Notes column added successfully!")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    add_notes_column()
    print("\nMigration completed!")
    print("\nMigration completed!")
