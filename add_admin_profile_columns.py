r"""
Migration script to add profile picture and name columns to admin_users table.

Adds:
- name: VARCHAR(255) - Admin's name
- profile_picture_data: BYTEA - Binary profile picture data
- profile_picture_content_type: VARCHAR(50) - MIME type (e.g., 'image/jpeg')
- password_hash: VARCHAR - Password hash (if not exists)

Run this script with:
    Tiger_leads\Scripts\activate.bat
    python add_admin_profile_columns.py
"""

import os
import sys

from sqlalchemy import create_engine, text

# Add the project root to the path
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


def add_admin_profile_columns():
    """Add profile-related columns to admin_users table."""
    with engine.connect() as conn:
        columns_to_add = [
            ("name", "VARCHAR(255)", "Admin's name"),
            ("password_hash", "VARCHAR", "Password hash for authentication"),
            ("profile_picture_data", "BYTEA", "Profile picture binary data"),
            (
                "profile_picture_content_type",
                "VARCHAR(50)",
                "MIME type (e.g., 'image/jpeg')",
            ),
        ]

        for column_name, column_type, description in columns_to_add:
            if check_column_exists("admin_users", column_name):
                print(
                    f"✅ Column '{column_name}' already exists in 'admin_users' table"
                )
            else:
                try:
                    conn.execute(
                        text(
                            f"""
                            ALTER TABLE admin_users 
                            ADD COLUMN {column_name} {column_type}
                            """
                        )
                    )
                    conn.commit()
                    print(
                        f"✅ Successfully added '{column_name}' column ({description})"
                    )
                except Exception as e:
                    print(f"❌ Error adding '{column_name}': {str(e)}")
                    conn.rollback()


def verify_columns():
    """Verify all columns were added successfully."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'admin_users' 
                AND column_name IN ('name', 'password_hash', 'profile_picture_data', 'profile_picture_content_type')
                ORDER BY column_name
                """
            )
        )

        rows = result.fetchall()
        if rows:
            print(f"\n✅ Verification successful - Found {len(rows)} columns:")
            for row in rows:
                print(f"   - {row[0]}: {row[1]} (Nullable: {row[2]})")
        else:
            print("⚠️  No new columns found!")


if __name__ == "__main__":
    print("=" * 60)
    print("Adding profile columns to admin_users table...")
    print("=" * 60)
    add_admin_profile_columns()
    verify_columns()
    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
    print("=" * 60)
