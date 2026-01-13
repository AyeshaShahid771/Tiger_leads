"""
Migration script to create temporary_uploads table for document preview.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create engine
engine = create_engine(DATABASE_URL)

def create_temporary_uploads_table():
    """Create temporary_uploads table"""
    
    with engine.connect() as conn:
        print("Creating temporary_uploads table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS temporary_uploads (
                id SERIAL PRIMARY KEY,
                temp_upload_id VARCHAR(100) UNIQUE NOT NULL,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                documents JSON NOT NULL,
                linked_to_job BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # Create index for faster lookups
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_temp_uploads_temp_id 
            ON temporary_uploads(temp_upload_id);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_temp_uploads_user_id 
            ON temporary_uploads(user_id);
        """))
        
        conn.commit()
        print("✓ Migration completed successfully!")
        print("  - Created temporary_uploads table")
        print("  - Created indexes on temp_upload_id and user_id")

if __name__ == "__main__":
    print("Starting migration: Create temporary_uploads table")
    print("=" * 50)
    create_temporary_uploads_table()
    print("=" * 50)
    print("Migration finished!")
