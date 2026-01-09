"""
Add note column to users table
"""
import os
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection (same as database.py)
password = quote_plus("Xb@qeJk3")
_raw_db = os.getenv(
    "DATABASE_URL", f"postgresql://postgres:{password}@localhost:5432/Tiger_leads"
)

# Tolerate misconfigured environment values
if isinstance(_raw_db, str):
    if _raw_db.startswith("DATABASE_URL="):
        _raw_db = _raw_db.split("=", 1)[1]
    if (_raw_db.startswith('"') and _raw_db.endswith('"')) or (
        _raw_db.startswith("'") and _raw_db.endswith("'")
    ):
        _raw_db = _raw_db[1:-1]

DATABASE_URL = _raw_db
engine = create_engine(DATABASE_URL)

def add_note_column():
    """Add note column to users table"""
    
    with engine.connect() as conn:
        print("Adding note column to users table...")
        
        # Add note column
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS note TEXT
        """))
        
        conn.commit()
        
        print("✅ Note column added successfully!")

if __name__ == "__main__":
    print("="*70)
    print("Add Note Column Migration")
    print("="*70)
    print("\nThis script will add a 'note' column to the users table.")
    print("This column can be used by admins to store notes about users.")
    print("="*70)
    
    confirm = input("\nProceed? (y/n): ")
    
    if confirm.lower() == "y":
        add_note_column()
    else:
        print("\n❌ Migration cancelled.")
