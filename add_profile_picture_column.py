"""
Migration script to add profile_picture column to users table.

This column will store the filename of the user's profile picture.
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


def add_profile_picture_column():
    """Add profile_picture column to users table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            text(
                """
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name = 'profile_picture'
                """
            )
        )
        
        if result.fetchone():
            print("✅ Column 'profile_picture' already exists in 'users' table")
            return
        
        # Add the column
        conn.execute(
            text(
                """
                ALTER TABLE users 
                ADD COLUMN profile_picture VARCHAR(255)
                """
            )
        )
        conn.commit()
        print("✅ Successfully added 'profile_picture' column to 'users' table")


def verify_column():
    """Verify the column was added successfully."""
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'users' 
                AND column_name = 'profile_picture'
                """
            )
        )
        
        row = result.fetchone()
        if row:
            print(f"\n✅ Verification successful:")
            print(f"   Column: {row[0]}")
            print(f"   Type: {row[1]}")
            print(f"   Nullable: {row[2]}")
        else:
            print("❌ Column not found!")


if __name__ == "__main__":
    print("Adding profile_picture column to users table...")
    add_profile_picture_column()
    verify_column()
    print("\n✅ Migration complete!")
