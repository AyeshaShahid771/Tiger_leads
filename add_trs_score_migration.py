"""
Migration Script: Add trs_score column to jobs table
Run this scripto add the TRS score column to your database
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ Error: DATABASE_URL not found in environment variables")
    exit(1)

print(f"Connecting to database...")

try:
    # Create engine
    engine = create_engine(DATABASE_URL)

    # Connect and execute migration
    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            print("Adding trs_score column to jobs table...")

            # Add the column
            conn.execute(
                text(
                    """
                ALTER TABLE jobs 
                ADD COLUMN IF NOT EXISTS trs_score INTEGER;
            """
                )
            )

            # Add comment
            conn.execute(
                text(
                    """
                COMMENT ON COLUMN jobs.trs_score IS 
                'Total Relevance Score (0-100): Average of project value score, stage score, and contact score';
            """
                )
            )

            # Create index
            conn.execute(
                text(
                    """
                CREATE INDEX IF NOT EXISTS idx_jobs_trs_score ON jobs(trs_score);
            """
                )
            )

            # Commit transaction
            trans.commit()

            print("✅ Migration completed successfully!")
            print("✅ trs_score column added to jobs table")
            print("✅ Index created on trs_score column")

            # Verify the column
            result = conn.execute(
                text(
                    """
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' AND column_name = 'trs_score';
            """
                )
            )

            row = result.fetchone()
            if row:
                print(f"\n📋 Column Details:")
                print(f"   Name: {row[0]}")
                print(f"   Type: {row[1]}")
                print(f"   Nullable: {row[2]}")

        except Exception as e:
            trans.rollback()
            print(f"❌ Error during migration: {str(e)}")
            raise

except Exception as e:
    print(f"❌ Failed to connect to database: {str(e)}")
    exit(1)

print("\n✅ Database migration completed successfully!")
print("   You can now restart your application and upload leads with TRS scoring.")
print("   You can now restart your application and upload leads with TRS scoring.")
