"""
Add 2FA columns to users table

This migration adds columns needed for Two-Factor Authentication:
- two_factor_enabled: Boolean flag
- two_factor_secret: TOTP secret key
- two_factor_backup_codes: Array of backup codes
- two_factor_enabled_at: Timestamp when 2FA was enabled
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from src.app.core.database import engine


def add_2fa_columns():
    """Add 2FA columns to users table"""
    
    with engine.connect() as conn:
        print("Adding 2FA columns to users table...")
        
        # Add two_factor_enabled column
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS two_factor_enabled BOOLEAN DEFAULT FALSE;
        """))
        print("✓ Added two_factor_enabled column")
        
        # Add two_factor_secret column
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS two_factor_secret VARCHAR(32);
        """))
        print("✓ Added two_factor_secret column")
        
        # Add two_factor_backup_codes column (array of text)
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS two_factor_backup_codes TEXT[];
        """))
        print("✓ Added two_factor_backup_codes column")
        
        # Add two_factor_enabled_at column
        conn.execute(text("""
            ALTER TABLE users 
            ADD COLUMN IF NOT EXISTS two_factor_enabled_at TIMESTAMP;
        """))
        print("✓ Added two_factor_enabled_at column")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    try:
        add_2fa_columns()
    except Exception as e:
        print(f"\n❌ Migration failed: {str(e)}")
        sys.exit(1)
