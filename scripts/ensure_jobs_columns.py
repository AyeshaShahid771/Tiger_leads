#!/usr/bin/env python3
"""Ensure `jobs` table has `country_city`, `uploaded_by_user_id` and FK constraint.

Run: python scripts/ensure_jobs_columns.py
Uses `src.app.core.database.engine` and respects `DATABASE_URL`.
"""
import os
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError


# the project root (parent of this `scripts/` folder) is first on sys.path so
# imports like `from src.app.core.database import engine` work.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.app.core.database import engine


def fk_exists(conn) -> bool:
    q = text(
        "SELECT constraint_name FROM information_schema.table_constraints "
        "WHERE table_name = 'jobs' AND constraint_type = 'FOREIGN KEY' "
        "AND constraint_name = 'fk_jobs_uploaded_by_user_id' LIMIT 1"
    )
    r = conn.execute(q).fetchone()
    return bool(r)


def main():
    try:
        with engine.begin() as conn:
            print("Ensuring column: country_city")
            conn.execute(
                text(
                    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS country_city VARCHAR(100);"
                )
            )

            print("Ensuring column: uploaded_by_user_id")
            conn.execute(
                text(
                    "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS uploaded_by_user_id INTEGER;"
                )
            )

            if fk_exists(conn):
                print("Foreign key fk_jobs_uploaded_by_user_id already exists")
            else:
                print("Creating foreign key fk_jobs_uploaded_by_user_id")
                conn.execute(
                    text(
                        "ALTER TABLE jobs ADD CONSTRAINT fk_jobs_uploaded_by_user_id "
                        "FOREIGN KEY (uploaded_by_user_id) REFERENCES users(id) ON DELETE SET NULL;"
                    )
                )

        print("Done")
    except SQLAlchemyError as e:
        print("Database error:", str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
    main()
