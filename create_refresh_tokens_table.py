"""
Migration: Create refresh_tokens table

This table stores refresh tokens for token rotation and revocation.
Each refresh token is securely hashed and linked to a user.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def run_migration():
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Check if table already exists
        check_table = text(
            """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_name = 'refresh_tokens'
        """
        )

        result = conn.execute(check_table).fetchone()

        if not result:
            print("Creating refresh_tokens table...")
            create_table = text(
                """
                CREATE TABLE refresh_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    expires_at TIMESTAMP NOT NULL,
                    is_revoked BOOLEAN DEFAULT FALSE NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_used_at TIMESTAMP,
                    user_agent VARCHAR(500),
                    ip_address VARCHAR(45)
                );
                
                CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
                CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
                CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
            """
            )
            conn.execute(create_table)
            conn.commit()
            print("✓ Created refresh_tokens table with indexes")
        else:
            print("✓ refresh_tokens table already exists")

        print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    run_migration()
