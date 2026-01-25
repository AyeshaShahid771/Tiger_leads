"""
Script to get exact job data with state, country_city, and audience_type_slugs
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
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("Jobs Table - Exact Data")
print("=" * 120)

# Get actual job data
query = text("""
    SELECT 
        id,
        state,
        country_city,
        audience_type_slugs
    FROM jobs
    WHERE job_review_status = 'posted'
    ORDER BY id DESC
    LIMIT 30
""")

try:
    result = session.execute(query)
    rows = result.fetchall()
    
    print(f"\nTotal Posted Jobs: {len(rows)}\n")
    print(f"{'ID':<8} | {'State':<15} | {'Country/City':<30} | {'User Types (audience_type_slugs)'}")
    print("-" * 120)
    
    for row in rows:
        job_id = str(row.id)
        state = row.state or "NULL"
        country_city = row.country_city or "NULL"
        user_types = row.audience_type_slugs or "NULL"
        
        print(f"{job_id:<8} | {state:<15} | {country_city:<30} | {user_types}")
    
except Exception as e:
    print(f"ERROR: {str(e)}")
finally:
    session.close()
    engine.dispose()
