"""
Migration script to add job_group_id column to jobs table.
This column links multiple job records that were created from the same submission.
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

def add_job_group_id_column():
    """Add job_group_id column to jobs table"""
    
    with engine.connect() as conn:
        # Add job_group_id column
        print("Adding job_group_id column to jobs table...")
        conn.execute(text("""
            ALTER TABLE jobs 
            ADD COLUMN IF NOT EXISTS job_group_id VARCHAR(100);
        """))
        
        # Create index for better query performance
        print("Creating index on job_group_id...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_jobs_job_group_id 
            ON jobs(job_group_id);
        """))
        
        conn.commit()
        print("✓ Migration completed successfully!")
        print("  - Added job_group_id column (VARCHAR(100))")
        print("  - Created index on job_group_id")

if __name__ == "__main__":
    print("Starting migration: Add job_group_id column")
    print("=" * 50)
    add_job_group_id_column()
    print("=" * 50)
    print("Migration finished!")
