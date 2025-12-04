"""
Migration script to add not_interested_jobs table.

This table tracks jobs that users have marked as "not interested" 
so they never see them again.
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    exit(1)

engine = create_engine(DATABASE_URL)

print("🔄 Creating not_interested_jobs table...")
print("=" * 70)

try:
    with engine.connect() as conn:
        trans = conn.begin()
        
        try:
            # Create table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS not_interested_jobs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    marked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, job_id)
                )
            """))
            
            # Create indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_not_interested_user_id 
                ON not_interested_jobs(user_id)
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_not_interested_job_id 
                ON not_interested_jobs(job_id)
            """))
            
            trans.commit()
            
            print("✅ Table 'not_interested_jobs' created successfully!")
            print("\nTable structure:")
            print("  - id: Primary key")
            print("  - user_id: References users table")
            print("  - job_id: References jobs table")
            print("  - marked_at: Timestamp when marked")
            print("  - UNIQUE(user_id, job_id): Prevents duplicates")
            print("\n✅ Indexes created:")
            print("  - idx_not_interested_user_id")
            print("  - idx_not_interested_job_id")
            print("=" * 70)
            
        except Exception as e:
            trans.rollback()
            print(f"❌ Migration failed: {str(e)}")
            print("   Transaction rolled back.")
            raise
            
except Exception as e:
    print(f"❌ Database connection error: {str(e)}")
    exit(1)
