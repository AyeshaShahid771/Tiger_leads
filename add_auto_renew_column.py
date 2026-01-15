"""
Migration to add auto_renew column to subscribers table.
Tracks whether user wants automatic subscription renewal (default: True).
"""

from sqlalchemy import create_engine, text, inspect
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables")

engine = create_engine(DATABASE_URL)


def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in the table"""
    inspector = inspect(engine)
    columns = [col["name"] for col in inspector.get_columns(table_name)]
    return column_name in columns


def add_auto_renew_column():
    """Add auto_renew column to subscribers table"""
    
    with engine.connect() as conn:
        # Check if column already exists
        if check_column_exists(engine, "subscribers", "auto_renew"):
            print("✓ Column 'auto_renew' already exists in 'subscribers' table")
            return
        
        print("Adding 'auto_renew' column to 'subscribers' table...")
        
        # Add auto_renew column (BOOLEAN, default TRUE, NOT NULL)
        conn.execute(text("""
            ALTER TABLE subscribers 
            ADD COLUMN auto_renew BOOLEAN DEFAULT TRUE NOT NULL
        """))
        
        conn.commit()
        print("✓ Successfully added 'auto_renew' column to 'subscribers' table")
        print("  Default value: TRUE (users must opt-out)")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("MIGRATION: Add auto_renew column to subscribers table")
    print("="*60 + "\n")
    
    try:
        add_auto_renew_column()
        print("\n" + "="*60)
        print("✓ Migration completed successfully!")
        print("="*60 + "\n")
    except Exception as e:
        print(f"\n❌ Migration failed: {e}\n")
        raise
