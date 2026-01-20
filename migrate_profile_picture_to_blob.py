"""
Migration: Change profile_picture from VARCHAR to BYTEA (binary data)
This allows storing profile pictures directly in the database instead of filesystem.
Works on Vercel's read-only filesystem.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def migrate_profile_picture_to_blob():
    """Change profile_picture column to store binary data and add content_type."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            print("Starting migration: profile_picture to BLOB storage...")
            
            # Step 1: Add new columns for binary storage
            print("\n1. Adding profile_picture_data (BYTEA) column...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS profile_picture_data BYTEA;
            """))
            
            print("2. Adding profile_picture_content_type (VARCHAR) column...")
            conn.execute(text("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS profile_picture_content_type VARCHAR(50);
            """))
            
            # Step 2: Drop old profile_picture column (filename storage)
            print("3. Dropping old profile_picture column...")
            conn.execute(text("""
                ALTER TABLE users 
                DROP COLUMN IF EXISTS profile_picture;
            """))
            
            conn.commit()
            
            print("\n✅ Migration completed successfully!")
            print("\nNew schema:")
            print("  - profile_picture_data: BYTEA (stores image binary data)")
            print("  - profile_picture_content_type: VARCHAR(50) (stores MIME type like 'image/jpeg')")
            
        except Exception as e:
            print(f"\n❌ Error during migration: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    migrate_profile_picture_to_blob()
