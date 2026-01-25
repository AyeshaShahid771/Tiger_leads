"""
Migration script to fix notification sequence issue.
Run this once to reset the notification ID sequence.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in .env file")
    exit(1)

print(f"Connecting to database...")
print(f"Database: {DATABASE_URL.split('@')[1] if '@' in DATABASE_URL else 'localhost'}")

engine = create_engine(DATABASE_URL)

# SQL to fix notification sequence
sql_commands = [
    """
    -- Reset the notification sequence to the correct value
    SELECT setval('notifications_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM notifications), false);
    """,
    """
    -- Verify the fix
    SELECT currval('notifications_id_seq') as current_sequence_value;
    """,
]

try:
    with engine.connect() as conn:
        print("\n" + "=" * 50)
        print("Fixing notification sequence...")
        print("=" * 50)
        
        # Get current max ID
        result = conn.execute(text("SELECT MAX(id) as max_id FROM notifications"))
        max_id = result.fetchone()[0] or 0
        print(f"\nCurrent max notification ID: {max_id}")
        
        # Reset sequence
        for sql in sql_commands:
            print(f"\nExecuting: {sql.strip()}")
            result = conn.execute(text(sql))
            conn.commit()
            print("✓ Success")
            
            # Show result if available
            try:
                row = result.fetchone()
                if row:
                    print(f"  Result: {dict(row)}")
            except:
                pass

    print("\n" + "=" * 50)
    print("✓ Notification sequence fixed successfully!")
    print("=" * 50)
    print("\nYou can now:")
    print("1. Try the contractor approval endpoint again")
    print("2. New notifications will be created without ID conflicts")

except Exception as e:
    print(f"\n✗ Error: {str(e)}")
    print("\nThis might mean:")
    print("- Database connection failed")
    print("- Sequence doesn't exist (check table name)")
    print("- Permission issues")

finally:
    engine.dispose()
