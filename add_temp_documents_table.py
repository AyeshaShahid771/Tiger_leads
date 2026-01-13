"""
Migration script to add temp_documents table for preview functionality.
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

def add_temp_documents_table():
    """Create temp_documents table"""
    
    with engine.connect() as conn:
        print("Creating temp_documents table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS temp_documents (
                id SERIAL PRIMARY KEY,
                temp_upload_id VARCHAR(100) UNIQUE NOT NULL,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                documents JSON NOT NULL,
                linked_to_job BOOLEAN DEFAULT FALSE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL
            );
        """))
        
        print("Creating indexes...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_temp_documents_temp_upload_id 
            ON temp_documents(temp_upload_id);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_temp_documents_user_id 
            ON temp_documents(user_id);
        """))
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_temp_documents_expires_at 
            ON temp_documents(expires_at);
        """))
        
        conn.commit()
        print("✓ Migration completed successfully!")
        print("  - Created temp_documents table")
        print("  - Created indexes on temp_upload_id, user_id, expires_at")

if __name__ == "__main__":
    print("Starting migration: Add temp_documents table")
    print("=" * 50)
    add_temp_documents_table()
    print("=" * 50)
    print("Migration finished!")
