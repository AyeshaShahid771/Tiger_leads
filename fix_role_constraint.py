"""
Fix the users table role constraint to allow 'Supplier' role.

Run this script to update the database constraint.
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/dbname")

# Create engine
engine = create_engine(DATABASE_URL)

def fix_role_constraint():
    """Update the users table role constraint to allow both Contractor and Supplier"""
    
    try:
        with engine.connect() as connection:
            # Drop the existing constraint
            print("Dropping old role constraint...")
            connection.execute(text("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_role_check;"))
            connection.commit()
            
            # Add new constraint that allows both Contractor and Supplier
            print("Adding new role constraint...")
            connection.execute(text(
                "ALTER TABLE users ADD CONSTRAINT users_role_check "
                "CHECK (role IN ('Contractor', 'Supplier') OR role IS NULL);"
            ))
            connection.commit()
            
            print("✅ Role constraint updated successfully!")
            print("   Allowed values: 'Contractor', 'Supplier', or NULL")
            return True
            
    except Exception as e:
        print(f"❌ Error updating role constraint: {str(e)}")
        return False


if __name__ == "__main__":
    print("Fixing users table role constraint...")
    fix_role_constraint()
