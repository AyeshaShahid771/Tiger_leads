"""
Check if user has unlocked job 642
"""
import sys
sys.path.insert(0, 'f:/Tiger_lead_backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("Checking unlocked leads for job 642...")
print("=" * 80)

# Check if job 642 exists and is posted
job_query = text("""
    SELECT id, state, source_county, audience_type_slugs, job_review_status
    FROM jobs
    WHERE id = 642
""")

job = session.execute(job_query).fetchone()
if job:
    print(f"\n✅ Job 642 exists:")
    print(f"   State: {job.state}")
    print(f"   County: {job.source_county}")
    print(f"   User Type: {job.audience_type_slugs}")
    print(f"   Status: {job.job_review_status}")
else:
    print("\n❌ Job 642 not found")
    session.close()
    engine.dispose()
    sys.exit(1)

# Check unlocked leads
unlocked_query = text("""
    SELECT user_id, job_id, unlocked_at
    FROM unlocked_leads
    WHERE job_id = 642
""")

unlocked = session.execute(unlocked_query).fetchall()

print(f"\n{'=' * 80}")
print("UNLOCKED LEADS CHECK")
print("=" * 80)

if unlocked:
    print(f"\n✅ Job 642 has been unlocked by {len(unlocked)} user(s):")
    for lead in unlocked:
        print(f"   User ID: {lead.user_id}, Unlocked at: {lead.unlocked_at}")
else:
    print("\n❌ Job 642 has NOT been unlocked by any user")
    print("\n⚠️  This is why it doesn't show in /jobs/my-job-feed")
    print("   The endpoint only shows jobs that the user has already unlocked (paid for)")

session.close()
engine.dispose()
