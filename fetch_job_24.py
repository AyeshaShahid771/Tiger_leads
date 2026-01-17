"""
Script to fetch all data for job ID 24
"""
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from src.app.core.database import SessionLocal
from src.app.models.user import Job, UnlockedLead
import json

def fetch_job_data(job_id: int):
    """Fetch all data for a specific job ID"""
    db: Session = SessionLocal()
    
    try:
        # Fetch the job
        job = db.query(Job).filter(Job.id == job_id).first()
        
        if not job:
            print(f"❌ Job with ID {job_id} not found")
            return
        
        print(f"\n{'='*80}")
        print(f"JOB DATA FOR ID: {job_id}")
        print(f"{'='*80}\n")
        
        # Convert job to dictionary
        job_data = {
            "id": job.id,
            "user_id": job.user_id,
            "job_type": job.job_type,
            "property_type": job.property_type,
            "title": job.title,
            "description": job.description,
            "location": job.location,
            "latitude": job.latitude,
            "longitude": job.longitude,
            "budget": job.budget,
            "timeline": job.timeline,
            "status": job.status,
            "created_at": str(job.created_at) if job.created_at else None,
            "updated_at": str(job.updated_at) if job.updated_at else None,
            "posted_date": str(job.posted_date) if job.posted_date else None,
            "expiry_date": str(job.expiry_date) if job.expiry_date else None,
            "is_featured": job.is_featured,
            "views_count": job.views_count,
            "contact_name": job.contact_name,
            "contact_email": job.contact_email,
            "contact_phone": job.contact_phone,
            "additional_details": job.additional_details,
            "source": job.source,
            "offset_days": job.offset_days,
        }
        
        # Print formatted JSON
        print("📋 JOB DETAILS:")
        print(json.dumps(job_data, indent=2, default=str))
        
        # Fetch related documents
        if hasattr(job, 'documents') and job.documents:
            print(f"\n📎 DOCUMENTS ({len(job.documents)}):")
            for i, doc in enumerate(job.documents, 1):
                print(f"\n  Document {i}:")
                print(f"    - ID: {doc.id}")
                print(f"    - Filename: {doc.filename}")
                print(f"    - File Path: {doc.file_path}")
                print(f"    - File Type: {doc.file_type}")
                print(f"    - Uploaded At: {doc.uploaded_at}")
        else:
            print("\n📎 DOCUMENTS: None")
        
        # Fetch unlocked leads for this job
        unlocked_count = db.query(UnlockedLead).filter(
            UnlockedLead.job_id == job_id
        ).count()
        
        print(f"\n🔓 UNLOCKED LEADS: {unlocked_count}")
        
        if unlocked_count > 0:
            unlocked_leads = db.query(UnlockedLead).filter(
                UnlockedLead.job_id == job_id
            ).all()
            
            for i, lead in enumerate(unlocked_leads, 1):
                print(f"\n  Lead {i}:")
                print(f"    - User ID: {lead.user_id}")
                print(f"    - Unlocked At: {lead.unlocked_at}")
        
        print(f"\n{'='*80}\n")
        
    except Exception as e:
        print(f"❌ Error fetching job data: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    fetch_job_data(24)
