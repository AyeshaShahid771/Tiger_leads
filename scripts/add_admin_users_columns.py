"""Script to add missing admin_users columns required for admin auth.

Adds: verification_code (VARCHAR(10)), code_expires_at (TIMESTAMP NULL), password_hash (VARCHAR(255) NULL).

Usage:
    python scripts/add_admin_users_columns.py

This script uses the project's `src.app.core.database` session maker to run raw SQL ALTER TABLE
only when the columns are missing. It will not drop or modify existing columns.
"""

import os
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

# Ensure project root is on sys.path so `src` imports work when running this script
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.core.database import get_db


def _column_exists(db, table_name: str, column_name: str) -> bool:
    q = text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = :table AND column_name = :column LIMIT 1"
    )
    r = db.execute(q, {"table": table_name, "column": column_name}).first()
    return bool(r)


def main():
    db = next(get_db())
    table = "admin_users"
    try:
        cols_to_add = []
        if not _column_exists(db, table, "verification_code"):
            # Use a larger varchar to allow URL-safe tokens for password reset links
            cols_to_add.append(("verification_code", "VARCHAR(255)"))
        if not _column_exists(db, table, "code_expires_at"):
            cols_to_add.append(("code_expires_at", "TIMESTAMP NULL"))
        if not _column_exists(db, table, "password_hash"):
            cols_to_add.append(("password_hash", "VARCHAR(255) NULL"))
        # Columns to support separate password reset tokens (do not reuse verification_code)
        if not _column_exists(db, table, "reset_token"):
            cols_to_add.append(("reset_token", "VARCHAR(255) NULL"))
        if not _column_exists(db, table, "reset_token_expires_at"):
            cols_to_add.append(("reset_token_expires_at", "TIMESTAMP NULL"))

        if not cols_to_add:
            print("No changes required — all admin columns present.")
            return

        print("Adding columns to admin_users:")
        for col_name, col_type in cols_to_add:
            print(f" - {col_name} {col_type}")
            try:
                db.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                )
            except SQLAlchemyError as e:
                print(f"Failed to add column {col_name}: {e}")
                db.rollback()
                raise

        db.commit()
        print("Completed: added missing admin_users columns.")
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
