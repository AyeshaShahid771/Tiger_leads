"""
Migration script to add job_documents column to jobs table.
This column stores uploaded PDF/JPG documents for contractor-uploaded jobs.
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

def add_job_documents_column():
    """Add job_documents column to jobs table"""
    
    with engine.connect() as conn:
        # Add job_documents column
        print("Adding job_documents column to jobs table...")
        conn.execute(text("""
            ALTER TABLE jobs 
            ADD COLUMN IF NOT EXISTS job_documents JSON;
        """))
        
        conn.commit()
        print("✓ Migration completed successfully!")
        print("  - Added job_documents column (JSON)")
        print("  - This column will store uploaded PDF/JPG files as base64 encoded JSON array")

if __name__ == "__main__":
    print("Starting migration: Add job_documents column")
    print("=" * 50)
    add_job_documents_column()
    print("=" * 50)
    print("Migration finished!")
