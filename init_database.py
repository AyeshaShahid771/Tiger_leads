"""
Database Initialization Script
This script creates all tables in the database if they don't exist.
Run this script before starting the application to ensure all tables are created.
"""

import logging
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import inspect, text

from app.core.database import Base, engine
from app.models.user import Contractor, Notification, PasswordReset, Supplier, User

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def create_all_tables():
    """Create all tables defined in the models"""
    try:
        logger.info("Starting database initialization...")
        logger.info(f"Database URL: {engine.url}")

        # Get list of existing tables
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"Existing tables: {existing_tables}")

        # Create all tables
        logger.info("Creating tables from models...")
        Base.metadata.create_all(bind=engine)

        # Verify all tables were created
        inspector = inspect(engine)
        final_tables = inspector.get_table_names()

        expected_tables = [
            "users",
            "notifications",
            "password_resets",
            "contractors",
            "suppliers",
        ]

        logger.info("\n" + "=" * 60)
        logger.info("DATABASE INITIALIZATION SUMMARY")
        logger.info("=" * 60)

        for table in expected_tables:
            if table in final_tables:
                status = "✓ EXISTS" if table in existing_tables else "✓ CREATED"
                logger.info(f"{status:12} | {table}")
            else:
                logger.error(f"✗ MISSING   | {table}")

        logger.info("=" * 60)

        # Verify constraints and indexes
        logger.info("\nVerifying table constraints...")

        for table in expected_tables:
            if table in final_tables:
                # Get foreign keys
                fks = inspector.get_foreign_keys(table)
                if fks:
                    logger.info(f"  {table}: {len(fks)} foreign key(s)")

                # Get indexes
                indexes = inspector.get_indexes(table)
                if indexes:
                    logger.info(f"  {table}: {len(indexes)} index(es)")

        logger.info("\n✓ Database initialization completed successfully!")
        return True

    except Exception as e:
        logger.error(f"✗ Error initializing database: {str(e)}")
        logger.exception(e)
        return False


def verify_database_connection():
    """Verify database connection is working"""
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
            logger.info("✓ Database connection verified")
            return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {str(e)}")
        return False


def main():
    """Main execution function"""
    logger.info("=" * 60)
    logger.info("DATABASE INITIALIZATION SCRIPT")
    logger.info("=" * 60)

    # Step 1: Verify connection
    if not verify_database_connection():
        logger.error("Failed to connect to database. Please check your DATABASE_URL.")
        sys.exit(1)

    # Step 2: Create tables
    if not create_all_tables():
        logger.error("Failed to create tables.")
        sys.exit(1)

    logger.info("\n✓ All database initialization tasks completed successfully!")
    logger.info("You can now start your application.")


if __name__ == "__main__":
    main()
