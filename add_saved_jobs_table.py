"""
Migration script to create saved_jobs table.
Run this script to add the saved jobs feature to the database.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.app.core.database import engine

def create_saved_jobs_table():
    """Create saved_jobs table for tracking user saved jobs."""
    
    print("Starting migration: Creating saved_jobs table...")
    
    with engine.connect() as conn:
        try:
            # Start transaction
            trans = conn.begin()
            
            # Create saved_jobs table
            print("Creating saved_jobs table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS saved_jobs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, job_id)
                )
            """))
            
            # Create indexes for better performance
            print("Creating indexes...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_saved_jobs_user_id 
                ON saved_jobs(user_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_saved_jobs_job_id 
                ON saved_jobs(job_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_saved_jobs_saved_at 
                ON saved_jobs(saved_at DESC)
            """))
            
            # Commit transaction
            trans.commit()
            
            print("✅ Migration completed successfully!")
            print("   - Created saved_jobs table")
            print("   - Added user_id, job_id indexes")
            print("   - Added saved_at index")
            print("   - Added unique constraint on (user_id, job_id)")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {str(e)}")
            raise

if __name__ == "__main__":
    print("=" * 70)
    print("Saved Jobs Table Migration")
    print("=" * 70)
    
    try:
        create_saved_jobs_table()
        print("\n" + "=" * 70)
        print("Migration completed! Users can now save jobs.")
        print("=" * 70)
    except Exception as e:
        print("\n" + "=" * 70)
        print("Migration failed. Please check the error above.")
        print("=" * 70)
        sys.exit(1)
