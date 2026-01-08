"""
Debug script to check why user 67 is getting no matching jobs
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("=" * 80)
print("DEBUGGING DASHBOARD MATCHING FOR USER 67")
print("=" * 80)

# 1. Get user 67's contractor profile
print("\n1. USER 67 CONTRACTOR PROFILE:")
print("-" * 80)
contractor_query = text("""
    SELECT user_id, user_type, state, country_city, is_completed
    FROM contractors
    WHERE user_id = 67
""")
contractor = session.execute(contractor_query).fetchone()

if contractor:
    print(f"User ID: {contractor.user_id}")
    print(f"User Type: {contractor.user_type}")
    print(f"State: {contractor.state}")
    print(f"Country/City: {contractor.country_city}")
    print(f"Is Completed: {contractor.is_completed}")
else:
    print("❌ No contractor profile found for user 67")
    session.close()
    exit(1)

# 2. Count total posted jobs
print("\n2. TOTAL POSTED JOBS:")
print("-" * 80)
posted_jobs_query = text("""
    SELECT COUNT(*) as count
    FROM jobs
    WHERE job_review_status = 'posted'
""")
posted_count = session.execute(posted_jobs_query).fetchone()
print(f"Total posted jobs: {posted_count.count}")

# 3. Get sample posted jobs with their audience_type_slugs
print("\n3. SAMPLE POSTED JOBS (first 5):")
print("-" * 80)
sample_jobs_query = text("""
    SELECT id, permit_number, audience_type_slugs, state, source_county, 
           job_review_status, review_posted_at
    FROM jobs
    WHERE job_review_status = 'posted'
    ORDER BY review_posted_at ASC
    LIMIT 5
""")
sample_jobs = session.execute(sample_jobs_query).fetchall()

for job in sample_jobs:
    print(f"Job ID: {job.id}")
    print(f"  Permit: {job.permit_number}")
    print(f"  Audience Slugs: {job.audience_type_slugs}")
    print(f"  State: {job.state}")
    print(f"  County: {job.source_county}")
    print(f"  Status: {job.job_review_status}")
    print(f"  Posted At: {job.review_posted_at}")
    print()

# 4. Test matching logic for user 67
print("\n4. TESTING MATCHING LOGIC:")
print("-" * 80)

user_types = contractor.user_type if contractor.user_type else []
states = contractor.state if contractor.state else []
cities = contractor.country_city if contractor.country_city else []

print(f"User types to match: {user_types}")
print(f"States to match: {states}")
print(f"Cities to match: {cities}")
print()

# Build the query similar to dashboard endpoint
if user_types and len(user_types) > 0:
    # Build audience conditions
    audience_conditions = []
    for user_type in user_types:
        audience_conditions.append(f"audience_type_slugs ILIKE '%{user_type}%'")
    
    audience_sql = " OR ".join(audience_conditions)
    
    # Build state conditions if exists
    state_sql = ""
    if states and len(states) > 0:
        state_conditions = []
        for state in states:
            state_conditions.append(f"state ILIKE '%{state}%'")
        state_sql = f" AND ({' OR '.join(state_conditions)})"
    
    # Build city conditions if exists
    city_sql = ""
    if cities and len(cities) > 0:
        city_conditions = []
        for city in cities:
            city_conditions.append(f"source_county ILIKE '%{city}%'")
        city_sql = f" AND ({' OR '.join(city_conditions)})"
    
    # Full query
    full_query = text(f"""
        SELECT id, permit_number, audience_type_slugs, state, source_county, 
               job_review_status, review_posted_at
        FROM jobs
        WHERE job_review_status = 'posted'
        AND ({audience_sql})
        {state_sql}
        {city_sql}
        ORDER BY review_posted_at ASC
        LIMIT 20
    """)
    
    print(f"SQL Query:\n{full_query}")
    print()
    
    matching_jobs = session.execute(full_query).fetchall()
    
    print(f"MATCHING JOBS FOUND: {len(matching_jobs)}")
    print()
    
    if matching_jobs:
        for job in matching_jobs:
            print(f"✓ Job ID: {job.id} - {job.permit_number}")
            print(f"  Slugs: {job.audience_type_slugs}")
            print(f"  State: {job.state}, County: {job.source_county}")
            print()
    else:
        print("❌ NO MATCHING JOBS FOUND!")
        print("\nLet's check each condition separately:")
        
        # Check audience match only
        audience_only_query = text(f"""
            SELECT COUNT(*) as count
            FROM jobs
            WHERE job_review_status = 'posted'
            AND ({audience_sql})
        """)
        audience_count = session.execute(audience_only_query).fetchone()
        print(f"  - Jobs matching audience_type_slugs: {audience_count.count}")
        
        # Check state match only
        if state_sql:
            state_only_query = text(f"""
                SELECT COUNT(*) as count
                FROM jobs
                WHERE job_review_status = 'posted'
                {state_sql}
            """)
            state_count = session.execute(state_only_query).fetchone()
            print(f"  - Jobs matching state: {state_count.count}")
        
        # Check city match only
        if city_sql:
            city_only_query = text(f"""
                SELECT COUNT(*) as count
                FROM jobs
                WHERE job_review_status = 'posted'
                {city_sql}
            """)
            city_count = session.execute(city_only_query).fetchone()
            print(f"  - Jobs matching source_county: {city_count.count}")

else:
    print("❌ User has NO user_type values - cannot match any jobs!")

session.close()

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)
