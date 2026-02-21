"""
Migration: Add admin_settings table for storing admin configuration

Creates admin_settings table to store admin-level configuration settings
like auto_post_jobs toggle, and inserts default 'auto_post_jobs' = 'true' setting.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment variables")

# Create engine
engine = create_engine(DATABASE_URL)


def run_migration():
    """Create admin_settings table and insert default values"""

    with engine.connect() as conn:
        # Start transaction
        trans = conn.begin()

        try:
            # Check if table already exists
            check_table = text(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'admin_settings'
                );
            """
            )

            result = conn.execute(check_table)
            table_exists = result.scalar()

            if table_exists:
                print("✓ admin_settings table already exists")
            else:
                # Create admin_settings table
                create_table = text(
                    """
                    CREATE TABLE admin_settings (
                        id SERIAL PRIMARY KEY,
                        setting_key VARCHAR(100) UNIQUE NOT NULL,
                        setting_value VARCHAR(255),
                        description TEXT,
                        updated_at TIMESTAMP DEFAULT NOW(),
                        updated_by INTEGER REFERENCES admin_users(id),
                        created_at TIMESTAMP DEFAULT NOW()
                    );
                """
                )

                conn.execute(create_table)
                print("✅ Created admin_settings table")

                # Create index on setting_key for faster lookups
                create_index = text(
                    """
                    CREATE INDEX idx_admin_settings_key ON admin_settings(setting_key);
                """
                )
                conn.execute(create_index)
                print("✅ Created index on setting_key")

            # Check if default setting exists
            check_setting = text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM admin_settings 
                    WHERE setting_key = 'auto_post_jobs'
                );
            """
            )

            result = conn.execute(check_setting)
            setting_exists = result.scalar()

            if setting_exists:
                print("✓ auto_post_jobs setting already exists")
            else:
                # Insert default auto_post_jobs setting
                insert_default = text(
                    """
                    INSERT INTO admin_settings (setting_key, setting_value, description) 
                    VALUES (
                        'auto_post_jobs', 
                        'true',
                        'Auto-post jobs from upload endpoints based on timing logic (true/false)'
                    );
                """
                )

                conn.execute(insert_default)
                print("✅ Inserted default auto_post_jobs setting (value: true)")

            # Commit transaction
            trans.commit()
            print("\n✅ Migration completed successfully!")

        except Exception as e:
            # Rollback on error
            trans.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            raise


if __name__ == "__main__":
    print("=" * 60)
    print("Running Migration: Add admin_settings table")
    print("=" * 60)
    run_migration()
