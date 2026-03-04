"""
Migration script: Fix pending_jurisdictions rows where US state names
were incorrectly stored with jurisdiction_type = 'country_city'.

Corrects them to jurisdiction_type = 'state' so:
  - admin panel shows the correct "State" label
  - approval endpoint routes the value to the right contractor/supplier field
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.app.utils.geo import US_STATE_NAMES

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is not set")


def fix_jurisdiction_types(dry_run: bool = False):
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        # Fetch all rows with jurisdiction_type = 'country_city'
        rows = session.execute(
            text(
                "SELECT id, user_id, user_type, jurisdiction_value "
                "FROM pending_jurisdictions "
                "WHERE jurisdiction_type = 'country_city' "
                "ORDER BY id"
            )
        ).fetchall()

        to_fix = [r for r in rows if r.jurisdiction_value in US_STATE_NAMES]

        print(f"Found {len(rows)} rows with jurisdiction_type='country_city'")
        print(f"Found {len(to_fix)} rows where jurisdiction_value is a US state")

        if not to_fix:
            print("Nothing to fix.")
            return

        print("\nRows to be fixed:")
        for r in to_fix:
            print(
                f"  id={r.id}  user_id={r.user_id}  user_type={r.user_type}  "
                f"value={r.jurisdiction_value!r}"
            )

        if dry_run:
            print("\nDry run — no changes made.")
            return

        ids = [r.id for r in to_fix]
        session.execute(
            text(
                "UPDATE pending_jurisdictions "
                "SET jurisdiction_type = 'state' "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": ids},
        )
        session.commit()
        print(f"\nUpdated {len(ids)} rows → jurisdiction_type = 'state'")

    except Exception as exc:
        session.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    fix_jurisdiction_types(dry_run=dry_run)

    try:
        # Fetch all rows with jurisdiction_type = 'country_city'
        rows = session.execute(
            text(
                "SELECT id, user_id, user_type, jurisdiction_value "
                "FROM pending_jurisdictions "
                "WHERE jurisdiction_type = 'country_city' "
                "ORDER BY id"
            )
        ).fetchall()

        to_fix = [r for r in rows if r.jurisdiction_value in US_STATE_NAMES]

        print(f"Found {len(rows)} rows with jurisdiction_type='country_city'")
        print(f"Found {len(to_fix)} rows where jurisdiction_value is a US state")

        if not to_fix:
            print("Nothing to fix.")
            return

        print("\nRows to be fixed:")
        for r in to_fix:
            print(
                f"  id={r.id}  user_id={r.user_id}  user_type={r.user_type}  "
                f"value={r.jurisdiction_value!r}"
            )

        if dry_run:
            print("\nDry run — no changes made.")
            return

        ids = [r.id for r in to_fix]
        session.execute(
            text(
                "UPDATE pending_jurisdictions "
                "SET jurisdiction_type = 'state' "
                "WHERE id = ANY(:ids)"
            ),
            {"ids": ids},
        )
        session.commit()
        print(f"\nUpdated {len(ids)} rows → jurisdiction_type = 'state'")

    except Exception as exc:
        session.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    fix_jurisdiction_types(dry_run=dry_run)
