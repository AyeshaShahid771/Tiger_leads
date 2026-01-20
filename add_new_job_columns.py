"""
Migration: Add new columns to jobs table for enhanced project data.

New columns:
- project_number (VARCHAR 255) - Project/permit number
- project_type (VARCHAR 100) - Type of project
- project_sub_type (VARCHAR 100) - Sub-type of project
- project_status (VARCHAR 100) - Current project status
- project_cost (INTEGER) - Project cost
- project_address (VARCHAR 255) - Project address
- owner_name (VARCHAR 255) - Property owner name
- applicant_name (VARCHAR 255) - Applicant name
- applicant_email (VARCHAR 255) - Applicant email
- applicant_phone (VARCHAR 20) - Applicant phone
- contractor_company_and_address (TEXT) - Contractor company and address
- permit_raw (TEXT) - Raw permit type description
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def add_new_job_columns():
    """Add new columns to jobs table."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            print("Starting migration: Adding new columns to jobs table...")
            print("=" * 60)
            
            # Add project_number
            print("\n1. Adding project_number column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS project_number VARCHAR(255);
            """))
            
            # Add project_type
            print("2. Adding project_type column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS project_type VARCHAR(100);
            """))
            
            # Add project_sub_type
            print("3. Adding project_sub_type column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS project_sub_type VARCHAR(100);
            """))
            
            # Add project_status
            print("4. Adding project_status column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS project_status VARCHAR(100);
            """))
            
            # Add project_cost
            print("5. Adding project_cost column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS project_cost INTEGER;
            """))
            
            # Add project_address
            print("6. Adding project_address column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS project_address VARCHAR(255);
            """))
            
            # Add owner_name
            print("7. Adding owner_name column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS owner_name VARCHAR(255);
            """))
            
            # Add applicant_name
            print("8. Adding applicant_name column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS applicant_name VARCHAR(255);
            """))
            
            # Add applicant_email
            print("9. Adding applicant_email column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS applicant_email VARCHAR(255);
            """))
            
            # Add applicant_phone
            print("10. Adding applicant_phone column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS applicant_phone VARCHAR(20);
            """))
            
            # Add contractor_company_and_address
            print("11. Adding contractor_company_and_address column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS contractor_company_and_address TEXT;
            """))
            
            # Add permit_raw
            print("12. Adding permit_raw column...")
            conn.execute(text("""
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS permit_raw TEXT;
            """))
            
            conn.commit()
            
            print("\n" + "=" * 60)
            print("✅ Migration completed successfully!")
            print("\nNew columns added:")
            print("  1. project_number (VARCHAR 255)")
            print("  2. project_type (VARCHAR 100)")
            print("  3. project_sub_type (VARCHAR 100)")
            print("  4. project_status (VARCHAR 100)")
            print("  5. project_cost (INTEGER)")
            print("  6. project_address (VARCHAR 255)")
            print("  7. owner_name (VARCHAR 255)")
            print("  8. applicant_name (VARCHAR 255)")
            print("  9. applicant_email (VARCHAR 255)")
            print(" 10. applicant_phone (VARCHAR 20)")
            print(" 11. contractor_company_and_address (TEXT)")
            print(" 12. permit_raw (TEXT)")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Error during migration: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    add_new_job_columns()
