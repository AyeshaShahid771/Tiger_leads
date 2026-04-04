"""
Migration Script: Add Missing Columns to existing tables
This script adds missing columns to pending_jurisdictions and pending_user_types tables.

Run this script after deploying code changes that reference new columns.
"""

import logging
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    inspect,
    text,
)
from sqlalchemy.exc import ProgrammingError
from src.app.core.database import Base, engine
from src.app.models.user import PendingJurisdiction, PendingUserType

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def ensure_table_exists(table_class, table_name: str):
    """Create table if it doesn't exist"""
    try:
        inspector = inspect(engine)
        if table_name not in inspector.get_table_names():
            logger.info(f"Creating {table_name} table...")
            Base.metadata.create_tables([table_class.__table__], bind=engine)
            logger.info(f"✓ {table_name} table created")
            return True
        else:
            logger.info(f"✓ {table_name} table already exists")
            return False
    except Exception as e:
        logger.error(f"✗ Error creating {table_name}: {str(e)}")
        return False


def add_column_if_missing(table_name: str, column_name: str, column_type: str):
    """Add a column to a table if it doesn't exist"""
    try:
        inspector = inspect(engine)

        # Check if table exists
        if table_name not in inspector.get_table_names():
            logger.warning(f"✗ Table {table_name} does not exist. Create it first.")
            return False

        # Get existing columns
        columns = inspector.get_columns(table_name)
        existing_column_names = [col["name"] for col in columns]

        if column_name in existing_column_names:
            logger.info(f"✓ Column {table_name}.{column_name} already exists")
            return False

        # Add the missing column
        logger.info(f"Adding column {table_name}.{column_name} ({column_type})...")

        with engine.connect() as conn:
            if column_type == "TEXT":
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" TEXT NULL'
            elif column_type == "INTEGER":
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" INTEGER'
            else:
                sql = f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {column_type}'

            conn.execute(text(sql))
            conn.commit()

        logger.info(f"✓ Column {table_name}.{column_name} added successfully")
        return True

    except ProgrammingError as e:
        if "already exists" in str(e):
            logger.info(f"✓ Column {table_name}.{column_name} already exists")
            return False
        else:
            logger.error(f"✗ Error adding column: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"✗ Error adding column {table_name}.{column_name}: {str(e)}")
        return False


def main():
    """Run all migrations"""
    try:
        logger.info("\n" + "=" * 80)
        logger.info("DATABASE SCHEMA MIGRATION - Add Missing Columns")
        logger.info("=" * 80 + "\n")

        logger.info("Step 1: Ensuring tables exist...")
        ensure_table_exists(PendingJurisdiction, "pending_jurisdictions")
        ensure_table_exists(PendingUserType, "pending_user_types")

        logger.info("\nStep 2: Adding missing columns...")

        # Add rejection_note to pending_jurisdictions
        add_column_if_missing("pending_jurisdictions", "rejection_note", "TEXT")

        # Add rejection_note to pending_user_types (for consistency)
        add_column_if_missing("pending_user_types", "rejection_note", "TEXT")

        logger.info("\n" + "=" * 80)
        logger.info("✓ Migration completed successfully!")
        logger.info("=" * 80 + "\n")

        return True

    except Exception as e:
        logger.error(f"✗ Migration failed: {str(e)}")
        logger.exception(e)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
