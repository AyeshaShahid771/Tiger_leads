"""
Migration: Add token revocation columns to users table

Adds:
- last_logout_at: Track when user last logged out (for token revocation)
- last_password_change_at: Track when password was last changed (for token revocation)
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def run_migration():
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Check if columns already exist
        check_last_logout = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'last_logout_at'
        """
        )

        check_last_password_change = text(
            """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' 
            AND column_name = 'last_password_change_at'
        """
        )

        result_logout = conn.execute(check_last_logout).fetchone()
        result_password = conn.execute(check_last_password_change).fetchone()

        # Add last_logout_at if it doesn't exist
        if not result_logout:
            print("Adding last_logout_at column to users table...")
            add_logout_col = text(
                """
                ALTER TABLE users 
                ADD COLUMN last_logout_at TIMESTAMP NULL
            """
            )
            conn.execute(add_logout_col)
            conn.commit()
            print("✓ Added last_logout_at column")
        else:
            print("✓ last_logout_at column already exists")

        # Add last_password_change_at if it doesn't exist
        if not result_password:
            print("Adding last_password_change_at column to users table...")
            add_password_col = text(
                """
                ALTER TABLE users 
                ADD COLUMN last_password_change_at TIMESTAMP NULL
            """
            )
            conn.execute(add_password_col)
            conn.commit()
            print("✓ Added last_password_change_at column")
        else:
            print("✓ last_password_change_at column already exists")

        print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    run_migration()
