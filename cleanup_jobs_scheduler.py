"""
Scheduled Job Cleanup Script

This script automatically deletes jobs that have been posted for 7 days or more.
Run this script as a cron job or scheduled task (e.g., daily at midnight).

Example cron (runs daily at midnight):
0 0 * * * cd /path/to/Tiger_lead_backend && /path/to/python cleanup_jobs_scheduler.py

Or use Windows Task Scheduler to run this script daily.
"""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import models
from src.app.core.database import Base

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

# Create engine and session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def cleanup_old_jobs():
    """Delete jobs that were posted 7 days ago or more.
    
    NOTE: This functionality is currently DISABLED.
    The review_posted_at column is still tracked for future use.
    """
    session = SessionLocal()
    try:
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        print(f"[{datetime.utcnow().isoformat()}] Job cleanup is DISABLED")
        print("The review_posted_at column is still being tracked for future use.")
        
        # DISABLED: Job deletion logic commented out
        # Find jobs to delete
        # jobs_to_delete = session.query(models.user.Job).filter(
        #     models.user.Job.job_review_status == "posted",
        #     models.user.Job.review_posted_at.isnot(None),
        #     models.user.Job.review_posted_at <= cutoff_date
        # ).all()
        # 
        # if not jobs_to_delete:
        #     print("No jobs found that are 7 days old or older.")
        #     return 0
        # 
        # count = len(jobs_to_delete)
        # deleted_ids = []
        # 
        # # Delete jobs
        # for job in jobs_to_delete:
        #     deleted_ids.append(job.id)
        #     session.delete(job)
        # 
        # session.commit()
        # 
        # print(f"✓ Successfully deleted {count} jobs")
        # print(f"Deleted job IDs: {deleted_ids[:20]}{'...' if len(deleted_ids) > 20 else ''}")
        
        return 0
        
    except Exception as e:
        session.rollback()
        print(f"ERROR during cleanup: {str(e)}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    try:
        deleted_count = cleanup_old_jobs()
        print(f"\n[{datetime.utcnow().isoformat()}] Cleanup completed: {deleted_count} jobs deleted")
        sys.exit(0)
    except Exception as e:
        print(f"\n[{datetime.utcnow().isoformat()}] Cleanup failed: {str(e)}")
        sys.exit(1)
