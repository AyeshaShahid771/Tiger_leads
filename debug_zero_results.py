"""
Debug script for ayeshashahid771771@gmail.com
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

email = 'ayeshashahid771771@gmail.com'

print("=" * 100)
print(f"DEBUGGING /jobs/all FOR {email}")
print("=" * 100)

# 1. Get user
user_query = text("SELECT id, email, role FROM users WHERE email = :email")
user = session.execute(user_query, {"email": email}).fetchone()

if not user:
    print(f"\n❌ User not found!")
    session.close()
    engine.dispose()
    sys.exit(1)

print(f"\n✅ User: {user.email} (ID: {user.id}, Role: {user.role})")

# 2. Get contractor profile
contractor_query = text("SELECT user_id, state, country_city, user_type FROM contractors WHERE user_id = :user_id")
contractor = session.execute(contractor_query, {"user_id": user.id}).fetchone()

if not contractor:
    print("\n❌ Contractor profile not found!")
    session.close()
    engine.dispose()
    sys.exit(1)

print(f"\n{'=' * 100}")
print("PROFILE DATA")
print("=" * 100)
print(f"State: {contractor.state}")
print(f"Country/City: {contractor.country_city}")
print(f"User Type: {contractor.user_type}")

# 3. Total posted jobs
total_query = text("SELECT COUNT(*) as total FROM jobs WHERE job_review_status = 'posted'")
total = session.execute(total_query).fetchone()
print(f"\n{'=' * 100}")
print(f"TOTAL POSTED JOBS: {total.total}")
print("=" * 100)

# 4. Individual filter counts
print(f"\nJOBS BY INDIVIDUAL FILTERS:")
if contractor.state:
    for state in contractor.state:
        count = session.execute(text("SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted' AND state ILIKE :s"), {"s": f"%{state}%"}).fetchone()[0]
        print(f"  State '{state}': {count} jobs")

if contractor.country_city:
    for city in contractor.country_city:
        count = session.execute(text("SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted' AND source_county ILIKE :c"), {"c": f"%{city}%"}).fetchone()[0]
        print(f"  City '{city}': {count} jobs")

if contractor.user_type:
    for ut in contractor.user_type:
        count = session.execute(text("SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted' AND audience_type_slugs ILIKE :u"), {"u": f"%{ut}%"}).fetchone()[0]
        print(f"  User Type '{ut}': {count} jobs")

# 5. Excluded jobs
excluded_query = text("""
    SELECT 
        (SELECT COUNT(*) FROM unlocked_leads WHERE user_id = :uid) as unlocked,
        (SELECT COUNT(*) FROM saved_jobs WHERE user_id = :uid) as saved,
        (SELECT COUNT(*) FROM not_interested_jobs WHERE user_id = :uid) as not_interested
""")
excluded = session.execute(excluded_query, {"uid": user.id}).fetchone()

print(f"\n{'=' * 100}")
print("EXCLUDED JOBS")
print("=" * 100)
print(f"Unlocked: {excluded.unlocked}")
print(f"Saved: {excluded.saved}")
print(f"Not Interested: {excluded.not_interested}")
print(f"Total: {excluded.unlocked + excluded.saved + excluded.not_interested}")

# 6. Full matching logic
print(f"\n{'=' * 100}")
print("FULL MATCHING TEST")
print("=" * 100)

if contractor.state and contractor.country_city and contractor.user_type:
    state_cond = " OR ".join([f"state ILIKE '%{s}%'" for s in contractor.state])
    city_cond = " OR ".join([f"source_county ILIKE '%{c}%'" for c in contractor.country_city])
    ut_cond = " OR ".join([f"audience_type_slugs ILIKE '%{ut}%'" for ut in contractor.user_type])
    
    full_query = text(f"""
        SELECT COUNT(*) FROM jobs
        WHERE job_review_status = 'posted'
        AND ({state_cond})
        AND ({city_cond})
        AND ({ut_cond})
    """)
    
    full_count = session.execute(full_query).fetchone()[0]
    print(f"Jobs matching ALL filters: {full_count}")
    
    if full_count > 0:
        # Get excluded IDs
        exc_ids_query = text("""
            SELECT job_id FROM unlocked_leads WHERE user_id = :uid
            UNION SELECT job_id FROM saved_jobs WHERE user_id = :uid
            UNION SELECT job_id FROM not_interested_jobs WHERE user_id = :uid
        """)
        exc_ids = [str(r.job_id) for r in session.execute(exc_ids_query, {"uid": user.id}).fetchall()]
        
        if exc_ids:
            exc_clause = f"AND id NOT IN ({','.join(exc_ids)})"
        else:
            exc_clause = ""
        
        final_query = text(f"""
            SELECT COUNT(*) FROM jobs
            WHERE job_review_status = 'posted'
            AND ({state_cond})
            AND ({city_cond})
            AND ({ut_cond})
            {exc_clause}
        """)
        
        final_count = session.execute(final_query).fetchone()[0]
        print(f"After excluding user's jobs: {final_count}")
        
        if final_count == 0:
            print(f"\n❌ PROBLEM: All {full_count} matching jobs are excluded!")
        else:
            print(f"\n✅ Should show {final_count} jobs")
            # Sample
            sample_q = text(f"""
                SELECT id, state, source_county, audience_type_slugs
                FROM jobs
                WHERE job_review_status = 'posted'
                AND ({state_cond})
                AND ({city_cond})
                AND ({ut_cond})
                {exc_clause}
                LIMIT 3
            """)
            samples = session.execute(sample_q).fetchall()
            print("\nSample jobs:")
            for j in samples:
                print(f"  Job {j.id}: {j.state}, {j.source_county}, {j.audience_type_slugs[:40]}...")
    else:
        print("\n❌ NO jobs match all filters!")
        print("\nTrying partial matches:")
        
        # State + City
        sc_query = text(f"SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted' AND ({state_cond}) AND ({city_cond})")
        sc_count = session.execute(sc_query).fetchone()[0]
        print(f"  State + City: {sc_count} jobs")
        
        # State + UserType
        su_query = text(f"SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted' AND ({state_cond}) AND ({ut_cond})")
        su_count = session.execute(su_query).fetchone()[0]
        print(f"  State + UserType: {su_count} jobs")
        
        # City + UserType
        cu_query = text(f"SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted' AND ({city_cond}) AND ({ut_cond})")
        cu_count = session.execute(cu_query).fetchone()[0]
        print(f"  City + UserType: {cu_count} jobs")

session.close()
engine.dispose()
