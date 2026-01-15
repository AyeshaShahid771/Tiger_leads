#!/usr/bin/env python3
"""
Add contractor-upload tracking columns to the `jobs` table:
 - uploaded_by_contractor BOOLEAN DEFAULT FALSE
 - uploaded_by_user_id INTEGER NULL
 - job_review_status VARCHAR(20) DEFAULT 'posted'

Run from the repository root (Windows `cmd.exe`):

    cd f:\\Tiger_lead_backend
    Tiger_leads\\Scripts\\activate.bat
    pip install -r requirements.txt
    python scripts\\add_contractor_uploaded_jobs_columns.py

Make a DB backup before running on production.
"""
import os
import sys

from sqlalchemy import text

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.core.database import engine


def column_exists(conn, column_name: str) -> bool:
    q = text(
        "SELECT 1 FROM information_schema.columns WHERE table_name='jobs' AND column_name = :col"
    )
    return conn.execute(q, {"col": column_name}).first() is not None


def main():
    print("Connecting to database using src.app.core.database.engine...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            if not column_exists(conn, "uploaded_by_contractor"):
                print("Adding column: uploaded_by_contractor BOOLEAN DEFAULT FALSE")
                conn.execute(
                    text(
                        "ALTER TABLE jobs ADD COLUMN uploaded_by_contractor BOOLEAN DEFAULT FALSE;"
                    )
                )
            else:
                print("Column already exists: uploaded_by_contractor")

            if not column_exists(conn, "uploaded_by_user_id"):
                print("Adding column: uploaded_by_user_id INTEGER NULL")
                conn.execute(
                    text(
                        "ALTER TABLE jobs ADD COLUMN uploaded_by_user_id INTEGER NULL;"
                    )
                )
            else:
                print("Column already exists: uploaded_by_user_id")

            if not column_exists(conn, "job_review_status"):
                print("Adding column: job_review_status VARCHAR(20) DEFAULT 'posted'")
                conn.execute(
                    text(
                        "ALTER TABLE jobs ADD COLUMN job_review_status VARCHAR(20) DEFAULT 'posted';"
                    )
                )
            else:
                print("Column already exists: job_review_status")

            trans.commit()
            print("Migration completed successfully.")
        except Exception as exc:
            trans.rollback()
            print("Error during migration:", exc, file=sys.stderr)
            raise


if __name__ == "__main__":
    main()



