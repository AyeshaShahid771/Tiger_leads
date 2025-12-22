"""
Migration script to add contractor-upload tracking columns to `jobs` table.
Run once against your database to add these fields:
 - uploaded_by_contractor BOOLEAN DEFAULT FALSE
 - uploaded_by_user_id INTEGER (FK -> users.id)
 - job_review_status VARCHAR(20) DEFAULT 'posted'

Usage:
    python add_job_uploaded_columns.py
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment")
    raise SystemExit(1)

engine = create_engine(DATABASE_URL)

sql_commands = [
    """
    ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS uploaded_by_contractor BOOLEAN DEFAULT FALSE NOT NULL;
    """,
    """
    ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS uploaded_by_user_id INTEGER NULL;
    """,
    """
    ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS job_review_status VARCHAR(20) DEFAULT 'posted';
    """,
    # Optionally add a foreign key constraint if supported and desired.
]

try:
    with engine.connect() as conn:
        for sql in sql_commands:
            print(f"Executing: {sql.strip()}")
            conn.execute(text(sql))
            conn.commit()
        print("\n✓ Migration completed: job upload columns added (if they did not exist)\n")
except Exception as e:
    print(f"Migration error: {e}")
finally:
    engine.dispose()
