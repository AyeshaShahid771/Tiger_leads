"""
Migration to add property_type column to jobs table.
Allows contractors to specify if a job is Residential or Commercial.
"""

from sqlalchemy import create_engine, text, inspect
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

engine = create_engine(DATABASE_URL)


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in the table"""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_property_type_column():
    """Add property_type column to jobs table"""
    
    with engine.connect() as conn:
        # Check if column already exists
        if check_column_exists(engine, "jobs", "property_type"):
            print("✓ Column 'property_type' already exists in 'jobs' table")
            return
        
        print("Adding 'property_type' column to 'jobs' table...")
        
        # Add property_type column (VARCHAR, nullable, with Residential/Commercial options)
        conn.execute(text("""
            ALTER TABLE jobs 
            ADD COLUMN property_type VARCHAR(20) NULL
        """))
        
        conn.commit()
        print("✓ Successfully added 'property_type' column to 'jobs' table")
        print("  Allowed values: 'Residential', 'Commercial', or NULL")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MIGRATION: Add property_type column to jobs table")
    print("="*60 + "\n")
    
    try:
        add_property_type_column()
        print("\n" + "="*60)
        print("✓ Migration completed successfully!")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}\n")
        raise
