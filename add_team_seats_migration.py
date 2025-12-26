"""
Migration script to add team seats functionality.
This adds:
1. parent_user_id to users table
2. seats_used and max_seats to subscriptions table
3. user_invitations 
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
    """Execute migration to add team seats functionality."""
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
        print("Starting migration...")

        # 1. Add parent_user_id to users table
        print("Adding parent_user_id to users table...")
        cursor.execute(
            """
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS parent_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
        """
        )

        # Create index on parent_user_id for faster lookups
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_parent_user_id ON users(parent_user_id);
        """
        )

        # 2. Add seats columns to subscriptions table
        print("Adding seats columns to subscriptions table...")
        cursor.execute(
            """
            ALTER TABLE subscriptions
            ADD COLUMN IF NOT EXISTS max_seats INTEGER DEFAULT 1;
        """
        )

        # 3. Add seats_used to subscribers table (tracking actual usage)
        print("Adding seats_used to subscribers table...")
        cursor.execute(
            """
            ALTER TABLE subscribers
            ADD COLUMN IF NOT EXISTS seats_used INTEGER DEFAULT 1;
        """
        )

        # 4. Create user_invitations table
        print("Creating user_invitations table...")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_invitations (
                id SERIAL PRIMARY KEY,
                inviter_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                invited_email VARCHAR(255) NOT NULL,
                invitation_token VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'revoked')),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """
        )

        # Create indexes for user_invitations
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_invitations_inviter ON user_invitations(inviter_user_id);
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_invitations_token ON user_invitations(invitation_token);
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_invitations_email ON user_invitations(invited_email);
        """
        )

        # 5. Update existing subscriptions with max_seats based on tier
        print("Setting max_seats for existing subscription tiers...")
        cursor.execute(
            """
            UPDATE subscriptions
            SET max_seats = CASE
                WHEN LOWER(name) LIKE '%free%' THEN 0
                WHEN LOWER(name) LIKE '%starter%' OR LOWER(name) LIKE '%tier 1%' THEN 1
                WHEN LOWER(name) LIKE '%pro%' OR LOWER(name) LIKE '%tier 2%' THEN 3
                WHEN LOWER(name) LIKE '%enterprise%' OR LOWER(name) LIKE '%elite%' OR LOWER(name) LIKE '%tier 3%' THEN 10
                ELSE 1
            END
            WHERE max_seats IS NULL OR max_seats = 1;
        """
        )

        # 6. Initialize seats_used to 1 for all existing active subscribers
        print("Initializing seats_used for existing subscribers...")
        cursor.execute(
            """
            UPDATE subscribers
            SET seats_used = 1
            WHERE seats_used IS NULL;
        """
        )

        conn.commit()
        print("Migration completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
