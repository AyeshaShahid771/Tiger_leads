"""
Migration script to add Stripe-related fields.
This adds:
1. stripe_customer_id to users table
2. stripe_subscription_id and subscription_status to subscribers table
3. stripe_price_id and stripe_product_id to subscriptions table
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


def run_migration():
    """Execute migration to add Stripe fields."""
    # Parse connection string
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
        print("Starting Stripe fields migration...")

        # 1. Add stripe_customer_id to users table
        print("Adding stripe_customer_id to users table...")
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(255) UNIQUE;
        """
        )

        # Create index on stripe_customer_id
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_stripe_customer_id ON users(stripe_customer_id);
        """
        )

        # 2. Add Stripe fields to subscribers table
        print("Adding Stripe fields to subscribers table...")
        cursor.execute(
            """
            ALTER TABLE subscribers
            ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(255) UNIQUE,
            ADD COLUMN IF NOT EXISTS subscription_status VARCHAR(50) DEFAULT 'inactive';
        """
        )

        # Create index on stripe_subscription_id
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subscribers_stripe_subscription_id 
            ON subscribers(stripe_subscription_id);
        """
        )

        # 3. Add Stripe fields to subscriptions table
        print("Adding Stripe fields to subscriptions table...")
        cursor.execute(
            """
            ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(255) UNIQUE,
            ADD COLUMN IF NOT EXISTS stripe_product_id VARCHAR(255);
        """
        )

        # Create indexes
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_price_id 
            ON subscriptions(stripe_price_id);
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_product_id 
            ON subscriptions(stripe_product_id);
        """
        )

        # 4. Update existing subscribers to have inactive status
        print("Setting default subscription_status for existing subscribers...")
        cursor.execute(
            """
            UPDATE subscribers
            SET subscription_status = CASE
                WHEN is_active = TRUE THEN 'active'
                ELSE 'inactive'
            END
            WHERE subscription_status IS NULL;
        """
        )

        conn.commit()
        print("Stripe fields migration completed successfully!")
        print("\nNEXT STEPS:")
        print("1. Create subscription products in Stripe Dashboard")
        print("2. Update your subscriptions table with Stripe Price IDs:")
        print(
            "   UPDATE subscriptions SET stripe_price_id = 'price_xxxxx', stripe_product_id = 'prod_xxxxx' WHERE name = 'Starter';"
        )
        print("3. Set STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in your .env file")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
