"""
Run database migration to add team member roles
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get database URL from environment
database_url = os.getenv("DATABASE_URL")
if not database_url:
    print("❌ DATABASE_URL environment variable not set")
    exit(1)

print(f"📊 Connecting to database...")

# Create engine
engine = create_engine(database_url)

print("🔄 Running migration...")

try:
    with engine.connect() as conn:
        # Step 1: Add role column to user_invitations
        print("  1. Adding 'role' column to user_invitations table...")
        conn.execute(text("""
            ALTER TABLE user_invitations 
            ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'viewer' CHECK (role IN ('viewer', 'editor'))
        """))
        conn.commit()
        
        # Step 2: Add team_role column to users
        print("  2. Adding 'team_role' column to users table...")
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS team_role VARCHAR(20) DEFAULT NULL CHECK (team_role IN ('viewer', 'editor', NULL))
        """))
        conn.commit()
        
        # Step 3: Add comments
        print("  3. Adding column comments...")
        try:
            conn.execute(text("COMMENT ON COLUMN users.role IS 'User type: Contractor or Supplier'"))
            conn.execute(text("COMMENT ON COLUMN users.team_role IS 'Team member role: viewer or editor (only for sub-users with parent_user_id)'"))
            conn.execute(text("COMMENT ON COLUMN user_invitations.role IS 'Team member role for invited user: viewer (read-only) or editor (full access)'"))
            conn.commit()
        except Exception as e:
            print(f"    Warning: Could not add comments: {e}")
    
    print("\n✅ Migration completed successfully!")
    print("\nAdded columns:")
    print("  - user_invitations.role (viewer/editor, default: viewer)")
    print("  - users.team_role (viewer/editor, default: NULL)")
    
except Exception as e:
    print(f"\n❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)
