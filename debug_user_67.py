"""
Debug script to check why user ID 67 is getting 0 jobs
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

print("=" * 100)
print("DEBUGGING /jobs/all ENDPOINT - USER ID 67")
print("=" * 100)

user_id = 67

# 1. Get user info
user_query = text("""
    SELECT id, email, role
    FROM users
    WHERE id = :user_id
""")
user = session.execute(user_query, {"user_id": user_id}).fetchone()

if not user:
    print(f"\n❌ User ID {user_id} not found!")
    session.close()
    engine.dispose()
    sys.exit(1)

print(f"\n✅ User: {user.email} (ID: {user.id}, Role: {user.role})")

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
print(f"TOTAL POSTED JOBS: {total_jobs.total}")
print("=" * 100)

# 4. Check jobs by individual filters
print(f"\n{'=' * 100}")
print("JOBS MATCHING INDIVIDUAL FILTERS")
print("=" * 100)

if contractor.state:
    for state in contractor.state:
        state_jobs_query = text("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND state ILIKE :state
        """)
        state_count = session.execute(state_jobs_query, {"state": f"%{state}%"}).fetchone()
        print(f"✓ State '{state}': {state_count.count} jobs")

if contractor.country_city:
    for city in contractor.country_city:
        city_jobs_query = text("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND source_county ILIKE :city
        """)
        city_count = session.execute(city_jobs_query, {"city": f"%{city}%"}).fetchone()
        print(f"✓ City '{city}': {city_count.count} jobs")

if contractor.user_type:
    for ut in contractor.user_type:
        ut_jobs_query = text("""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND audience_type_slugs ILIKE :user_type
        """)
        ut_count = session.execute(ut_jobs_query, {"user_type": f"%{ut}%"}).fetchone()
        print(f"✓ User Type '{ut}': {ut_count.count} jobs")

# 5. Check excluded jobs
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

# 6. Test full matching logic (state AND city AND user_type)
print(f"\n{'=' * 100}")
print("TESTING FULL MATCHING LOGIC (ALL FILTERS)")
print("=" * 100)

if contractor.state and contractor.country_city and contractor.user_type:
    # Build conditions
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
    print(f"\n✅ Jobs matching ALL filters: {full_count.count}")
    
    # Now exclude user's jobs
    if full_count.count > 0:
        excluded_ids_query = text("""
            SELECT job_id FROM unlocked_leads WHERE user_id = :user_id
            UNION
            SELECT job_id FROM saved_jobs WHERE user_id = :user_id
            UNION
            SELECT job_id FROM not_interested_jobs WHERE user_id = :user_id
        """)
        excluded_ids = session.execute(excluded_ids_query, {"user_id": user.id}).fetchall()
        excluded_id_list = [str(row.job_id) for row in excluded_ids]
        
        if excluded_id_list:
            excluded_clause = f"AND id NOT IN ({','.join(excluded_id_list)})"
        else:
            excluded_clause = ""
        
        final_query = text(f"""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND ({state_conditions})
            AND ({city_conditions})
            AND ({ut_conditions})
            {excluded_clause}
        """)
        
        final_count = session.execute(final_query).fetchone()
        print(f"✅ Jobs after excluding user's jobs: {final_count.count}")
        
        if final_count.count == 0:
            print(f"\n❌ ISSUE FOUND: All matching jobs are excluded!")
            print(f"   - {full_count.count} jobs match filters")
            print(f"   - But all {full_count.count} are in unlocked/saved/not-interested")
        else:
            # Show sample
            sample_query = text(f"""
                SELECT id, state, source_county, audience_type_slugs, project_description
                FROM jobs
                WHERE job_review_status = 'posted'
                AND ({state_conditions})
                AND ({city_conditions})
                AND ({ut_conditions})
                {excluded_clause}
                LIMIT 5
            """)
            
            samples = session.execute(sample_query).fetchall()
            print(f"\n✅ Sample jobs that should appear:")
            for job in samples:
                print(f"   Job {job.id}: {job.state}, {job.source_county}")
else:
    print("\n❌ Profile is missing required fields!")

session.close()
engine.dispose()
