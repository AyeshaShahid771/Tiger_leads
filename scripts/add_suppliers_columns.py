#!/usr/bin/env python3
"""
Add `product_categories` and `product_types` columns to the `suppliers` table
and optionally backfill them from existing `product_categories` JSON data.

This script uses the application's configured SQLAlchemy `engine` found in
`src.app.core.database`. It will:
 - add `product_categories VARCHAR(255)` if missing
 - add `product_types TEXT[]` if missing
 - attempt to parse existing `product_categories` if it contains a JSON array
   and backfill into `product_types` where applicable

Run from the repository root (Windows `cmd.exe`):

    cd f:\\Tiger_lead_backend
    Tiger_leads\Scripts\activate.bat
    pip install -r requirements.txt
    python scripts\add_suppliers_columns.py

Make a DB backup before running on production.
"""
import json
import os
import sys

from sqlalchemy import text

# ensure project root on path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.core.database import engine


def column_exists(conn, column_name: str) -> bool:
    q = text(
        "SELECT 1 FROM information_schema.columns WHERE table_name='suppliers' AND column_name = :col"
    )
    return conn.execute(q, {"col": column_name}).first() is not None


def main():
    print("Connecting to database using src.app.core.database.engine...")

    with engine.connect() as conn:
        trans = conn.begin()
        try:
            if not column_exists(conn, "product_categories"):
                print("Adding column: product_categories VARCHAR(255)")
                conn.execute(
                    text(
                        "ALTER TABLE suppliers ADD COLUMN product_categories VARCHAR(255);"
                    )
                )
            else:
                print("Column already exists: product_categories")

            if not column_exists(conn, "product_types"):
                print("Adding column: product_types TEXT[]")
                conn.execute(
                    text("ALTER TABLE suppliers ADD COLUMN product_types TEXT[];")
                )
            else:
                print("Column already exists: product_types")

            # Try to backfill product_types from old product_categories JSON arrays
            print(
                "Attempting to backfill product_types from existing product_categories JSON (if any)..."
            )
            rows = conn.execute(
                text(
                    "SELECT id, product_categories FROM suppliers WHERE product_categories IS NOT NULL AND product_categories <> ''"
                )
            ).fetchall()

            updated = 0
            skipped = 0
            for row in rows:
                sid = row[0]
                p = row[1]
                try:
                    parsed = json.loads(p)
                    if not isinstance(parsed, list) or len(parsed) == 0:
                        skipped += 1
                        continue
                    escaped = ",".join(
                        "'{}'".format(str(x).replace("'", "''")) for x in parsed
                    )
                    sql = f"UPDATE suppliers SET product_types = ARRAY[{escaped}]::text[] WHERE id = {sid} AND (product_types IS NULL OR cardinality(product_types)=0);"
                    conn.execute(text(sql))
                    updated += 1
                except Exception:
                    skipped += 1

            print(f"product_types backfill: updated={updated}, skipped={skipped}")

            trans.commit()
            print("Supplier migration completed successfully.")

        except Exception as exc:
            trans.rollback()
            print("Error during supplier migration:", exc, file=sys.stderr)
            raise


if __name__ == "__main__":
    main()
    main()
