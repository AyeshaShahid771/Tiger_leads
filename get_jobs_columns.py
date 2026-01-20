"""
Script to fetch all column names from the jobs table.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_jobs_table_columns():
    """Fetch all column names from the jobs table."""
    
    engine = create_engine(DATABASE_URL)
    inspector = inspect(engine)
    
    print("=" * 60)
    print("JOBS TABLE COLUMNS")
    print("=" * 60)
    
    # Get columns
    columns = inspector.get_columns('jobs')
    
    print(f"\nTotal columns: {len(columns)}\n")
    
    for i, col in enumerate(columns, 1):
        col_name = col['name']
        col_type = str(col['type'])
        nullable = "NULL" if col['nullable'] else "NOT NULL"
        default = f" DEFAULT {col['default']}" if col.get('default') else ""
        
        print(f"{i:2}. {col_name:30} {col_type:20} {nullable:10}{default}")
    
    print("\n" + "=" * 60)
    print("Column names only (for copy-paste):")
    print("=" * 60)
    column_names = [col['name'] for col in columns]
    print(", ".join(column_names))
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    get_jobs_table_columns()
