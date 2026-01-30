"""
Database migration script to create push_subscriptions table.

Run this script with:
    Tiger_leads\Scripts\activate.bat
    python add_push_subscriptions_table.py
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("❌ DATABASE_URL not found in environment variables")
    exit(1)

engine = create_engine(DATABASE_URL)

# SQL to create push_subscriptions table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    endpoint VARCHAR NOT NULL UNIQUE,
    p256dh_key VARCHAR NOT NULL,
    auth_key VARCHAR NOT NULL,
    user_agent VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_notified_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user_id ON push_subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_last_notified ON push_subscriptions(last_notified_at);
"""

try:
    with engine.connect() as conn:
        # Execute the SQL
        conn.execute(text(CREATE_TABLE_SQL))
        conn.commit()
        
        print("✅ Successfully created push_subscriptions table")
        print("✅ Created index on user_id")
        print("✅ Created index on last_notified_at")
        
        # Verify table was created
        result = conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'push_subscriptions'
            ORDER BY ordinal_position
        """))
        
        print("\n📋 Table columns:")
        for row in result:
            print(f"  - {row[0]}: {row[1]}")
            
except Exception as e:
    print(f"❌ Error creating table: {str(e)}")
    exit(1)
