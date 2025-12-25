"""Remove unwanted columns previously added to support a generic dashboard.

Drops the following columns if present (using CASCADE):
- users.name
- users.state
- jobs.title
- jobs.description
- jobs.status
- subscriptions.plan_name

This script is idempotent. Run from repo root:
    python scripts/remove_unwanted_dashboard_columns.py

It uses the project's DB connection (src.app.core.database.get_db).
"""
import os
import sys
from sqlalchemy import text

# Make repo root importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app.core.database import get_db

COLUMNS_TO_DROP = [
    ('users', 'name'),
    ('users', 'state'),
    ('jobs', 'title'),
    ('jobs', 'description'),
    ('jobs', 'status'),
    ('subscriptions', 'plan_name'),
    ('subscriptions', 'status'),
    ('subscriptions', 'start_date'),
    ('subscriptions', 'end_date'),
]


def run():
    db = next(get_db())
    try:
        for table, column in COLUMNS_TO_DROP:
            try:
                print(f"Dropping {table}.{column} if it exists (CASCADE)")
                db.execute(text(f"ALTER TABLE {table} DROP COLUMN IF EXISTS {column} CASCADE"))
            except Exception as e:
                print(f"Failed to drop {table}.{column}: {e}")

        db.commit()
        print('Completed removal of unwanted columns (if present).')
    except Exception as e:
        print('Error during removal, rolling back:', e)
        db.rollback()
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == '__main__':
    run()
