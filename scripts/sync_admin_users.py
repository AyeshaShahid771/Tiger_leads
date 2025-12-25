"""
Sync `admin_users` table to a desired canonical list of admin emails.
- Inserts any missing allowed emails.
- Optionally removes unexpected admin rows (set REMOVE_UNKNOWN=True to enable).

Usage:
    python scripts/sync_admin_users.py

Ensure you're running from the project root so imports work, or set PYTHONPATH=.
"""

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.app.core.database import SessionLocal
from src.app.models import user as user_models

# Canonical desired admin emails (lowercase)
DESIRED_ADMINS = {
    "admin@tigerleads.ai",
    "ayeshashahid771771@gmail.com",
    "wasay.ahmad123@gmail.com",
}

# Set to True to delete admin rows not in DESIRED_ADMINS (use with caution)
REMOVE_UNKNOWN = True


def main():
    session = SessionLocal()
    try:
        # Ensure table exists
        try:
            user_models.AdminUser.__table__.create(
                bind=user_models.AdminUser.__table__.metadata.bind, checkfirst=True
            )
        except Exception:
            pass

        # Load existing admin emails
        rows = session.query(user_models.AdminUser).all()
        existing = {r.email.lower(): r for r in rows}

        # Insert missing
        for email in DESIRED_ADMINS:
            if email not in existing:
                print(f"Inserting missing admin: {email}")
                admin = user_models.AdminUser(email=email, is_active=True)
                session.add(admin)
        session.commit()

        # Optionally remove unknown
        if REMOVE_UNKNOWN:
            to_remove = [r for em, r in existing.items() if em not in DESIRED_ADMINS]
            for r in to_remove:
                print(f"Removing unexpected admin row: {r.email}")
                session.delete(r)
            session.commit()

        # Final list
        final = session.query(user_models.AdminUser.email).all()
        print("Final admin emails in DB:")
        for e in final:
            print(" -", e[0])

    finally:
        session.close()


if __name__ == "__main__":
    main()
