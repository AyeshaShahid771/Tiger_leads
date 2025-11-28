#!/usr/bin/env python3
r"""
Add `trade_categories` and `trade_specialities` columns to the `contractors` table
and optionally backfill them from existing `work_type` and `business_types` data.

This script uses the application's configured SQLAlchemy `engine` found in
`src.app.core.database`. It will:
 - add `trade_categories VARCHAR(255)` if missing
 - add `trade_specialities TEXT[]` if missing
 - backfill `trade_categories` with `work_type` where present
 - attempt to parse `business_types` as JSON array strings and convert them
   into `trade_specialities` (Postgres TEXT[]). Rows with invalid JSON are
   skipped and reported.

Run from the repository root (Windows `cmd.exe`):

    cd f:\\Tiger_lead_backend
    venv\Scripts\activate
    pip install -r requirements.txt
    python scripts\add_contractors_columns.py

Make a DB backup before running on production.
"""
import json
import os
import sys

from sqlalchemy import text

# Ensure project root is on sys.path so `src` package is importable when running
# this script directly (without setting PYTHONPATH).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.core.database import engine


def column_exists(conn, column_name: str) -> bool:
    q = text(
        "SELECT 1 FROM information_schema.columns WHERE table_name='contractors' AND column_name = :col"
    )
    return conn.execute(q, {"col": column_name}).first() is not None


def main():
    print("Connecting to database using src.app.core.database.engine...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            # Add columns if missing
            if not column_exists(conn, "trade_categories"):
                print("Adding column: trade_categories VARCHAR(255)")
                conn.execute(
                    text(
                        "ALTER TABLE contractors ADD COLUMN trade_categories VARCHAR(255);"
                    )
                )
            else:
                print("Column already exists: trade_categories")

            if not column_exists(conn, "trade_specialities"):
                print("Adding column: trade_specialities TEXT[]")
                conn.execute(
                    text(
                        "ALTER TABLE contractors ADD COLUMN trade_specialities TEXT[];"
                    )
                )
            else:
                print("Column already exists: trade_specialities")

            # Backfill trade_categories from work_type
            print("Backfilling trade_categories from work_type where applicable...")
            conn.execute(
                text(
                    "UPDATE contractors SET trade_categories = work_type WHERE trade_categories IS NULL AND work_type IS NOT NULL;"
                )
            )

            # Backfill trade_specialities from business_types (if business_types contains JSON array)
            print(
                "Attempting to backfill trade_specialities from business_types (JSON arrays)..."
            )
            rows = conn.execute(
                text(
                    "SELECT id, business_types FROM contractors WHERE business_types IS NOT NULL AND business_types <> ''"
                )
            ).fetchall()

            updated = 0
            skipped = 0
            for row in rows:
                cid = row[0]
                b = row[1]
                try:
                    parsed = json.loads(b)
                    if not isinstance(parsed, list) or len(parsed) == 0:
                        skipped += 1
                        continue

                    # Build a safe Postgres ARRAY[...] literal using escaped strings
                    escaped = ",".join(
                        "'{}'".format(str(x).replace("'", "''")) for x in parsed
                    )
                    sql = f"UPDATE contractors SET trade_specialities = ARRAY[{escaped}]::text[] WHERE id = {cid} AND (trade_specialities IS NULL OR cardinality(trade_specialities)=0);"
                    conn.execute(text(sql))
                    updated += 1
                except Exception:
                    skipped += 1

            print(f"trade_specialities backfill: updated={updated}, skipped={skipped}")

            trans.commit()
            print("Migration completed successfully.")

        except Exception as exc:
            trans.rollback()
            print("Error during migration:", exc, file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
    main()
