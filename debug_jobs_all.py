"""
Debug script to check why ayeshashahia117117@gmail.com is getting 0 jobs
"""
import sys
sys.path.insert(0, 'f:/Tiger_lead_backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import json

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("=" * 100)
print("DEBUGGING /jobs/all ENDPOINT - 0 RESULTS ISSUE")
print("=" * 100)

# 1. Get user info
user_query = text("""
    SELECT id, email, role
    FROM users
    WHERE email = 'ayeshashahia117117@gmail.com'
""")
user = session.execute(user_query).fetchone()

if not user:
    print("\n❌ User not found!")
    session.close()
    engine.dispose()
    sys.exit(1)

print(f"\n✅ User found: {user.email} (ID: {user.id}, Role: {user.role})")

# 2. Get contractor profile
contractor_query = text("""
    SELECT user_id, state, country_city, user_type
    FROM contractors
    WHERE user_id = :user_id
""")
contractor = session.execute(contractor_query, {"user_id": user.id}).fetchone()

if not contractor:
    print("\n❌ Contractor profile not found!")
    session.close()
    engine.dispose()
    sys.exit(1)

print(f"\n{'=' * 100}")
print("CONTRACTOR PROFILE")
print("=" * 100)
print(f"State: {contractor.state}")
print(f"Country/City: {contractor.country_city}")
print(f"User Type: {contractor.user_type}")

# 3. Count total posted jobs
total_jobs_query = text("""
    SELECT COUNT(*) as total
    FROM jobs
    WHERE job_review_status = 'posted'
""")
total_jobs = session.execute(total_jobs_query).fetchone()
print(f"\n{'=' * 100}")
print(f"TOTAL POSTED JOBS IN DATABASE: {total_jobs.total}")
print("=" * 100)

# 4. Check jobs matching state
if contractor.state:
    for state in contractor.state:
        state_jobs_query = text("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND state ILIKE :state
        """)
        state_count = session.execute(state_jobs_query, {"state": f"%{state}%"}).fetchone()
        print(f"Jobs in state '{state}': {state_count.count}")

# 5. Check jobs matching city
if contractor.country_city:
    for city in contractor.country_city:
        city_jobs_query = text("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND source_county ILIKE :city
        """)
        city_count = session.execute(city_jobs_query, {"city": f"%{city}%"}).fetchone()
        print(f"Jobs in city '{city}': {city_count.count}")

# 6. Check jobs matching user_type
if contractor.user_type:
    for ut in contractor.user_type:
        ut_jobs_query = text("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND audience_type_slugs ILIKE :user_type
        """)
        ut_count = session.execute(ut_jobs_query, {"user_type": f"%{ut}%"}).fetchone()
        print(f"Jobs for user_type '{ut}': {ut_count.count}")

# 7. Check excluded jobs
excluded_query = text("""
    SELECT 
        (SELECT COUNT(*) FROM unlocked_leads WHERE user_id = :user_id) as unlocked,
        (SELECT COUNT(*) FROM saved_jobs WHERE user_id = :user_id) as saved,
        (SELECT COUNT(*) FROM not_interested_jobs WHERE user_id = :user_id) as not_interested
""")
excluded = session.execute(excluded_query, {"user_id": user.id}).fetchone()

print(f"\n{'=' * 100}")
print("EXCLUDED JOBS")
print("=" * 100)
print(f"Unlocked: {excluded.unlocked}")
print(f"Saved: {excluded.saved}")
print(f"Not Interested: {excluded.not_interested}")
print(f"Total Excluded: {excluded.unlocked + excluded.saved + excluded.not_interested}")

# 8. Try to find matching jobs with full logic
print(f"\n{'=' * 100}")
print("TESTING FULL MATCHING LOGIC")
print("=" * 100)

# Build the query dynamically
if contractor.state and contractor.country_city and contractor.user_type:
    # Build state conditions
    state_conditions = " OR ".join([f"state ILIKE '%{s}%'" for s in contractor.state])
    city_conditions = " OR ".join([f"source_county ILIKE '%{c}%'" for c in contractor.country_city])
    ut_conditions = " OR ".join([f"audience_type_slugs ILIKE '%{ut}%'" for ut in contractor.user_type])
    
    full_query = text(f"""
        SELECT COUNT(*) as count
        FROM jobs
        WHERE job_review_status = 'posted'
        AND ({state_conditions})
        AND ({city_conditions})
        AND ({ut_conditions})
    """)
    
    full_count = session.execute(full_query).fetchone()
    print(f"Jobs matching ALL filters (state AND city AND user_type): {full_count.count}")
    
    # Show sample jobs
    if full_count.count > 0:
        sample_query = text(f"""
            SELECT id, state, source_county, audience_type_slugs, project_description
            FROM jobs
            WHERE job_review_status = 'posted'
            AND ({state_conditions})
            AND ({city_conditions})
            AND ({ut_conditions})
            LIMIT 5
        """)
        
        samples = session.execute(sample_query).fetchall()
        print(f"\nSample matching jobs:")
        for job in samples:
            print(f"  - Job {job.id}: {job.state}, {job.source_county}, {job.audience_type_slugs[:50]}...")

session.close()
engine.dispose()
