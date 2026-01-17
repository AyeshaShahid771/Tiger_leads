"""
Script to list all jobs in the database
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from src.app.core.database import SessionLocal
from src.app.models.user import Job

def list_all_jobs():
    """List all jobs in the database"""
    db: Session = SessionLocal()
    
    try:
        # Fetch all jobs
        jobs = db.query(Job).all()
        
        if not jobs:
            print("❌ No jobs found in the database")
            return
        
        print(f"\n{'='*80}")
        print(f"TOTAL JOBS: {len(jobs)}")
        print(f"{'='*80}\n")
        
        for job in jobs:
            print(f"ID: {job.id:4d} | Status: {job.status:10s} | Type: {job.job_type:20s} | Title: {job.title[:50] if job.title else 'N/A'}")
        
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Error listing jobs: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    list_all_jobs()
