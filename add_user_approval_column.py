"""
Migration script to add approved_by_admin column to users table.

This column tracks admin approval status for user accounts:
- "pending": Default status on signup, awaiting admin review
- "approved": User has been approved by admin
- "rejected": User has been rejected by admin
"""

import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not found in environment variables")
    sys.exit(1)

engine = create_engine(DATABASE_URL)


def run_migration():
    """Execute the migration."""
    with engine.connect() as conn:
        print("=" * 60)
        print("User Approval Column Migration")
        print("=" * 60)
        
        # Check if approved_by_admin column already exists
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='approved_by_admin'
        """))
        
        if result.fetchone():
            print("✓ Column 'approved_by_admin' already exists in users table")
        else:
            print("Adding 'approved_by_admin' column to users table...")
            
            # Add approved_by_admin column with default value 'pending'
            conn.execute(text("""
                ALTER TABLE users
                ADD COLUMN approved_by_admin VARCHAR(20) DEFAULT 'pending'
            """))
            conn.commit()
            
            print("✓ Column 'approved_by_admin' added successfully")
            
            # Update existing users to 'pending' status
            print("Setting existing users to 'pending' status...")
            conn.execute(text("""
                UPDATE users
                SET approved_by_admin = 'pending'
                WHERE approved_by_admin IS NULL
            """))
            conn.commit()
            print("✓ Existing users updated to 'pending' status")
        
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
        
        # Verify final schema
        print("\nVerifying users table schema:")
        result = conn.execute(text("""
            SELECT column_name, data_type, column_default, is_nullable
            FROM information_schema.columns 
            WHERE table_name='users' AND column_name='approved_by_admin'
        """))
        
        column = result.fetchone()
        if column:
            print("\nApproval column details:")
            print(f"  - Column: {column[0]}")
            print(f"  - Type: {column[1]}")
            print(f"  - Default: {column[2]}")
            print(f"  - Nullable: {column[3]}")
            print("\n✓ approved_by_admin column successfully added to users table")
        else:
            print("\n⚠ Warning: approved_by_admin column not found after migration")
        
        # Show count of users by approval status
        print("\nUser approval status summary:")
        result = conn.execute(text("""
            SELECT approved_by_admin, COUNT(*) as count
            FROM users
            GROUP BY approved_by_admin
            ORDER BY approved_by_admin
        """))
        
        statuses = result.fetchall()
        for status in statuses:
            print(f"  - {status[0]}: {status[1]} users")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"\n✗ Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
