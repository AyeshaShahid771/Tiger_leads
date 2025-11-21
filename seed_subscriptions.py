"""
Script to seed subscription plans into the database.
Run this once to initialize the subscription tiers.
"""
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from src.app.core.database import SessionLocal
from src.app.models.user import Subscription


def seed_subscriptions():
    db = SessionLocal()
    try:
        # Check if subscriptions already exist
        existing = db.query(Subscription).count()
        if existing > 0:
            print(f"✓ Subscriptions already exist ({existing} plans found)")
            return

        # Create subscription plans
        subscriptions = [
            Subscription(name="Starter", price="$89.99/month", tokens=100),
            Subscription(name="Pro", price="$199.99/month", tokens=300),
            Subscription(name="Elite", price="$499.99/month", tokens=1000),
        ]

        db.add_all(subscriptions)
        db.commit()

        print("✓ Successfully created subscription plans:")
        for sub in subscriptions:
            print(f"  - {sub.name}: {sub.price} ({sub.tokens} tokens)")

    except Exception as e:
        print(f"✗ Error seeding subscriptions: {str(e)}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding subscription plans...")
    seed_subscriptions()
