"""
Database migration script to create the contractors table.

Run this script to create the contractors table in your database.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

# Create engine
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def create_contractors_table():
    """Create the contractors table if it doesn't exist"""

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS contractors (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        
        -- Step 1: Basic Business Information
        company_name VARCHAR(255),
        phone_number VARCHAR(20),
        email_address VARCHAR(255),
        business_address TEXT,
        business_type VARCHAR(100),
        years_in_business INTEGER,
        
        -- Step 2: License Information
        state_license_number VARCHAR(100),
        county_license VARCHAR(100),
        occupational_license VARCHAR(100),
        license_picture_url VARCHAR(500),
        license_expiration_date DATE,
        license_status VARCHAR(20),
        
        -- Step 3: Trade Information
        work_type VARCHAR(50),
        business_types TEXT,
        
        -- Step 4: Service Jurisdictions
        service_state VARCHAR(100),
        service_zip_code VARCHAR(20),
        
        -- Tracking fields
        registration_step INTEGER DEFAULT 0,
        is_completed BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP
    );
    
    -- Create index on user_id for faster lookups
    CREATE INDEX IF NOT EXISTS idx_contractors_user_id ON contractors(user_id);
    """

    try:
        with engine.connect() as connection:
            connection.execute(text(create_table_sql))
            connection.commit()
            print("✅ Contractors table created successfully!")
            return True
    except Exception as e:
        print(f"❌ Error creating contractors table: {str(e)}")
        return False


if __name__ == "__main__":
    print("Creating contractors table...")
    create_contractors_table()
