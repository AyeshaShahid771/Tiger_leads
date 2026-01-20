"""
Script to fix the users table sequence issue.
Resets the sequence to max(id) + 1.
"""

import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def fix_users_sequence():
    """Fix the users table sequence."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        try:
            print("Fixing users table sequence...")
            print("=" * 60)
            
            # Get the current max ID
            result = conn.execute(text("SELECT MAX(id) FROM users"))
            max_id = result.fetchone()[0]
            
            if max_id is None:
                max_id = 0
            
            print(f"Current max ID in users table: {max_id}")
            
            # Set the sequence to max_id + 1
            next_id = max_id + 1
            conn.execute(text(f"SELECT setval('users_id_seq', {next_id}, false)"))
            
            conn.commit()
            
            print(f"✅ Sequence reset to: {next_id}")
            print("=" * 60)
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            conn.rollback()
            raise

if __name__ == "__main__":
    fix_users_sequence()
