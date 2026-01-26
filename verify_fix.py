"""
Final verification after fix
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

user = session.execute(text("SELECT id FROM users WHERE email = :email"), {"email": email}).fetchone()
profile = session.execute(text("SELECT state, country_city, user_type FROM contractors WHERE user_id = :uid"), {"uid": user.id}).fetchone()

print("=" * 100)
print("FINAL VERIFICATION")
print("=" * 100)
print(f"\nProfile after fix:")
print(f"  State: {profile.state}")
print(f"  Country/City: {profile.country_city}")
print(f"  User Type: {profile.user_type}")

# Test full matching
state_cond = " OR ".join([f"state ILIKE '%{s}%'" for s in profile.state])
city_cond = " OR ".join([f"source_county ILIKE '%{c}%'" for c in profile.country_city])

# Note: user_type has comma-separated values in array elements, need to split
user_types = []
for ut in profile.user_type:
    user_types.extend([u.strip() for u in ut.split(',') if u.strip()])
ut_cond = " OR ".join([f"audience_type_slugs ILIKE '%{ut}%'" for ut in user_types])

full_query = text(f"""
    SELECT COUNT(*) FROM jobs
    WHERE job_review_status = 'posted'
    AND ({state_cond})
    AND ({city_cond})
    AND ({ut_cond})
""")

count = session.execute(full_query).fetchone()[0]
print(f"\n✅ Jobs matching ALL filters: {count}")

if count > 0:
    # Get excluded
    exc_ids = [str(r.job_id) for r in session.execute(text("""
        SELECT job_id FROM unlocked_leads WHERE user_id = :uid
        UNION SELECT job_id FROM saved_jobs WHERE user_id = :uid
        UNION SELECT job_id FROM not_interested_jobs WHERE user_id = :uid
    """), {"uid": user.id}).fetchall()]
    
    exc_clause = f"AND id NOT IN ({','.join(exc_ids)})" if exc_ids else ""
    
    final_query = text(f"""
        SELECT COUNT(*) FROM jobs
        WHERE job_review_status = 'posted'
        AND ({state_cond})
        AND ({city_cond})
        AND ({ut_cond})
        {exc_clause}
    """)
    
    final_count = session.execute(final_query).fetchone()[0]
    print(f"✅ After excluding user's jobs: {final_count}")
    print(f"\n🎉 /jobs/all should now return {final_count} jobs!")
else:
    print("\n❌ Still 0 jobs - there may be another issue")

session.close()
engine.dispose()
