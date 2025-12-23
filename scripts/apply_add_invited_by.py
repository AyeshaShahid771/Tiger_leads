#!/usr/bin/env python3
"""Apply migration: add invited_by_id to users table.

Usage:
  python scripts/apply_add_invited_by.py

This script uses the project's SQLAlchemy `engine` (from `src.app.core.database`) and
runs idempotent SQL statements suitable for PostgreSQL. It will:
 - add column `invited_by_id` if missing
 - create an index on `invited_by_id` if missing
 - attempt to add a FK constraint (will warn and continue if it fails)

Run this from the project root inside your virtualenv so environment variables are loaded.
"""
import sys
import traceback
from sqlalchemy import text
import os

# Ensure project root is on sys.path so `src` package imports resolve when running this script
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from src.app.core.database import engine
except Exception as e:
    print("Failed to import database engine from src.app.core.database:", e)
    print(f"Tried adding project root to sys.path: {PROJECT_ROOT}")
    sys.exit(1)


SQL_STATEMENTS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_by_id INTEGER;",
    "CREATE INDEX IF NOT EXISTS ix_users_invited_by_id ON users (invited_by_id);",
]

# Optional FK constraint (Postgres). This may error if constraint exists or DB differs.
FK_SQL = (
    "ALTER TABLE users "
    "ADD CONSTRAINT fk_users_invited_by FOREIGN KEY (invited_by_id) "
    "REFERENCES users(id) ON DELETE SET NULL;"
)


def main():
    print("Applying migration: add invited_by_id to users...")
    conn = engine.connect()
    try:
        # Try to set a short statement timeout for Postgres to avoid long hangs
        try:
            conn.execute(text("SET statement_timeout = 10000;"))
            print("Set statement_timeout = 10000ms")
        except Exception:
            # Not fatal; some DBs don't support this setting
            print("Could not set statement timeout (DB may not support it); continuing.")

        any_success = False
        for sql in SQL_STATEMENTS:
            print("Executing:", sql)
            try:
                conn.execute(text(sql))
                print(" -> OK")
                any_success = True
            except Exception as stmt_err:
                print(f" -> Statement failed: {stmt_err}")

        # Attempt FK constraint separately
        try:
            print("Attempting to add FK constraint (optional)...")
            conn.execute(text(FK_SQL))
            print(" -> FK constraint added")
            any_success = True
        except Exception as fk_err:
            print("Warning: could not add FK constraint (continuing). Error:", fk_err)

        if any_success:
            print("Migration finished (some statements executed).")
        else:
            print("No statements executed successfully. Check DB connection and permissions.")

    except Exception:
        print("Migration failed. See traceback below:")
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
