"""
Migration script to add review_posted_at column to jobs table.

This column tracks when a job's review status was set to 'posted',
enabling automatic deletion of jobs 7 days after posting.
"""

import os
import sys
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

print(f"Connecting to database...")
engine = create_engine(DATABASE_URL)

def main():
    with engine.connect() as conn:
        # Check if column already exists
        check_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='jobs' AND column_name='review_posted_at'
        """)
        result = conn.execute(check_query).fetchone()
        
        if result:
            print("✓ Column 'review_posted_at' already exists in jobs table")
            return
        
        print("Adding 'review_posted_at' column to jobs table...")
        
        # Add the column
        add_column_query = text("""
            ALTER TABLE jobs 
            ADD COLUMN review_posted_at TIMESTAMP
        """)
        conn.execute(add_column_query)
        
        # Update existing jobs that are already posted
        # Set review_posted_at to created_at for existing posted jobs
        update_query = text("""
            UPDATE jobs 
            SET review_posted_at = created_at 
            WHERE job_review_status = 'posted' AND review_posted_at IS NULL
        """)
        result = conn.execute(update_query)
        updated_count = result.rowcount
        
        conn.commit()
        
        print(f"✓ Column 'review_posted_at' added successfully")
        print(f"✓ Updated {updated_count} existing posted jobs with review_posted_at = created_at")
        print("\nMigration completed successfully!")
        print("\nNote: Jobs will now automatically track when they are posted.")
        print("Use the /admin/dashboard/jobs/cleanup endpoint to delete jobs 7 days after posting.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR during migration: {str(e)}")
        sys.exit(1)
