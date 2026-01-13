"""
Scheduler script to post approved jobs based on offset_days.

This script:
1. Finds jobs where uploaded_by_contractor = False (admin approved)
2. Checks if review_posted_at + offset_days <= current_time
3. Updates job_review_status from 'pending' to 'posted'
4. Should run every hour via cron/scheduler
"""

import os
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def post_jobs_by_offset():
    """
    Post jobs that have passed their offset_days delay.
    
    Updates jobs where:
    - uploaded_by_contractor = False (admin approved)
    - job_review_status = 'pending'
    - review_posted_at + offset_days <= current_time
    """
    db = SessionLocal()
    
    try:
        current_time = datetime.utcnow()
        
        # SQL query to find and update eligible jobs
        query = text("""
            UPDATE jobs 
            SET job_review_status = 'posted'
            WHERE uploaded_by_contractor = FALSE
            AND job_review_status = 'pending'
            AND review_posted_at IS NOT NULL
            AND review_posted_at + (COALESCE(day_offset, 0) || ' days')::interval <= :current_time
            RETURNING id, permit_number, audience_type_slugs, day_offset, review_posted_at
        """)
        
        result = db.execute(query, {"current_time": current_time})
        updated_jobs = result.fetchall()
        
        db.commit()
        
        if updated_jobs:
            print(f"✓ Posted {len(updated_jobs)} job(s) based on offset_days:")
            for job in updated_jobs:
                print(f"  - Job ID {job.id}: {job.permit_number} | User Type: {job.audience_type_slugs} | Offset: {job.day_offset} days | Approved: {job.review_posted_at}")
        else:
            print("ℹ No jobs ready to be posted at this time")
            
        return len(updated_jobs)
        
    except Exception as e:
        db.rollback()
        print(f"✗ Error posting jobs: {str(e)}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 70)
    print(f"Running Job Posting Scheduler - {datetime.utcnow().isoformat()}")
    print("=" * 70)
    
    count = post_jobs_by_offset()
    
    print("=" * 70)
    print(f"Scheduler completed. Jobs posted: {count}")
    print("=" * 70)
