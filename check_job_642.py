"""
Script to fetch job details for a specific job ID
"""
import sys
sys.path.insert(0, 'f:/Tiger_lead_backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

# Get the highest ID job (should be 642)
query = text("""
    SELECT *
    FROM jobs
    ORDER BY id DESC
    LIMIT 1
""")

try:
    result = session.execute(query)
    row = result.fetchone()
    
    if not row:
        print("No jobs found")
    else:
        print("=" * 100)
        print(f"JOB ID: {row.id}")
        print("=" * 100)
        
        # Key fields for debugging
        print(f"\n{'Field':<30} | Value")
        print("-" * 100)
        print(f"{'id':<30} | {row.id}")
        print(f"{'state':<30} | {row.state}")
        print(f"{'country_city':<30} | {row.country_city}")
        print(f"{'source_county':<30} | {row.source_county}")
        print(f"{'audience_type_slugs':<30} | {row.audience_type_slugs}")
        print(f"{'job_review_status':<30} | {row.job_review_status}")
        print(f"{'review_posted_at':<30} | {row.review_posted_at}")
        print(f"{'permit_type_norm':<30} | {row.permit_type_norm}")
        print(f"{'project_description':<30} | {row.project_description[:50] if row.project_description else None}...")
        print(f"{'contractor_name':<30} | {row.contractor_name}")
        print(f"{'contractor_email':<30} | {row.contractor_email}")
        print(f"{'anchor_at':<30} | {row.anchor_at}")
        print(f"{'due_at':<30} | {row.due_at}")
        print(f"{'day_offset':<30} | {row.day_offset}")
        print(f"{'created_at':<30} | {row.created_at}")
        
        print("\n" + "=" * 100)
        print("ANALYSIS")
        print("=" * 100)
        
        # Check why it might not show
        issues = []
        
        if row.job_review_status != 'posted':
            issues.append(f"❌ Status is '{row.job_review_status}' (should be 'posted')")
        else:
            issues.append(f"✅ Status is 'posted'")
            
        if not row.state:
            issues.append("❌ State is NULL")
        else:
            issues.append(f"✅ State: {row.state}")
            
        if not row.audience_type_slugs:
            issues.append("❌ Audience type slugs is NULL")
        else:
            issues.append(f"✅ Audience type: {row.audience_type_slugs}")
        
        for issue in issues:
            print(issue)
        
except Exception as e:
    print(f"ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
    engine.dispose()
