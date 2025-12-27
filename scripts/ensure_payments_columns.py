import logging
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `from src...` imports work when running
# this script directly (script lives in the `scripts/` folder).
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from sqlalchemy import inspect, text

from src.app.core.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def rename_subscription_to_subscriber():
    """Idempotently rename payments.subscription_id -> payments.subscriber_id

    - If the `payments` table does not exist, the script exits with a log message.
    - If `subscription_id` exists and `subscriber_id` does not, the column is renamed.
    - If `subscriber_id` is missing (and `subscription_id` wasn't present), it will be added.
    - The script will also ensure minimal columns (`amount`, `payment_date`, `created_at`) exist.
    """
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if "payments" not in tables:
        logger.error(
            "payments table does not exist in the connected database. Nothing to rename."
        )
        return

    cols = [c["name"] for c in inspector.get_columns("payments")]

    with engine.connect() as conn:
        # Rename subscription_id -> subscriber_id when appropriate
        if "subscription_id" in cols and "subscriber_id" not in cols:
            try:
                logger.info(
                    "Renaming payments.subscription_id -> payments.subscriber_id"
                )
                conn.execute(
                    text(
                        "ALTER TABLE payments RENAME COLUMN subscription_id TO subscriber_id"
                    )
                )
                conn.commit()
                # refresh local cols list
                cols = [c["name"] for c in inspector.get_columns("payments")]
            except Exception:
                logger.exception("Failed to rename subscription_id to subscriber_id")

        # Ensure subscriber_id exists
        if "subscriber_id" not in cols:
            try:
                logger.info("Adding payments.subscriber_id column")
                conn.execute(
                    text(
                        "ALTER TABLE payments ADD COLUMN IF NOT EXISTS subscriber_id INTEGER"
                    )
                )
                conn.commit()
            except Exception:
                logger.exception("Failed to add subscriber_id column to payments")

        # Ensure minimal required columns exist (id assumed present)
        try:
            conn.execute(
                text("ALTER TABLE payments ADD COLUMN IF NOT EXISTS amount NUMERIC")
            )
            conn.execute(
                text(
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_date TIMESTAMP"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE payments ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now()"
                )
            )
            conn.commit()
        except Exception:
            logger.exception("Failed to ensure minimal payments columns")


if __name__ == "__main__":
    logger.info("Running payments column rename/ensure script...")
    rename_subscription_to_subscriber()
    logger.info("Done.")
    logger.info("Done.")
