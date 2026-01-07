"""
Migration script to update jobs table schema.
Drops old columns and adds new permit-based schema columns.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def migrate_jobs_schema():
    """Migrate jobs table to new permit-based schema"""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        print("Starting jobs table migration...")
        
        # Start transaction
        trans = conn.begin()
        
        try:
            # Drop old columns that don't exist in new schema
            old_columns = [
                'permit_record_number',
                'date',
                'permit_type',
                'job_cost',
                'email',
                'phone_number',
                'country_city',
                'work_type',
                'category'
            ]
            
            print("\n1. Dropping old columns...")
            for column in old_columns:
                # Check if column exists before dropping
                check_query = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'jobs' AND column_name = :column_name
                """)
                result = conn.execute(check_query, {"column_name": column})
                if result.fetchone():
                    drop_query = text(f"ALTER TABLE jobs DROP COLUMN IF EXISTS {column} CASCADE")
                    conn.execute(drop_query)
                    print(f"  ✓ Dropped column: {column}")
                else:
                    print(f"  - Column {column} doesn't exist, skipping")
            
            # Add new columns
            print("\n2. Adding new columns...")
            
            new_columns = [
                ("queue_id", "INTEGER"),
                ("rule_id", "INTEGER"),
                ("recipient_group", "VARCHAR(100)"),
                ("recipient_group_id", "INTEGER"),
                ("day_offset", "INTEGER DEFAULT 0"),
                ("anchor_event", "VARCHAR(50)"),
                ("anchor_at", "TIMESTAMP"),
                ("due_at", "TIMESTAMP"),
                ("permit_id", "INTEGER"),
                ("permit_number", "VARCHAR(255)"),
                ("permit_status", "VARCHAR(100)"),
                ("permit_type_norm", "VARCHAR(100)"),
                ("project_cost_total", "INTEGER"),
                ("project_cost_source", "VARCHAR(100)"),
                ("source_county", "VARCHAR(100)"),
                ("source_system", "VARCHAR(100)"),
                ("routing_anchor_at", "TIMESTAMP"),
                ("first_seen_at", "TIMESTAMP"),
                ("last_seen_at", "TIMESTAMP"),
                ("contractor_name", "VARCHAR(255)"),
                ("contractor_company", "VARCHAR(255)"),
                ("contractor_email", "VARCHAR(255)"),
                ("contractor_phone", "VARCHAR(20)"),
                ("audience_type_slugs", "TEXT"),
                ("audience_type_names", "TEXT"),
                ("querystring", "TEXT"),
                ("trs_score", "INTEGER"),
                ("uploaded_by_contractor", "BOOLEAN DEFAULT FALSE"),
                ("uploaded_by_user_id", "INTEGER REFERENCES users(id) ON DELETE SET NULL"),
                ("job_review_status", "VARCHAR(20) DEFAULT 'posted'"),
                ("review_posted_at", "TIMESTAMP")
            ]
            
            for column_name, column_type in new_columns:
                # Check if column already exists
                check_query = text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'jobs' AND column_name = :column_name
                """)
                result = conn.execute(check_query, {"column_name": column_name})
                if not result.fetchone():
                    add_query = text(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}")
                    conn.execute(add_query)
                    print(f"  ✓ Added column: {column_name} ({column_type})")
                else:
                    print(f"  - Column {column_name} already exists, skipping")
            
            # Add index on permit_number if not exists
            print("\n3. Adding indexes...")
            index_query = text("""
                CREATE INDEX IF NOT EXISTS idx_jobs_permit_number 
                ON jobs(permit_number)
            """)
            conn.execute(index_query)
            print("  ✓ Added index on permit_number")
            
            # Commit transaction
            trans.commit()
            print("\n✅ Jobs table migration completed successfully!")
            
            # Show summary
            print("\n" + "="*50)
            print("MIGRATION SUMMARY")
            print("="*50)
            summary_query = text("""
                SELECT COUNT(*) as total_jobs 
                FROM jobs
            """)
            result = conn.execute(summary_query)
            total = result.fetchone()[0]
            print(f"Total jobs in table: {total}")
            
            # Show column list
            columns_query = text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'jobs' 
                ORDER BY ordinal_position
            """)
            result = conn.execute(columns_query)
            print("\nCurrent table columns:")
            for row in result:
                print(f"  - {row[0]}: {row[1]}")
            
        except Exception as e:
            trans.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            raise


if __name__ == "__main__":
    migrate_jobs_schema()
