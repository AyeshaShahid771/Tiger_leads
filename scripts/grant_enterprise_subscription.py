"""
Script: grant_enterprise_subscription.py
Grant the Enterprise subscription to the specified user email.
Usage:
    python scripts/grant_enterprise_subscription.py n.abdullah.self@gmail.com

This script:
- imports project modules by adding project root to sys.path
- finds or creates a User with the given email (marks verified if needed)
- finds the 'Enterprise' Subscription tier
- creates or updates a Subscriber record for the user with that tier and sets is_active=True
- sets seats_used to 1 (main account) and current_credits to tier.credits

Run from repository root.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

# Ensure project root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.app import models
from src.app.core.database import SessionLocal


def grant(email: str):
    db = SessionLocal()
    try:
        user = (
            db.query(models.user.User).filter(models.user.User.email == email).first()
        )
        if not user:
            print(
                f"User with email {email} not found. Creating a verified user without password."
            )
            user = models.user.User(
                email=email,
                password_hash="",
                email_verified=True,
                verification_code=None,
                code_expires_at=None,
                role="Admin",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            print(
                f"Found user id={user.id} email={user.email} verified={user.email_verified}"
            )
            # ensure verified
            if not user.email_verified:
                user.email_verified = True
                db.add(user)
                db.commit()

        # Find Enterprise subscription tier
        tier = (
            db.query(models.user.Subscription)
            .filter(models.user.Subscription.name.ilike("Enterprise"))
            .first()
        )
        if not tier:
            print("Enterprise tier not found in subscriptions table. Aborting.")
            return

        subscriber = (
            db.query(models.user.Subscriber)
            .filter(models.user.Subscriber.user_id == user.id)
            .first()
        )
        if not subscriber:
            subscriber = models.user.Subscriber(
                user_id=user.id,
                subscription_id=tier.id,
                current_credits=tier.credits or 0,
                seats_used=0,
                subscription_start_date=datetime.now(timezone.utc),
                subscription_renew_date=datetime.now(timezone.utc) + timedelta(days=30),
                is_active=True,
                stripe_subscription_id=None,
            )
            db.add(subscriber)
            db.commit()
            db.refresh(subscriber)
            print(f"Created subscriber id={subscriber.id} for user {email}")
        else:
            subscriber.subscription_id = tier.id
            subscriber.current_credits = tier.credits or 0
            subscriber.is_active = True
            subscriber.subscription_start_date = datetime.now(timezone.utc)
            subscriber.subscription_renew_date = datetime.now(timezone.utc) + timedelta(
                days=30
            )
            db.add(subscriber)
            db.commit()
            print(f"Updated subscriber id={subscriber.id} for user {email}")

        # Ensure admin_users row exists and is active for this email
        admin_row = (
            db.query(models.user.AdminUser)
            .filter(models.user.AdminUser.email == email.lower())
            .first()
        )
        if not admin_row:
            admin_row = models.user.AdminUser(
                email=email.lower(),
                created_by=user.id if user else None,
                is_active=True,
            )
            db.add(admin_row)
            db.commit()
            print("Created admin_users row and activated admin")
        else:
            if not admin_row.is_active:
                admin_row.is_active = True
                db.add(admin_row)
                db.commit()
                print("Activated existing admin_users row")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("email", help="Email to grant enterprise subscription")
    args = p.parse_args()
    grant(args.email)
