"""
Script to update subscription plans with correct pricing and seat information.

Subscription packages:
- Tier 1 – Starter: $89/month, 100 credits, 1 seat
- Tier 2 – Pro: $199/month, 250 credits, 3 seats
- Tier 3 – Enterprise: $399/month, 650 credits, 10 seats
"""

import os
from urllib.parse import quote_plus

import psycopg2
from dotenv import load_dotenv

load_dotenv()

password = quote_plus("Xb@qeJk3")
DATABASE_URL = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)


def update_subscriptions():
    """Update subscription plans with correct data."""
    conn_params = DATABASE_URL.replace("postgresql://", "").split("@")
    user_pass = conn_params[0].split(":")
    host_db = conn_params[1].split("/")
    host_port = host_db[0].split(":")

    conn = psycopg2.connect(
        dbname=host_db[1],
        user=user_pass[0],
        password=user_pass[1],
        host=host_port[0],
        port=host_port[1] if len(host_port) > 1 else "5432",
    )

    cursor = conn.cursor()

    try:
        print("Updating subscription plans...")

        # Delete existing subscriptions (if needed for clean slate)
        # Uncomment the following line if you want to start fresh
        # cursor.execute("DELETE FROM subscriptions;")

        # Check if subscriptions exist
        cursor.execute("SELECT COUNT(*) FROM subscriptions;")
        count = cursor.fetchone()[0]

        if count == 0:
            print("No subscriptions found. Creating new ones...")
            # Insert the three subscription tiers
            cursor.execute(
                """
                INSERT INTO subscriptions (name, price, credits, max_seats)
                VALUES
                    ('Starter', '$89/month', 100, 1),
                    ('Pro', '$199/month', 250, 3),
                    ('Enterprise', '$399/month', 650, 10)
                ON CONFLICT DO NOTHING;
            """
            )
            print("Created 3 subscription plans: Starter, Pro, Enterprise")
        else:
            print(f"Found {count} existing subscriptions. Updating them...")
            # Update existing subscriptions by name
            cursor.execute(
                """
                UPDATE subscriptions
                SET price = '$89/month', credits = 100, max_seats = 1
                WHERE LOWER(name) LIKE '%starter%' OR LOWER(name) LIKE '%tier 1%';
            """
            )

            cursor.execute(
                """
                UPDATE subscriptions
                SET price = '$199/month', credits = 250, max_seats = 3
                WHERE LOWER(name) LIKE '%pro%' OR LOWER(name) LIKE '%tier 2%';
            """
            )

            cursor.execute(
                """
                UPDATE subscriptions
                SET price = '$399/month', credits = 650, max_seats = 10
                WHERE LOWER(name) LIKE '%enterprise%' OR LOWER(name) LIKE '%elite%' OR LOWER(name) LIKE '%tier 3%';
            """
            )
            print("Updated existing subscriptions")

        conn.commit()

        # Display current subscriptions
        cursor.execute(
            """
            SELECT id, name, price, credits, max_seats, stripe_price_id
            FROM subscriptions
            ORDER BY credits;
        """
        )

        print("\nCurrent subscription plans:")
        print("-" * 80)
        for row in cursor.fetchall():
            plan_id, name, price, credits, seats, stripe_id = row
            print(
                f"ID: {plan_id} | {name:15} | {price:15} | {credits:4} credits | {seats:2} seats | Stripe: {stripe_id or 'Not set'}"
            )
        print("-" * 80)

        print("\n✅ Subscription plans updated successfully!")
        print("\nNEXT STEPS:")
        print("1. Go to Stripe Dashboard (https://dashboard.stripe.com)")
        print("2. Create Products for each subscription tier")
        print("3. Create recurring Prices for each product")
        print("4. Update the subscriptions table with the Stripe Price IDs:")
        print("\n   Example SQL commands:")
        print(
            "   UPDATE subscriptions SET stripe_price_id = 'price_xxxxx', stripe_product_id = 'prod_xxxxx' WHERE name = 'Starter';"
        )
        print(
            "   UPDATE subscriptions SET stripe_price_id = 'price_yyyyy', stripe_product_id = 'prod_yyyyy' WHERE name = 'Pro';"
        )
        print(
            "   UPDATE subscriptions SET stripe_price_id = 'price_zzzzz', stripe_product_id = 'prod_zzzzz' WHERE name = 'Enterprise';"
        )

    except Exception as e:
        conn.rollback()
        print(f"Error updating subscriptions: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    update_subscriptions()
