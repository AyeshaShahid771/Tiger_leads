"""
Check actual saved jobs data in database to see source_county values
Run from backend directory: python check_saved_jobs_data.py
"""
from sqlalchemy import text
from src.app.core.database import get_db

def check_saved_jobs():
    """Check saved jobs data"""
    db = next(get_db())
    
    try:
        # Get sample of saved jobs with their location data
        query = text("""
            SELECT 
                j.id,
                j.permit_type_norm,
                j.source_county,
                j.state,
                j.project_description,
                sj.user_id
            FROM saved_jobs sj
            JOIN jobs j ON sj.job_id = j.id
            WHERE j.job_review_status = 'posted'
            ORDER BY sj.saved_at DESC
            LIMIT 20
        """)
        
        result = db.execute(query)
        rows = result.fetchall()
        
        print(f"\n=== SAVED JOBS DATA (Sample of 20) ===\n")
        print(f"Total rows: {len(rows)}\n")
        
        null_county_count = 0
        for row in rows:
            job_id, permit_type, source_county, state, description, user_id = row
            
            if source_county is None or (isinstance(source_county, str) and source_county.strip() == ""):
                null_county_count += 1
                print(f"❌ Job ID {job_id}: source_county=NULL, state={state}")
            else:
                print(f"✓ Job ID {job_id}: source_county={source_county}, state={state}")
            
            print(f"   Permit: {permit_type}")
            if description:
                print(f"   Description: {description[:50]}...")
            print()
        
        print(f"\n=== SUMMARY ===")
        print(f"Total saved jobs checked: {len(rows)}")
        print(f"Jobs with NULL/empty source_county: {null_county_count}")
        print(f"Jobs with valid source_county: {len(rows) - null_county_count}")
        
        # Check if there's a country_city column
        check_columns = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'jobs' 
            AND column_name IN ('source_county', 'country_city')
        """)
        
        result = db.execute(check_columns)
        columns = [row[0] for row in result.fetchall()]
        
        print(f"\n=== JOBS TABLE COLUMNS ===")
        print(f"Columns found: {columns}")
        
    finally:
        db.close()

if __name__ == "__main__":
    check_saved_jobs()
