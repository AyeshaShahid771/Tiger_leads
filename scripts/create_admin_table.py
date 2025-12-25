"""
Script to create `admin_users` table and seed allowed admin emails.
Run with the virtualenv Python that has project deps.
Usage: python scripts/create_admin_table.py
"""

import os
import sys

# Ensure project root is on sys.path so `import src...` works when running this script directly
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from sqlalchemy.exc import IntegrityError

from src.app.core.database import SessionLocal, engine
from src.app.models import user as user_models

ALLOWED = [
    "admin@tigerleads.ai",
    "ayeshashahid771771@gmail.com",
    "wasay.ahmad123@gmail.com",
]


def main():
    # Create table if missing
    print("Creating admin_users table if not exists...")
    try:
        user_models.AdminUser.__table__.create(bind=engine, checkfirst=True)
        print("Table created or already exists.")
    except Exception as e:
        print("Failed to create table:", e)
        return

    session = SessionLocal()
    try:
        for email in ALLOWED:
            email_l = email.lower()
            exists = (
                session.query(user_models.AdminUser)
                .filter(user_models.AdminUser.email == email_l)
                .first()
            )
            if exists:
                print(f"Admin {email_l} already present, skipping.")
                continue
            admin = user_models.AdminUser(email=email_l, is_active=True)
            session.add(admin)
            try:
                session.commit()
                print(f"Inserted admin: {email_l}")
            except IntegrityError:
                session.rollback()
                print(f"Integrity error inserting {email_l}, skipping.")
    finally:
        session.close()


if __name__ == "__main__":
    main()
