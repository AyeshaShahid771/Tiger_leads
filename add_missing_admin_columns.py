r"""
Migration script to add missing columns to admin_users table.

Adds (if not already present):
- note: VARCHAR(255) - Admin notes
- subscription_status: VARCHAR(50) - Subscription status
- profile_picture_data: BYTEA - Binary profile picture data
- profile_picture_content_type: VARCHAR(50) - MIME type
- name: VARCHAR(255) - Admin's name
- password_hash: VARCHAR - Password hash

Run this script with:
    .venv\Scripts\python.exe add_missing_admin_columns.py
"""

import os
import sys

from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

engine = create_engine(DATABASE_URL)


def check_column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = :table 
                AND column_name = :column
                """
            ),
            {"table": table_name, "column": column_name},
        )
        return result.fetchone() is not None


def add_missing_columns():
    """Add all missing columns to admin_users table."""
    columns_to_add = [
        ("note", "VARCHAR(255)", "Admin notes"),
        ("subscription_status", "VARCHAR(50) DEFAULT 'inactive'", "Subscription status"),
        ("profile_picture_data", "BYTEA", "Profile picture binary data"),
        ("profile_picture_content_type", "VARCHAR(50)", "MIME type"),
        ("name", "VARCHAR(255)", "Admin name"),
        ("password_hash", "VARCHAR", "Password hash"),
    ]

    with engine.connect() as conn:
        for column_name, column_type, description in columns_to_add:
            if check_column_exists("admin_users", column_name):
                print(f"  OK  Column '{column_name}' already exists")
            else:
                try:
                    conn.execute(
                        text(
                            f"ALTER TABLE admin_users ADD COLUMN {column_name} {column_type}"
                        )
                    )
                    conn.commit()
                    print(f"  ADDED  '{column_name}' ({description})")
                except Exception as e:
                    print(f"  ERROR  adding '{column_name}': {str(e)}")
                    conn.rollback()


def verify():
    """Show current admin_users columns."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'admin_users'
                ORDER BY ordinal_position
                """
            )
        )
        rows = result.fetchall()
        print(f"\nadmin_users table has {len(rows)} columns:")
        for row in rows:
            print(f"   {row[0]}: {row[1]}")


if __name__ == "__main__":
    print("=" * 50)
    print("Adding missing columns to admin_users...")
    print("=" * 50)
    add_missing_columns()
    verify()
    print("\nDone!")
