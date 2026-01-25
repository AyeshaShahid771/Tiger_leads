"""
Script to check jobs table for state, country_city, and audience_type_slugs values
"""
import sys
sys.path.insert(0, 'f:/Tiger_lead_backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    sys.exit(1)

# Create engine and session
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("=" * 80)
print("JOBS TABLE - State, Country/City, and User Type Analysis")
print("=" * 80)

# Query to get sample jobs with these fields
query = text("""
    SELECT 
        id,
        state,
        country_city,
        source_county,
        audience_type_slugs,
        permit_type_norm,
        job_review_status
    FROM jobs
    WHERE job_review_status = 'posted'
    ORDER BY id DESC
    LIMIT 20
""")

try:
    result = session.execute(query)
    rows = result.fetchall()
    
    if not rows:
        print("\nNo posted jobs found in the database.")
    else:
        print(f"\nFound {len(rows)} posted jobs. Showing details:\n")
        
        for i, row in enumerate(rows, 1):
            print(f"Job #{i} (ID: {row.id})")
            print(f"  State: {row.state}")
            print(f"  Country/City: {row.country_city}")
            print(f"  Source County: {row.source_county}")
            print(f"  Audience Type Slugs: {row.audience_type_slugs}")
            print(f"  Permit Type: {row.permit_type_norm}")
            print(f"  Status: {row.job_review_status}")
            print("-" * 80)
    
    # Get unique values summary
    print("\n" + "=" * 80)
    print("UNIQUE VALUES SUMMARY")
    print("=" * 80)
    
    # Unique states
    state_query = text("""
        SELECT DISTINCT state 
        FROM jobs 
        WHERE job_review_status = 'posted' AND state IS NOT NULL
        ORDER BY state
        LIMIT 50
    """)
    states = session.execute(state_query).fetchall()
    print(f"\nUnique States ({len(states)}):")
    for state in states:
        print(f"  - {state[0]}")
    
    # Unique counties
    county_query = text("""
        SELECT DISTINCT source_county 
        FROM jobs 
        WHERE job_review_status = 'posted' AND source_county IS NOT NULL
        ORDER BY source_county
        LIMIT 50
    """)
    counties = session.execute(county_query).fetchall()
    print(f"\nUnique Counties ({len(counties)}):")
    for county in counties:
        print(f"  - {county[0]}")
    
    # Unique audience types
    audience_query = text("""
        SELECT DISTINCT audience_type_slugs 
        FROM jobs 
        WHERE job_review_status = 'posted' AND audience_type_slugs IS NOT NULL
        ORDER BY audience_type_slugs
        LIMIT 50
    """)
    audiences = session.execute(audience_query).fetchall()
    print(f"\nUnique Audience Type Slugs ({len(audiences)}):")
    for audience in audiences:
        print(f"  - {audience[0]}")
    
    # Total count
    count_query = text("""
        SELECT COUNT(*) FROM jobs WHERE job_review_status = 'posted'
    """)
    total = session.execute(count_query).scalar()
    print(f"\n{'=' * 80}")
    print(f"TOTAL POSTED JOBS: {total}")
    print(f"{'=' * 80}")
    
except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
    engine.dispose()

print("\nScript completed.")
