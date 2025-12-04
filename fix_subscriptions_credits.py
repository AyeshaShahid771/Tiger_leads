"""
Migration script to add missing credits column to subscriptions table.
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
    """Add credits column if missing."""
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
        print("Checking subscriptions table structure...")
        
        # Check current columns
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'subscriptions'
            ORDER BY ordinal_position;
        """)
        
        columns = cursor.fetchall()
        print("\nCurrent columns in subscriptions table:")
        for col in columns:
            print(f"  - {col[0]} ({col[1]})")
        
        # Add credits column if it doesn't exist
        cursor.execute("""
            ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS credits INTEGER NOT NULL DEFAULT 0;
        """)
        
        print("\n✅ Added 'credits' column to subscriptions table")
        
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
