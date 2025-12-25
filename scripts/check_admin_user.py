"""
Check admin_users row for a given email.
Usage:
    python scripts/check_admin_user.py n.abdullah.self@gmail.com
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app import models
from src.app.core.database import SessionLocal


def check(email: str):
    db = SessionLocal()
    try:
        row = (
            db.query(models.user.AdminUser)
            .filter(models.user.AdminUser.email == email.lower())
            .first()
        )
        if not row:
            print(f"No admin_users row found for {email}")
            return
        print("Found admin_users row:")
        print(f"  id: {row.id}")
        print(f"  email: {row.email}")
        print(f"  is_active: {row.is_active}")
        print(f"  created_by: {row.created_by}")
        print(f"  created_at: {row.created_at}")
        print(f"  updated_at: {row.updated_at}")
    except Exception as e:
        print(f"Error querying admin_users: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("email")
    args = p.parse_args()
    check(args.email)
