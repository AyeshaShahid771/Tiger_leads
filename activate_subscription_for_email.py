"""
Activate or create a subscription for a user by email.

Usage:
    python activate_subscription_for_email.py --email f2023065030@umt.edu.pk

If no --plan is provided the script will pick the 'Starter' plan if present,
otherwise the first subscription in the `subscriptions` table.

This script reuses the project's SQLAlchemy configuration and models.
"""

import argparse
from datetime import datetime, timedelta

from sqlalchemy import func

from src.app.core.database import SessionLocal
from src.app.models import user as models_user


def activate_subscription(email: str, plan_name: str | None = None, months: int = 1):
    db = SessionLocal()
    try:
        # Find the user
        user = (
            db.query(models_user.User).filter(models_user.User.email == email).first()
        )
        if not user:
            print(f"User with email '{email}' not found.")
            return 1

        # Choose subscription plan
        subscription = None
        if plan_name:
            subscription = (
                db.query(models_user.Subscription)
                .filter(func.lower(models_user.Subscription.name) == plan_name.lower())
                .first()
            )

        if not subscription:
            # Prefer Starter, otherwise first plan
            subscription = (
                db.query(models_user.Subscription)
                .filter(func.lower(models_user.Subscription.name).like("%starter%"))
                .first()
            )

        if not subscription:
            subscription = (
                db.query(models_user.Subscription)
                .order_by(models_user.Subscription.id)
                .first()
            )

        if not subscription:
            print("No subscription plans found in the database. Aborting.")
            return 1

        # Find or create subscriber row
        subscriber = (
            db.query(models_user.Subscriber)
            .filter(models_user.Subscriber.user_id == user.id)
            .first()
        )

        now = datetime.utcnow()
        renew_date = now + timedelta(days=30 * months)

        if not subscriber:
            subscriber = models_user.Subscriber(
                user_id=user.id,
                subscription_id=subscription.id,
                current_credits=subscription.credits or 0,
                total_spending=0,
                seats_used=0,
                subscription_start_date=now,
                subscription_renew_date=renew_date,
                is_active=True,
                subscription_status="active",
            )
            db.add(subscriber)
            db.commit()
            db.refresh(subscriber)
            print(
                f"Created and activated subscription (plan='{subscription.name}') for {email}."
            )
        else:
            subscriber.subscription_id = subscription.id
            subscriber.current_credits = (
                subscription.credits or subscriber.current_credits
            )
            subscriber.subscription_start_date = now
            subscriber.subscription_renew_date = renew_date
            subscriber.is_active = True
            subscriber.subscription_status = "active"
            db.add(subscriber)
            db.commit()
            db.refresh(subscriber)
            print(
                f"Updated and activated subscription (plan='{subscription.name}') for {email}."
            )

        print("Subscriber row:")
        print(
            {
                "user_id": subscriber.user_id,
                "subscription_id": subscriber.subscription_id,
                "current_credits": subscriber.current_credits,
                "is_active": subscriber.is_active,
                "subscription_status": subscriber.subscription_status,
                "subscription_start_date": subscriber.subscription_start_date,
                "subscription_renew_date": subscriber.subscription_renew_date,
            }
        )
        return 0
    except Exception as e:
        print(f"Error activating subscription: {e}")
        db.rollback()
        return 2
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(
        description="Activate subscription for a user by email"
    )
    parser.add_argument(
        "--email", required=False, default="f2023065030@umt.edu.pk", help="User email"
    )
    parser.add_argument(
        "--plan", required=False, help="Subscription plan name to assign (optional)"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        help="Number of months until renewal (default: 1)",
    )
    args = parser.parse_args()

    exit_code = activate_subscription(args.email, args.plan, args.months)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
