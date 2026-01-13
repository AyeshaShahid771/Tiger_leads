"""
Migration: Add draft_jobs table and update temp_documents table

This migration:
1. Creates draft_jobs table for saving job drafts
2. Adds linked_to_draft column to temp_documents table
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Create database engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def add_draft_jobs_table():
    """Add draft_jobs table and update temp_documents"""
    
    session = SessionLocal()
    try:
        print("Starting migration: Add draft_jobs table...")
        
        # Check if draft_jobs table already exists
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'draft_jobs'
            );
        """))
        table_exists = result.scalar()
        
        if table_exists:
            print("✓ draft_jobs table already exists")
        else:
            # Create draft_jobs table
            session.execute(text("""
                CREATE TABLE draft_jobs (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    permit_number VARCHAR(255),
                    permit_type_norm VARCHAR(100),
                    project_description TEXT,
                    job_address TEXT,
                    project_cost_total INTEGER,
                    permit_status VARCHAR(100),
                    contractor_email VARCHAR(255),
                    contractor_phone VARCHAR(20),
                    source_county VARCHAR(100),
                    state VARCHAR(100),
                    contractor_name VARCHAR(255),
                    contractor_company VARCHAR(255),
                    user_types JSON,
                    temp_upload_id VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP
                );
            """))
            
            # Create indexes
            session.execute(text("""
                CREATE INDEX idx_draft_jobs_user_id ON draft_jobs(user_id);
            """))
            session.execute(text("""
                CREATE INDEX idx_draft_jobs_temp_upload_id ON draft_jobs(temp_upload_id);
            """))
            
            print("✓ Created draft_jobs table")
        
        # Check if linked_to_draft column exists in temp_documents
        result = session.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = 'temp_documents' 
                AND column_name = 'linked_to_draft'
            );
        """))
        column_exists = result.scalar()
        
        if column_exists:
            print("✓ linked_to_draft column already exists in temp_documents")
        else:
            # Add linked_to_draft column to temp_documents
            session.execute(text("""
                ALTER TABLE temp_documents 
                ADD COLUMN linked_to_draft BOOLEAN NOT NULL DEFAULT FALSE;
            """))
            print("✓ Added linked_to_draft column to temp_documents")
        
        session.commit()
        print("✅ Migration completed successfully!")
        
        return True
        
    except Exception as e:
        session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        return False
    finally:
        session.close()


if __name__ == "__main__":
    success = add_draft_jobs_table()
    sys.exit(0 if success else 1)
