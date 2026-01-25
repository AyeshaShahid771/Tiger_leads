"""
Script to fetch all columns of the job with the highest ID
"""
import sys
sys.path.insert(0, 'f:/Tiger_lead_backend')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

print("=" * 100)
print("HIGHEST ID JOB - ALL COLUMNS")
print("=" * 100)

# Get the highest ID job
query = text("""
    SELECT *
    FROM jobs
    ORDER BY id DESC
    LIMIT 1
""")

try:
    result = session.execute(query)
    row = result.fetchone()
    
    if not row:
        print("\nNo jobs found in the database.")
    else:
        # Get column names
        columns = result.keys()
        
        print(f"\nJob ID: {row.id}")
        print("-" * 100)
        
        # Print all columns and their values
        for col in columns:
            value = getattr(row, col)
            
            # Format the value for display
            if value is None:
                display_value = "NULL"
            elif isinstance(value, (list, dict)):
                display_value = json.dumps(value, indent=2)
            else:
                display_value = str(value)
            
            # Truncate very long values
            if len(display_value) > 200:
                display_value = display_value[:200] + "... (truncated)"
            
            print(f"{col:30} : {display_value}")
        
        print("-" * 100)
        print(f"\nTotal columns: {len(columns)}")
    
except Exception as e:
    print(f"\nERROR: {str(e)}")
    import traceback
    traceback.print_exc()
finally:
    session.close()
    engine.dispose()

print("\nScript completed.")
