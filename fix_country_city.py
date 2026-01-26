"""
Fix country_city array for user ayeshashahid771771@gmail.com
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
print(f"FIXING COUNTRY_CITY FOR {email}")
print("=" * 100)

# Get user
user_query = text("SELECT id FROM users WHERE email = :email")
user = session.execute(user_query, {"email": email}).fetchone()

if not user:
    print("User not found!")
    session.close()
    engine.dispose()
    sys.exit(1)

# Get current profile
profile_query = text("SELECT country_city FROM contractors WHERE user_id = :uid")
profile = session.execute(profile_query, {"uid": user.id}).fetchone()

print(f"\nCurrent country_city: {profile.country_city}")

# Fix: Split the comma-separated string into separate array elements
new_country_city = ['Hillsborough County', 'Mecklenburg County']

print(f"New country_city: {new_country_city}")

# Update
update_query = text("""
    UPDATE contractors
    SET country_city = :new_cities
    WHERE user_id = :uid
""")

session.execute(update_query, {"new_cities": new_country_city, "uid": user.id})
session.commit()

print("\n✅ Updated!")

# Verify
verify_query = text("SELECT country_city FROM contractors WHERE user_id = :uid")
verify = session.execute(verify_query, {"uid": user.id}).fetchone()
print(f"Verified country_city: {verify.country_city}")

# Now test matching
print(f"\n{'=' * 100}")
print("TESTING MATCHING AFTER FIX")
print("=" * 100)

test_query = text("""
    SELECT COUNT(*) FROM jobs
    WHERE job_review_status = 'posted'
    AND (state ILIKE '%Florida%' OR state ILIKE '%NC%')
    AND (source_county ILIKE '%Hillsborough County%' OR source_county ILIKE '%Mecklenburg County%')
""")

count = session.execute(test_query).fetchone()[0]
print(f"Jobs matching state + city: {count}")

session.close()
engine.dispose()
