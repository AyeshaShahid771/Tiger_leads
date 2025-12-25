#!/usr/bin/env python3
"""
Restore a user's role in the `users` table.
Usage: python scripts/restore_user_role.py user@example.com [Role]
"""
import sys

from src.app import models
from src.app.core.database import SessionLocal

if len(sys.argv) < 2:
    print("Usage: python scripts/restore_user_role.py user@example.com [Role]")
    sys.exit(1)

email = sys.argv[1]
new_role = sys.argv[2] if len(sys.argv) > 2 else "Contractor"

db = SessionLocal()
try:
    user = db.query(models.user.User).filter(models.user.User.email == email).first()
    if not user:
        print(f"User not found: {email}")
        sys.exit(2)

    old_role = getattr(user, "role", None)
    print(f"Found user {email} with role={old_role}")
    user.role = new_role
    db.add(user)
    db.commit()
    print(f"Updated role for {email}: {old_role} -> {new_role}")
finally:
    db.close()
