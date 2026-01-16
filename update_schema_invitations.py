
import logging
from sqlalchemy import text
from src.app.core.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_schema():
    """
    Adds invited_name, invited_phone_number, and invited_user_type columns 
    to the user_invitations table if they don't exist.
    """
    logger.info("Starting schema update for user_invitations table...")
    
    with engine.connect() as connection:
        # 1. Add invited_name
        try:
            logger.info("Checking/Adding invited_name column...")
            connection.execute(text("""
                ALTER TABLE user_invitations 
                ADD COLUMN IF NOT EXISTS invited_name VARCHAR(255);
            """))
            logger.info("✓ invited_name column processed.")
        except Exception as e:
            logger.error(f"Error adding invited_name: {e}")

        # 2. Add invited_phone_number
        try:
            logger.info("Checking/Adding invited_phone_number column...")
            connection.execute(text("""
                ALTER TABLE user_invitations 
                ADD COLUMN IF NOT EXISTS invited_phone_number VARCHAR(20);
            """))
            logger.info("✓ invited_phone_number column processed.")
        except Exception as e:
            logger.error(f"Error adding invited_phone_number: {e}")

        # 3. Add invited_user_type
        try:
            logger.info("Checking/Adding invited_user_type column...")
            # Note: Using text[] for array of strings in PostgreSQL
            connection.execute(text("""
                ALTER TABLE user_invitations 
                ADD COLUMN IF NOT EXISTS invited_user_type TEXT[];
            """))
            logger.info("✓ invited_user_type column processed.")
        except Exception as e:
            logger.error(f"Error adding invited_user_type: {e}")

        # Commit the transaction
        connection.commit()
        logger.info("Schema update completed successfully!")

if __name__ == "__main__":
    update_schema()
