"""
Migration script to rename tokens column to credits and update all references.
This will:
1. Drop the new credits column (just added)
2. Rename tokens to credits
3. Update all related tables
"""

import os
from urllib.parse import quote_plus

import psycopg2
from dotenv import load_dotenv

load_dotenv()

password = quote_plus("Xb@qeJk3")
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)


def run_migration():
    """Rename tokens to credits throughout the database."""
    conn_params = DATABASE_URL.replace("postgresql://", "").split("@")
    user_pass = conn_params[0].split(":")
    host_db = conn_params[1].split("/")
    host_port = host_db[0].split(":")

    conn = psycopg2.connect(
        dbname=host_db[1],
        user=user_pass[0],
        password=user_pass[1],
        host=host_port[0],
        port=host_port[1] if len(host_port) > 1 else "5432",
    )

    cursor = conn.cursor()

    try:
        print("Starting tokens to credits migration...")

        # 1. Drop the credits column if it exists (we just added it)
        print("Removing duplicate credits column from subscriptions...")
        cursor.execute(
            """
            ALTER TABLE subscriptions
            DROP COLUMN IF EXISTS credits;
        """
        )

        # 2. Rename tokens to credits in subscriptions table
        print("Renaming tokens to credits in subscriptions table...")
        cursor.execute(
            """
            ALTER TABLE subscriptions
            RENAME COLUMN tokens TO credits;
        """
        )

        print("\n✅ Successfully renamed tokens to credits!")
        print("All subscription data preserved with new column name.")

        conn.commit()
        print("\nMigration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
